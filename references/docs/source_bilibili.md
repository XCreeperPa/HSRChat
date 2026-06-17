# B站官方视频数据源开发逻辑与签名机制设计

`references/bilibili/` 目录中存储了从 Bilibili 官方视频频道增量爬取的系列与合集视频设定元数据，以纯净的 `.json` 格式保存。本文档描述其核心开发逻辑、WBI 鉴权机制、敏感凭证隔离以及防重复拉取算法。

---

## 1. 数据落盘结构

本地视频元数据严格按照 `config.json` 中 `bilibili.categories` 定义的分类列表进行分级物理建档：

```text
references/bilibili/
├── 角色预告/
│   ├── 角色PV——「致命浪漫」.json
│   └── ...
├── 千星纪游/
│   ├── 千星纪游PV：「永火一夜：第33场」.json
│   └── ...
└── ...
```

保存的 JSON 元数据规范如下（Views 和 Likes 统一转化为 Python 整数存储，便于下游解析）：

```json
{
  "bvid": "视频BV号",
  "title": "视频标题原文",
  "url": "视频播放地址",
  "pubdate": "发布时间 (YYYY-MM-DD HH:mm:ss)",
  "category": "分类名称",
  "views": 6750157,
  "likes": 341323,
  "description": "视频简介文案原文 (换行符完整保留)"
}
```

---

## 2. WBI 安全鉴权与 bili_ticket 申请流

Bilibili 在 2023 年后对用户空间接口启用了强力的 WBI 动态风控和去登录化指纹。程序通过 **GenWebTicket 机制** 模拟无感鉴权，不依赖任何第三方解密库实现底层通讯：

### 2.1 申请 WBI 密钥与 bili_ticket 签名算法

1.  **GenWebTicket 调用**：
    *   **方法**：`POST`
    *   **接口**：`https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket`
    *   **参数签名**：使用 HMAC-SHA256 对 `ts{timestamp}` 进行签名，签名密钥硬编码为 `XgwSnGZ1p`（B站官方客户端校验秘钥）。
    *   **响应解析**：从返回中提取出访客临时凭证 `ticket`，以及 WBI 加密使用的 `img_url` 和 `sub_url` 链接。
2.  **Mixin Key 混合密钥计算**：
    *   提取 `img_url` 和 `sub_url` 文件名中的哈希字符串（分别为 `img_key` 和 `sub_key`）。
    *   将两者拼接，并根据固定的混淆偏移映射表 `MIXIN_TABLE` 进行重新排列组合，截取前 32 位生成该访客本次通信的独享 `mixin_key`。
3.  **WBI 签名 (w_rid)**：
    *   将要发起的 API 参数字典加入当前时间戳 `wts`，按键名升序排列。
    *   利用 `urlencode` 转换查询参数，剔除特殊保留字符 `!'()*`。
    *   拼接 `mixin_key` 后计算其 MD5 值，生成签名参数 `w_rid` 追加到请求中。

---

## 3. 本地增量比对算法 (免 state.json 物理扫描)

与 Wiki 依赖 `state.json` 状态库不同，B站同步程序采用更纯粹的**本地物理扫描归纳法**。因为每个视频落盘就是独立的 JSON，我们能够以极低的本地 I/O 成本直接重建状态：

```
[扫描本地分类子目录]
      │
      ▼
遍历所有 *.json 文件并加载
      │
      ▼
提取 json["bvid"] ────> 存入 local_bvids 集合 (Set)
      │
      ▼
拉取线上该合集/系列的全量 BVID 列表 online_bvids
      │
      ▼
对比差集：to_download = online_bvids - local_bvids
      │
      ▼
并发下发 fetch 详情任务并落盘 (对文件名剔除游戏前缀过滤)
```
该算法无需维护第三方的同步状态文件，对本地误删、重命名等物理变动有极强的抗干扰性和天然自愈性。

---

## 4. 敏感凭证隔离 (config_secrets.json)

*   **痛点**：B站部分敏感接口（如空间合集分类列表 `seasons_series_list`）在匿名状态下由于动态去敏感风控，可能经常返回 `total: 0`。
*   **策略**：
    *   建立本地隔离配置文件 `config_secrets.json`，存储您的 SESSDATA 凭证。
    *   该文件已配置到 `.gitignore` 中，确保秘钥仅保留在本地。
    *   在启动时，爬虫会尝试将 SESSDATA 转换并注入全局 `http.cookiejar.CookieJar`。在随后的所有 `urllib` 请求中，都会自动带有该安全 Cookie，避免了代码中硬编码秘钥导致泄密。

---

## 5. 文件名净化与去重机制

在同步视频落盘时，因为官方视频标题的前缀往往格式不一（如 `《崩坏：星穹铁道》千星纪游PV...` 或 `崩坏：星穹铁道 角色PV...`），容易产生 `《崩坏：星穹铁道》《崩坏：星穹铁道》` 这样的重影文件名。
程序设计了文件名净化逻辑：
```python
# 彻底去除视频标题前缀中的游戏名“《崩坏：星穹铁道》”或“崩坏：星穹铁道”以实现规范落盘
base_name = re.sub(r'^《?崩坏[:：]星穹铁道》?\s*', '', title)
filename = clean_filename(base_name)
```
这保证了生成的文件名永远像 `千星纪游PV：「永火一夜：第33场」.json` 这样精简，且在文件系统与向量化检索时拥有更直观的辨识度。
