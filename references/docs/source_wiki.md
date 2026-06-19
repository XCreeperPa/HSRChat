# BWiki 数据源开发逻辑与运维设计

`references/wiki/` 目录中存储了 1,400+ 篇来自 Bilibili 星穹铁道游戏 Wiki（BWiki）的设定文本，以原生的 Wikitext 格式（带 MediaWiki 标记语法）保存。本文档阐述该数据源的核心开发逻辑、网络请求机制以及增量同步算法。

---

## 1. 数据落盘结构

本地 Wiki 设定文本严格按照 `config.json` 中 `wiki.categories` 定义的分类列表进行分级物理建档：

```text
references/wiki/
├── state.json              # 核心增量同步状态文件
├── 开拓任务/
│   ├── 一杯尘埃的答复.txt
│   └── ...
├── 书籍/
├── 角色/
└── ...
```

---

## 2. 核心开发逻辑与 API 请求机制

在 `scripts/wiki/sync_wiki.py` 中，所有逻辑均基于 Python 3 标准库（`urllib`）实现，并使用 MediaWiki API 进行高并发（8 线程）多路抓取。

### 2.1 MediaWiki API 请求流

1.  **查询分类下所有条目名称 (Query Categorymembers)**：
    *   **接口**：`https://wiki.biligame.com/sr/api.php`
    *   **方法**：`GET`
    *   **核心参数**：
        ```python
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category_name}",
            "cmlimit": "500", # 单次最大分页上限
            "format": "json"
        }
        ```
    *   **分页机制**：通过返回数据中的 `continue.cmcontinue` 作为下一次请求的 `cmcontinue` 参数实现指针翻页。
2.  **批量拉取页面最后更新时间戳 (Query Revisions Timestamp)**：
    *   **核心参数**：
        ```python
        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "timestamp",
            "titles": "|".join(titles), # MediaWiki 允许单次用 | 拼接最大 50 个标题批量拉取
            "format": "json"
        }
        ```
3.  **下载单个条目的 Wikitext 设定内容**：
    *   **核心参数**：
        ```python
        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "titles": title,
            "format": "json"
        }
        ```

---

## 3. 智能增量与目录裁剪算法

为了避免网络流量浪费并保证同步历史的高度一致，系统基于 `state.json` 状态控制机制，并实现**单向覆盖**：

```
[开始同步分类]
      │
      ▼
批量获取线上条目的最新修改时间戳 net_ts
      │
      ▼
读取本地 state.json 对应条目的记录 local_ts
      │
      ├─────────────────── local_ts == net_ts 且文件物理存在 ?
      │                                 │
     (否)                              (是)
      │                                 │
      ▼                                 ▼
并发下发 fetch 详情任务              瞬间跳过下载 (Skip)
      │
      ▼
写入成功 ──> 更新 state[key] = net_ts
```

### 3.1 状态文件 (`state.json`) 映射设计
其数据结构为 `"{分类}/{条目标题}": "{最后修改时间戳}"`。例如：
```json
{
  "开拓任务/一杯尘埃的答复": "2024-03-27T08:12:35Z"
}
```

### 3.2 多余分类的自动物理裁剪逻辑
为了保持与配置文件的绝对对齐，程序在主流程中提供自动清理逻辑：
1.  **扫描**：遍历 `references/wiki/` 目录下的所有子文件夹。
2.  **判断**：将检测到的子目录名称与配置文件的 `wiki.categories` 列表对比（对文件名中特殊字符进行 Windows 兼容性过滤后判定）。
3.  **物理删除**：若本地包含非指定分类文件夹，调用 `shutil.rmtree()` 强制物理清除，同时将 `state.json` 中以该分类名开头的所有键值记录一并注销。这能确保用户通过只更改 `config.json` 即可完成库的轻量级裁剪。

---

## 4. 网络异常自愈设计 (指数退避重试)

因为 BWiki 启用了高强度的 EdgeOne (WAF) 防爬墙，并发拉取容易被防火墙拦截返回非 JSON 内容（如 403 页面）。
脚本实现了一个带有**随机化指数退避 (Exponential Backoff with Jitter)**的 API 请求包装函数：
```python
for attempt in range(4):
    try:
        # 发送请求与解析 JSON
        ...
    except (json.JSONDecodeError, HTTPError):
        # 产生报错后，根据当前重试轮数计算等待时间并随机扰动：
        wait_time = (attempt + 1) * random.uniform(3.0, 6.0)
        time.sleep(wait_time)
```
这能极大提高长距离高并发网络同步的生存率与成功率。
