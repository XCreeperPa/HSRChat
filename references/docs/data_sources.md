# HSRChat 统一信源同步与运维指南

HSRChat Skill 包的数据驱动体系由三个官方/权威信息信源共同支撑，涵盖了星穹铁道的深度世界观、主支线剧情文本、角色背景故事、官方视频考据数据以及 BWiki 页面附带的高价值视觉资料。本指南提供多信源更新的统一流程、配置管理以及日常同步运维方案。

---

## 1. 统一配置管理 (config.json)

为了降低运维复杂度，项目使用单一的配置文件 `config.json` 来集中管理文本与视频信源的目标更新分类：

```json
{
  "wiki": {
    "categories": [
      "开拓任务",
      "开拓续闻",
      "同行任务",
      "冒险任务",
      "书籍",
      "角色语音",
      "角色",
      "游戏内容考据",
      "NPC"
    ]
  },
  "bilibili": {
    "mid": 1340190821,
    "categories": [
      {
        "name": "角色预告",
        "type": "season",
        "id": 7074641
      },
      {
        "name": "角色PV",
        "type": "series",
        "id": 3236610
      },
      {
        "name": "动画短片",
        "type": "series",
        "id": 3581990
      },
      {
        "name": "千星纪游",
        "type": "series",
        "id": 3431689
      },
      {
        "name": "即兴巡演PV",
        "type": "series",
        "id": 5078098
      },
      {
        "name": "EP",
        "type": "series",
        "id": 3236620
      },
      {
        "name": "黄金史诗PV",
        "type": "series",
        "id": 4494993
      }
    ]
  }
}
```

*   **`wiki.categories`**：配置了 BWiki 需要拉取的分类名列表（本地以 `.txt` wikitext 存放于 `references/wiki/` 中）。
*   **`bilibili.mid`**：指定爬取官方 B 站账号的 MID（星铁官方 MID 为 `1340190821`）。
*   **`bilibili.categories`**：定义了需要同步的合集与系列名称、拉取类型（`season` 或 `series`）及合集系列 ID（本地以 `.json` 格式存放于 `references/bilibili/` 中）。
*   **BWiki 图片信源**：当前由 `scripts/sync_bwiki_images.py` 基于现有 `references/wiki/` 与角色页命名规则派生，不在 `config.json` 中默认启用，避免常规同步时意外下载大体积图片。

---

## 2. 脚本命名与功能一览

所有维护和同步脚本存放在 `scripts/` 目录下：

| 脚本名称 | 对应信源 | 核心功能描述 |
| :--- | :--- | :--- |
| `list_wiki_categories.py` | 崩铁 BWiki | 实时向终端输出 BWiki 当前所有的活跃页面分类名称。 |
| `sync_wiki.py` | 崩铁 BWiki | 获取并增量同步 Wiki 指定分类下的所有设定文本，自动清理过期目录。 |
| `sync_bilibili.py` | B站官方视频 | 增量下载官方视频元数据并以 JSON 格式落盘，自动进行敏感凭证隔离。 |
| `test_bwiki_image_download.py` | BWiki 图片 | 小样本下载测试脚本，用于验证不同图片引用类型的解析、下载与文件头校验。 |
| `sync_bwiki_images.py` | BWiki 图片 | 识别高价值图片、解析 MediaWiki `imageinfo`、估算总体积，并在 1 GiB 默认阈值内下载图片缓存。 |

---

## 3. 统一同步运维工作流

为防止拉取到坏数据污染本地语料，运维数据同步时必须遵循以下三步工作流：

### 第一步：检查工作区状态
每次更新数据前，先确保工作区干净，且敏感配置文件已正确排除：
```bash
git status
```
*确认不存在未添加至 `.gitignore` 的敏感配置文件 `config_secrets.json`*。

### 第二步：按需执行同步
根据数据更新需要，选择执行单信源或多信源同步：
```bash
# 1. 同步 BWiki 数据
python scripts/sync_wiki.py

# 2. 同步 B站视频数据
python scripts/sync_bilibili.py

# 3. 估算 BWiki 高价值图片体积，不下载
python scripts/sync_bwiki_images.py

# 4. 在估算不超过 1 GiB 时下载 BWiki 高价值图片
python scripts/sync_bwiki_images.py --download
```
*提示：可为 Wiki 与 B站同步命令附加 `--test` 标志进行高速连通性检测（Wiki 限制单分类爬取 10 页，B站限制单分类爬取 3 页）。图片信源可先运行 `test_bwiki_image_download.py` 做多类型小样本验证。*

### 第三步：合规性审计与提交/回滚
*   **安全审计**：运行 `git diff` 检查下载文件的改动，确保没有因为限频或服务器异常导致文件内容变为空或损坏。
*   **图片边界**：`references/bwiki_images/index.json`、`estimate_report.json`、`compressed_index.json` 与 `references/bwiki_images/assets_webp/` 可以纳入版本控制；`references/bwiki_images/assets/` 是本地原图缓存，必须保持在 `.gitignore` 中，严禁提交。项目固定规则是：图片二进制只提交 WebP，不提交原图缓存。
*   **一键回滚（若发现异常）**：
    ```bash
    git restore references/wiki/
    git restore references/bilibili/
    git restore references/wiki/state.json
    git restore references/bwiki_images/index.json
    git restore references/bwiki_images/estimate_report.json
    ```
*   **确认无误后提交**：
    ```bash
    git add . ':!references/bwiki_images/assets/'
    git commit -m "data: 同步星铁最新 Wiki 与 B站视频设定数据"
    ```
