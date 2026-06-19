import os
import json
import urllib.request
import urllib.parse
import time
import re
import random
import shutil
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

API_URL = "https://wiki.biligame.com/sr/api.php"
ROOT_DIR = Path(__file__).resolve().parents[2]
WIKI_DIR = os.fspath(ROOT_DIR / "references" / "wiki")
CONFIG_PATH = os.fspath(ROOT_DIR / "config.json")
STATE_PATH = os.path.join(WIKI_DIR, "state.json")
MAX_WORKERS = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://wiki.biligame.com/sr/%E9%A6%96%E9%A1%B5",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive"
}

def request_api(params, retries=4):
    """请求 API，并针对 JSONDecodeError 和 HTTP 错误进行指数退避重试"""
    url_params = urllib.parse.urlencode(params)
    req_url = f"{API_URL}?{url_params}"
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(req_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as response:
                content_bytes = response.read()
                return json.loads(content_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            wait_time = (attempt + 1) * random.uniform(3.0, 6.0)
            if attempt == retries - 1:
                print(f"\n[解析失败] 被 EdgeOne 拦截或返回非 JSON 数据，达到最大重试上限 | URL: {req_url}")
                return None
            time.sleep(wait_time)
        except Exception as e:
            wait_time = (attempt + 1) * random.uniform(3.0, 6.0)
            if attempt == retries - 1:
                print(f"\n[请求失败] {e} | URL: {req_url}")
                return None
            time.sleep(wait_time)
    return None

def clean_filename(name):
    """清理文件名"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def load_state():
    """读取本地 state.json 文件"""
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"读取状态文件 state.json 出错，重置为空状态: {e}")
    return {}

def save_state(state):
    """保存 state.json 文件"""
    os.makedirs(WIKI_DIR, exist_ok=True)
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存状态文件 state.json 失败: {e}")

def get_category_pages(category_name, limit=None):
    """分页获取指定分类下的页面，包含条目名称与最后更新时间戳"""
    pages = []
    cmcontinue = None
    
    while True:
        cmlimit = "500"
        if limit is not None:
            remaining = limit - len(pages)
            if remaining <= 0:
                break
            cmlimit = str(min(500, remaining))
            
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category_name}",
            "cmlimit": cmlimit,
            "format": "json",
            "utf8": "1"
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
            
        data = request_api(params)
        if not data:
            break
            
        members = data.get("query", {}).get("categorymembers", [])
        for member in members:
            if member.get("ns") == 0:
                pages.append({
                    "title": member.get("title")
                })
                
        if limit is not None and len(pages) >= limit:
            pages = pages[:limit]
            break
            
        if "continue" in data and "cmcontinue" in data["continue"]:
            cmcontinue = data["continue"]["cmcontinue"]
            time.sleep(random.uniform(0.1, 0.3))
        else:
            break
            
    return pages

def get_pages_timestamps(titles):
    """批量获取页面的最后修改时间戳 (单次最大限制50个标题)"""
    if not titles:
        return {}
        
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "timestamp",
        "titles": "|".join(titles),
        "format": "json",
        "utf8": "1"
    }
    data = request_api(params)
    if not data:
        return {}
        
    results = {}
    pages = data.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        title = page_data.get("title")
        revisions = page_data.get("revisions", [])
        if title and revisions:
            results[title] = revisions[0].get("timestamp", "")
    return results

def fetch_and_save_page(title, cat_dir, timestamp, state_key):
    """下载指定页面并保存为文件，下载成功返回最新时间戳"""
    clean_title = clean_filename(title)
    filepath = os.path.join(cat_dir, f"{clean_title}.txt")
    
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "titles": title,
        "format": "json",
        "utf8": "1"
    }
    data = request_api(params)
    if not data:
        return False
        
    pages = data.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        revisions = page_data.get("revisions", [])
        if revisions:
            content = revisions[0].get("*", "")
            if content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                return True
    return False

def process_category(category, state, limit=None):
    """处理单个分类的页面扫描、最新时间戳获取和增量状态对比"""
    cat_dir = os.path.join(WIKI_DIR, clean_filename(category))
    os.makedirs(cat_dir, exist_ok=True)
    
    # 1. 扫描分类下的全部页面名称
    pages = get_category_pages(category, limit=limit)
    if not pages:
        print(f"分类 【{category}】 下未找到符合要求的普通条目")
        return []
        
    print(f"分类 【{category}】 共搜集到 {len(pages)} 个页面，开始获取它们的最新时间戳...")
    
    # 2. 分批获取它们的最新更新时间戳（单次 API 限制 50 个 titles）
    page_titles = [p["title"] for p in pages]
    api_timestamps = {}
    
    chunk_size = 50
    for i in range(0, len(page_titles), chunk_size):
        chunk = page_titles[i:i+chunk_size]
        timestamps = get_pages_timestamps(chunk)
        api_timestamps.update(timestamps)
        
    # 3. 对比 state 中的记录，筛选出需要实际下载/更新的页面
    download_tasks = []
    for title in page_titles:
        net_ts = api_timestamps.get(title)
        if not net_ts:
            continue
            
        state_key = f"{category}/{title}"
        local_ts = state.get(state_key)
        
        # 判断本地文件是否真实物理存在
        clean_title = clean_filename(title)
        filepath = os.path.join(cat_dir, f"{clean_title}.txt")
        file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
        
        # 本地不存在，或者本地存储的时间戳与网络上不一致/较旧，则安排下载更新
        if not file_exists or local_ts != net_ts:
            download_tasks.append({
                "title": title,
                "cat_dir": cat_dir,
                "timestamp": net_ts,
                "state_key": state_key
            })
            
    print(f"分类 【{category}】 比对完毕：共需下载/更新 {len(download_tasks)}/{len(pages)} 个页面。")
    return download_tasks

def main():
    parser = argparse.ArgumentParser(description="星穹铁道 BWiki 数据智能同步脚本")
    parser.add_argument("--test", action="store_true", help="启用测试模式，每个分类仅爬取前10个页面")
    args = parser.parse_args()
    
    start_time = time.time()
    
    # 1. 载入配置文件中的指定分类列表
    if not os.path.exists(CONFIG_PATH):
        print(f"找不到配置文件: {CONFIG_PATH}")
        return
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    categories = config.get("wiki", {}).get("categories", [])
    print(f"载入的目标分类: {categories}")
        
    # 2. 加载本地状态文件 state.json
    state = load_state()
    
    # 3. 保证 wiki 目录下只有指定的分类文件夹，清除多余的文件夹与状态条目
    targeted_folders = {clean_filename(cat) for cat in categories}
    if os.path.exists(WIKI_DIR):
        for entry in os.listdir(WIKI_DIR):
            entry_path = os.path.join(WIKI_DIR, entry)
            # 过滤掉 state.json 自身
            if os.path.isdir(entry_path):
                if entry not in targeted_folders:
                    print(f"检测到非授权分类目录 【{entry}】，正在物理删除...")
                    try:
                        shutil.rmtree(entry_path)
                    except Exception as e:
                        print(f"删除目录失败: {e}")
                        
        # 物理清理 state 中不属于当前目标分类的键值
        keys_to_delete = []
        for key in state.keys():
            # key 格式为 "分类名/条目名"
            parts = key.split("/")
            if parts and parts[0] not in categories:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del state[key]
            
    # 4. 获取与比对：第一阶段
    limit = 10 if args.test else None
    print(f"\n开始第一阶段：扫描页面并比对更新时间戳... {'(测试模式)' if args.test else '(全量同步模式)'}")
    
    all_download_tasks = []
    # 这里扫描也使用并发，加速完成
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_category, cat, state, limit): cat for cat in categories}
        for future in as_completed(futures):
            cat = futures[future]
            try:
                tasks = future.result()
                if tasks:
                    all_download_tasks.extend(tasks)
            except Exception as e:
                print(f"处理分类 【{cat}】 发生异常: {e}")
                
    print(f"\n第一阶段完成！本次共需执行下载/更新的任务数: {len(all_download_tasks)} 个。")
    if not all_download_tasks:
        print("所有页面已是最新状态，无需下载。同步完成！")
        # 即使无事可做，也更新保存一次状态以确保没问题
        save_state(state)
        return
        
    # 5. 下载：第二阶段
    print("开始第二阶段：并发拉取更新页面内容...")
    success_count = 0
    
    # 使用线程池并发抓取与状态回填
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for task in all_download_tasks:
            future = executor.submit(fetch_and_save_page, task["title"], task["cat_dir"], task["timestamp"], task["state_key"])
            futures[future] = task
            
        for idx, future in enumerate(as_completed(futures)):
            task = futures[future]
            try:
                if future.result():
                    success_count += 1
                    # 写入成功，将最新时间戳存入 state
                    state[task["state_key"]] = task["timestamp"]
                else:
                    print(f"页面 【{task['title']}】 同步失败")
            except Exception as e:
                print(f"处理页面 【{task['title']}】 出现异常: {e}")
                
            if (idx + 1) % 50 == 0 or (idx + 1) == len(all_download_tasks):
                print(f"进度: 已处理 {idx + 1}/{len(all_download_tasks)} ...")
                
    # 6. 保存最终同步成功的状态
    save_state(state)
    
    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\n同步全部完成！")
    print(f"总计成功同步并写入: {success_count}/{len(all_download_tasks)} 个页面。")
    print(f"总耗时: {elapsed:.2f} 秒。")

if __name__ == "__main__":
    main()
