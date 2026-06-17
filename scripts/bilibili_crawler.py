import os
import json
import urllib.request
import urllib.parse
import time
import re
import hmac
import hashlib
import http.cookiejar
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

CONFIG_PATH = "config_bilibili.json"
SECRETS_PATH = "config_secrets.json"
OUTPUT_DIR = os.path.join("D:", os.sep, "HSRChat", "references", "bilibili")
MAX_WORKERS = 4

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com"
}

MIXIN_TABLE = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 52, 44
]

# 启用全局 Cookie 自动管理器
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
urllib.request.install_opener(opener)

def load_secrets_into_cookiejar():
    """从独立的安全配置文件中载入凭证并注入到全局 CookieJar"""
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                secrets = json.load(f)
                sessdata = secrets.get("sessdata")
                if sessdata:
                    cookie = http.cookiejar.Cookie(
                        version=0, name='SESSDATA', value=sessdata,
                        port=None, port_specified=False,
                        domain='.bilibili.com', domain_specified=True, domain_initial_dot=True,
                        path='/', path_specified=True,
                        secure=True, expires=None, discard=True, comment=None, comment_url=None, rest={}, rfc2109=False
                    )
                    cj.set_cookie(cookie)
                    print("[安全配置] 成功将 SESSDATA 注入全局 Cookie 凭证管理器中")
        except Exception as e:
            print(f"[安全配置] 读取安全配置文件 {SECRETS_PATH} 异常: {e}")

def init_cookies():
    """初始化 B 站设备指纹 Cookie"""
    print("[初始化] 正在访问 Bilibili 主页获取访客 Cookie 指纹...")
    try:
        req = urllib.request.Request("https://www.bilibili.com", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        print("[初始化] 访客 Cookie 状态初始化完成")
    except Exception as e:
        print(f"[警告] 初始化 Cookie 失败: {e}")

def hmac_sha256(key: str, message: str) -> str:
    key_bytes = key.encode('utf-8')
    message_bytes = message.encode('utf-8')
    return hmac.new(key_bytes, message_bytes, hashlib.sha256).digest().hex()

def get_mixin_key(img_key, sub_key):
    raw_key = img_key + sub_key
    return "".join([raw_key[i] for i in MIXIN_TABLE])[:32]

def get_wbi_keys_and_ticket():
    """使用 GenWebTicket 安全地申请 WBI 密钥与 bili_ticket"""
    print("[安全鉴权] 正在向 Bilibili 申请 WBI 签名密钥和 Ticket...")
    try:
        timestamp = int(time.time())
        hexsign = hmac_sha256("XgwSnGZ1p", f"ts{timestamp}")
        url = f"https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket?key_id=ec02&hexsign={hexsign}&context[ts]={timestamp}&csrf="
        req = urllib.request.Request(url, method="POST", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            if res_json.get("code") == 0:
                ticket = res_json["data"]["ticket"]
                nav_data = res_json["data"]["nav"]
                img_url = nav_data["img"]
                sub_url = nav_data["sub"]
                img_key = img_url.rsplit('/', 1)[-1].split('.')[0]
                sub_key = sub_url.rsplit('/', 1)[-1].split('.')[0]
                print("[安全鉴权] 成功换取 WBI 密钥")
                return img_key, sub_key, ticket
            else:
                print(f"[警告] GenWebTicket 接口返回错误: {res_json}")
    except Exception as e:
        print(f"[警告] 通过 Ticket 接口获取 WBI 密钥发生异常: {e}")
    return None, None, None

def sign_wbi(params: dict, img_key: str, sub_key: str) -> dict:
    mixin_key = get_mixin_key(img_key, sub_key)
    params["wts"] = int(time.time())
    sorted_params = dict(sorted(params.items()))
    clean_params = {
        k: "".join(c for c in str(v) if c not in "!'()*")
        for k, v in sorted_params.items()
    }
    query = urllib.parse.urlencode(clean_params)
    params["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return params

def fetch_ids_dynamically(mid, img_key, sub_key, ticket):
    """尝试动态扫描 UP 主的合集/系列总表以寻找 ID"""
    if not img_key or not ticket:
        return {}
    
    print("[动态扫描] 尝试动态获取合集与系列名称映射...")
    params = {"mid": mid, "page_num": 1, "page_size": 20}
    signed_params = sign_wbi(params, img_key, sub_key)
    url_params = urllib.parse.urlencode(signed_params)
    url = f"https://api.bilibili.com/x/polymer/web-space/seasons_series_list?{url_params}"
    
    # 构建包含 bili_ticket 的 Cookie
    cookies = {cookie.name: cookie.value for cookie in cj}
    cookies["bili_ticket"] = ticket
    cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    
    req_headers = {
        **HEADERS,
        "Cookie": cookie_header,
        "Referer": f"https://space.bilibili.com/{mid}/channel/series"
    }
    
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("code") == 0:
                lists = data.get("data", {}).get("items_lists", {})
                seasons = lists.get("seasons_list") or []
                series = lists.get("series_list") or []
                
                id_map = {}
                for s in seasons:
                    meta = s.get("meta", {})
                    name = meta.get("name")
                    sid = meta.get("season_id")
                    if name and sid:
                        id_map[name] = {"type": "season", "id": sid}
                for s in series:
                    meta = s.get("meta", {})
                    name = meta.get("name")
                    sid = meta.get("series_id")
                    if name and sid:
                        id_map[name] = {"type": "series", "id": sid}
                return id_map
    except Exception as e:
        print(f"[警告] 动态查询合集系列列表接口异常: {e}")
    return {}

def fetch_season_videos(mid, season_id):
    """根据合集 ID 分页拉取所有视频的 BVID 列表"""
    bvid_list = []
    page = 1
    while True:
        url = f"https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?mid={mid}&season_id={season_id}&sort_reverse=false&page_num={page}&page_size=30"
        req_headers = {
            **HEADERS,
            "Referer": f"https://space.bilibili.com/{mid}/channel/collectiondetail?sid={season_id}"
        }
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get("code") != 0:
                    print(f"  [获取失败] 合集 {season_id} 第 {page} 页: {data.get('message')}")
                    break
                
                archives = data.get("data", {}).get("archives") or []
                for arc in archives:
                    bvid = arc.get("bvid")
                    if bvid:
                        bvid_list.append(bvid)
                        
                page_info = data.get("data", {}).get("page", {})
                total = page_info.get("total", 0)
                if page * 30 >= total or not archives:
                    break
                page += 1
                time.sleep(0.5)
        except Exception as e:
            print(f"  [异常] 抓取合集 {season_id} 视频列表时出错: {e}")
            break
    return bvid_list

def fetch_series_videos(mid, series_id):
    """根据系列 ID 分页拉取所有视频的 BVID 列表"""
    bvid_list = []
    page = 1
    while True:
        url = f"https://api.bilibili.com/x/series/archives?mid={mid}&series_id={series_id}&only_normal=true&sort=desc&pn={page}&ps=30"
        req_headers = {
            **HEADERS,
            "Referer": f"https://space.bilibili.com/{mid}/channel/seriesdetail?sid={series_id}"
        }
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get("code") != 0:
                    print(f"  [获取失败] 系列 {series_id} 第 {page} 页: {data.get('message')}")
                    break
                
                archives = data.get("data", {}).get("archives") or []
                for arc in archives:
                    bvid = arc.get("bvid")
                    if bvid:
                        bvid_list.append(bvid)
                        
                page_info = data.get("data", {}).get("page", {})
                total = page_info.get("total", 0)
                if page * 30 >= total or not archives:
                    break
                page += 1
                time.sleep(0.5)
        except Exception as e:
            print(f"  [异常] 抓取系列 {series_id} 视频列表时出错: {e}")
            break
    return bvid_list

def clean_filename(name):
    """清理文件名中 Windows 不支持的字符"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def fetch_and_save_video(bvid, cat_name, cat_dir):
    """请求单个视频详情并写入 JSON 文件"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("code") != 0:
                print(f"    [详情错误] 视频 {bvid} 详情获取失败: {data.get('message')}")
                return False
            
            view_data = data.get("data", {})
            title = view_data.get("title", "")
            if not title:
                return False
            
            pubdate = view_data.get("pubdate", 0)
            pub_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(pubdate))
            
            stat = view_data.get("stat", {})
            view_count = stat.get("view", 0)
            like_count = stat.get("like", 0)
            desc = view_data.get("desc", "")
            
            # 整理为 JSON 数据结构
            video_json = {
                "bvid": bvid,
                "title": title,
                "url": f"https://www.bilibili.com/video/{bvid}",
                "pubdate": pub_time_str,
                "category": cat_name,
                "views": view_count,
                "likes": like_count,
                "description": desc
            }
            
            # 彻底去除视频标题前缀中的游戏名“《崩坏：星穹铁道》”或“崩坏：星穹铁道”
            base_name = re.sub(r'^《?崩坏[:：]星穹铁道》?\s*', '', title)
            filename = clean_filename(base_name)
                
            filepath = os.path.join(cat_dir, f"{filename}.json")
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(video_json, f, ensure_ascii=False, indent=2)
            return True
    except Exception as e:
        print(f"    [详情异常] 请求视频 {bvid} 详情时异常: {e}")
    return False

def process_category(cat, mid, dynamic_id_map, is_test):
    cat_name = cat["name"]
    cat_type = cat["type"]
    cat_id = cat.get("id")
    
    # 动态匹配兜底
    if cat_id is None:
        dynamic_info = dynamic_id_map.get(cat_name)
        if dynamic_info:
            cat_id = dynamic_info["id"]
            print(f"\n分类 【{cat_name}】 动态匹配到 ID: {cat_id}")
        else:
            print(f"\n[提示] 分类 【{cat_name}】 未静态配置 ID 且动态匹配失败。")
            print(f"       请打开 B站 空间在登录状态下复制其分类 ID 填入 {CONFIG_PATH} 的 id 字段中。")
            return 0
            
    cat_dir = os.path.join(OUTPUT_DIR, cat_name)
    os.makedirs(cat_dir, exist_ok=True)
    
    print(f"\n开始抓取分类 【{cat_name}】 (类型: {cat_type}, ID: {cat_id})...")
    if cat_type == "season":
        bvid_list = fetch_season_videos(mid, cat_id)
    else:
        bvid_list = fetch_series_videos(mid, cat_id)
        
    if not bvid_list:
        print(f"分类 【{cat_name}】 未拉取到视频列表。")
        return 0
        
    print(f"分类 【{cat_name}】 线上总共包含 {len(bvid_list)} 个视频。开始执行增量检测...")
    
    # 本地增量扫描以规避重复请求
    local_bvids = set()
    for fn in os.listdir(cat_dir):
        if fn.endswith(".json"):
            filepath = os.path.join(cat_dir, fn)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    v_data = json.load(f)
                    bvid = v_data.get("bvid")
                    if bvid:
                        local_bvids.add(bvid)
            except Exception:
                pass
                
    to_download = [b for b in bvid_list if b not in local_bvids]
    
    # 测试模式限制
    if is_test:
        to_download = to_download[:3]
        print(f"  [测试模式] 限制本次抓取最多 3 个视频")
        
    print(f"分类 【{cat_name}】 比对完毕：本地已存在 {len(local_bvids)} 个视频，本次需增量同步 {len(to_download)} 个视频。")
    if not to_download:
        print(f"分类 【{cat_name}】 已经是最新状态，无需同步。")
        return 0
        
    # 并发同步详情并写入 JSON
    success_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_and_save_video, bvid, cat_name, cat_dir): bvid for bvid in to_download}
        for idx, future in enumerate(as_completed(futures)):
            bvid = futures[future]
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                print(f"    [任务异常] 视频 {bvid} 同步失败: {e}")
            
            # 微小休眠防止频控
            time.sleep(0.3)
            if (idx + 1) % 10 == 0 or (idx + 1) == len(to_download):
                print(f"  进度: 已处理 {idx + 1}/{len(to_download)} ...")
                
    print(f"分类 【{cat_name}】 同步完成！成功写入 {success_count} 个页面。")
    return success_count

def main():
    parser = argparse.ArgumentParser(description="星穹铁道 B站官方视频元数据智能同步爬虫")
    parser.add_argument("--test", action="store_true", help="启用测试模式，每个分类仅同步最多3个视频详情")
    args = parser.parse_args()
    
    start_time = time.time()
    
    # 载入配置
    if not os.path.exists(CONFIG_PATH):
        print(f"找不到 B站 配置文件: {CONFIG_PATH}")
        return
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    mid = config.get("mid", 1749127287)
    categories = config.get("categories", [])
    print(f"载入目标 UP 主 (MID: {mid})，包含 {len(categories)} 个指定分类。")
    
    # 初始化全局 Cookie
    init_cookies()
    # 载入独立文件中的 SESSDATA 敏感安全配置
    load_secrets_into_cookiejar()
    
    img_key, sub_key, ticket = get_wbi_keys_and_ticket()
    
    # 如果配置中包含 ID 为 null 的分类，则启动一次动态扫描获取 ID 作为 Fallback
    needs_dynamic = any(cat.get("id") is None for cat in categories)
    dynamic_id_map = {}
    if needs_dynamic:
        # 顺便把 ticket 塞入 cookiejar 以供动态扫描使用
        if ticket:
            t_cookie = http.cookiejar.Cookie(
                version=0, name='bili_ticket', value=ticket,
                port=None, port_specified=False,
                domain='.bilibili.com', domain_specified=True, domain_initial_dot=True,
                path='/', path_specified=True,
                secure=True, expires=None, discard=True, comment=None, comment_url=None, rest={}, rfc2109=False
            )
            cj.set_cookie(t_cookie)
        dynamic_id_map = fetch_ids_dynamically(mid, img_key, sub_key, ticket)
        
    total_sync_count = 0
    # 依次同步每个分类
    for cat in categories:
        try:
            sync_count = process_category(cat, mid, dynamic_id_map, args.test)
            total_sync_count += sync_count
        except Exception as e:
            print(f"处理分类 【{cat.get('name')}】 时发生严重异常: {e}")
            
    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\n[同步完毕] B站官方视频元数据增量同步完成！")
    print(f"           总计成功写入/更新: {total_sync_count} 个视频 JSON 页面。")
    print(f"           总耗时: {elapsed:.2f} 秒。")

if __name__ == "__main__":
    main()
