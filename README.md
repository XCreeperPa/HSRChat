# HSRChat - 星穹铁道专属剧情与设定 Skill

HSRChat 是一个基于 **Agent Skills** 开放规范构建的《崩坏：星穹铁道》（Honkai: Star Rail）世界观剧情设定技能包。它旨在为 AI 智能体（Agent）提供一套权威、纯净的官方参考语料，使其能够深度交流崩铁的世界观、主支线剧情以及角色背景故事。

此 Skill 采用**渐进式披露（On-demand Activation）**设计。在交互时，仅在用户提起“星穹铁道”、“崩铁”或相关角色设定时才被激活，将对应的语料引入到 Agent 上下文中以提供事实性背景支撑。

---

## 目录结构

```text
D:\HSRChat\
├── SKILL.md             # Skill 核心声明文件（定义触发词与核心行为指南）
├── config.json          # 统一的全局配置文件（合并了 Wiki 与 B站的分类配置）
├── config_secrets.json  # (安全隔离/已忽略) 本地 B站 敏感凭证配置文件
├── README.md            # 项目说明文档（本文件）
├── references/
│   ├── docs/
│   │   ├── devops.md              # 开发运维指南与 Git 版本控制规范
│   │   ├── data_sources.md        # 统一数据源同步与运维指南
│   │   ├── source_wiki.md         # Wiki 文本信源设计与接口逻辑
│   │   ├── source_bilibili.md     # B站官方视频元数据信源设计
│   │   └── source_bwiki_images.md # BWiki 图片多模态信源设计与同步记录
│   ├── bwiki_images/    # BWiki 图片索引、估算报告与压缩索引；图片缓存不入 Git
│   ├── bilibili/        # 120+ 篇官方视频元数据 JSON 分类存放处
│   └── wiki/            # 1,440 篇官方 Wiki 语料分类存放处
│       ├── 开拓任务/
│       ├── 开拓续闻/
│       ├── 同行任务/
│       ├── 冒险任务/
│       ├── 书籍/
│       ├── 角色语音/
│       ├── 角色/
│       ├── 游戏内容考据/
│       └── NPC/
└── scripts/
    ├── list_wiki_categories.py      # 脚本 1：命令行输出 BWiki 全部分类
    ├── sync_wiki.py                 # 脚本 2：基于状态文件的 Wiki 文本同步爬虫
    ├── sync_bilibili.py             # 脚本 3：基于 WBI 签名的 B站官方视频元数据同步爬虫
    ├── test_bwiki_image_download.py # 脚本 4：BWiki 图片小样本下载测试
    ├── sync_bwiki_images.py         # 脚本 5：BWiki 高价值图片估算与下载
    ├── compress_bwiki_images.py     # 脚本 6：BWiki 图片 WebP 派生压缩
    └── run_bwiki_image_pipeline.py  # 脚本 7：BWiki 图片全量流水线
```

---

## 安装与获取方法

### 1. 通用 Agent / 知识库克隆
如果你需要在自定义的 AI 智能体或 RAG 本地知识库中使用本数据库，可以直接克隆本仓库：
```bash
git clone https://github.com/XCreeperPa/HSRChat.git
```
克隆完成后，将 `references/wiki/` 以及 `references/bilibili/` 目录挂载到你的向量数据库或 Agent 检索路径即可。

### 2. 通过 CLI 工具直接安装
对于支持 Agent Skill 动态安装的 CLI 交互式会话，可以直接通过远程 URL 安装：
* **全局安装（所有会话生效）**：
  ```bash
  gemini skills install https://github.com/XCreeperPa/HSRChat.git
  ```
* **项目本地安装（仅在当前项目生效）**：
  ```bash
  gemini skills install https://github.com/XCreeperPa/HSRChat.git --scope workspace
  ```

---

## 开发与爬虫脚本使用

项目内置了多个 Python 脚本，用于维护和更新本地语料库。文本同步脚本仅依赖 Python 标准库；图片压缩脚本依赖 Pillow。

### 1. 查询所有分类 (list_wiki_categories.py)
用于查询星穹铁道 BWiki 当前的全部页面分类，并将其输出到命令行终端：
```bash
python scripts/list_wiki_categories.py
```
*提示：该脚本不会写入或修改本地任何文件，结果完全通过控制台标准输出返回。*

### 2. Wiki 设定文本同步 (sync_wiki.py)
该脚本是多线程高并发爬虫（最大支持 8 并发），负责下载 Wiki 页面并将非指定分类的文件夹物理清除：
* **全量同步**（读取 `config.json` 中的 `wiki.categories` 分类）：
  ```bash
  python scripts/sync_wiki.py
  ```
* **测试同步**（每个分类仅同步前 10 个页面，加快测试与验证）：
  ```bash
  python scripts/sync_wiki.py --test
  ```
* **关于多余分类目录的自动清除**：
  在执行时，脚本会自动对比配置文件中的指定分类。如果 `references/wiki/` 目录下含有非指定分类的文件夹，爬虫会在运行时主动将其从本地物理删除，以保证语料库的纯净。
* **基于 `state.json` 的智能增量同步**：
  - 脚本将已下载条目的最新 API 时间戳记录在 `references/wiki/state.json` 中。
  - 在下载前，脚本会获取线上条目的最新修改时间，仅在线上版本新于本地记录时发起下载。若无更新则瞬间跳过，极大地节省流量并保障安全防风控。

### 3. B站官方视频元数据同步 (sync_bilibili.py)
该脚本负责根据 `config.json` 中的 `bilibili` 配置，抓取并输出官方的视频元数据为结构化的 JSON 文件：
* **关于敏感凭证隔离 (config_secrets.json)**：
  如果需要以高限频额度或在登录态下运行（例如抓取私有或动态去敏感的空间合集），请在项目根目录下建立 `config_secrets.json`，并写入您的 Cookie 凭证。该文件已被 `.gitignore` 排除在外，绝不会被意外上传：
  ```json
  {
    "sessdata": "您的 SESSDATA Cookie 值"
  }
  ```
* **全量增量同步**（自动比对本地已存在的 JSON 文件进行增量拉取）：
  ```bash
  python scripts/sync_bilibili.py
  ```
* **测试同步**（每个分类仅同步前 3 个视频的元数据，快速验证）：
  ```bash
  python scripts/sync_bilibili.py --test
  ```
* **数据落盘与去重**：
  视频元数据以标准 JSON 格式保存在 `references/bilibili/{分类名称}/` 下。文件名使用去除了“《崩坏：星穹铁道》”前缀的游戏名后的干净视频标题（如 `千星纪游PV：「永火一夜：第33场」.json`）。

### 4. BWiki 图片多模态信源
图片流水线从已同步的 BWiki 文本和角色页命名规则中识别高价值图片，先估算体积，再按阈值下载原图缓存，并生成面向 Agent 的轻量 WebP 参考图：
* **一键全量模式**：
  ```bash
  python scripts/run_bwiki_image_pipeline.py --clean
  ```
  该模式会重新生成 `estimate_report.json`、`index.json`、`compressed_index.json`，并重建 `assets/` 原图缓存与 `assets_webp/` 压缩缓存。脚本会按本机 CPU 与网络能力启用并发，单个图片失败会记录在索引中并继续处理后续图片。
* **估算模式**：
  ```bash
  python scripts/sync_bwiki_images.py
  ```
  该模式只生成 `references/bwiki_images/estimate_report.json`，不会下载图片。
* **下载模式**：
  ```bash
  python scripts/sync_bwiki_images.py --download
  ```
  下载前会执行同一套估算流程。默认总量阈值为 1 GiB，超过即中止，避免意外拉取过大的图片库。可用 `--workers` 调整并发。
* **压缩模式**：
  ```bash
  python scripts/compress_bwiki_images.py --overwrite
  ```
  根据图片类别生成 WebP 副本：角色立绘默认最长边 1600、剧情 CG 默认最长边 1920，书籍/短信/线索图默认不降尺寸。压缩索引写入 `references/bwiki_images/compressed_index.json`。
* **版本控制边界**：
  `references/bwiki_images/index.json`、`estimate_report.json` 与 `compressed_index.json` 是可提交的文本索引；`references/bwiki_images/assets/` 与 `assets_webp/` 是本地图片缓存，已被 `.gitignore` 排除。
* **角色立绘**：
  角色页立绘由 BWiki 模板渲染，不一定出现在本地 wikitext 中。脚本会根据角色名推断主立绘 `角色名立绘.png`，并通过 MediaWiki `imageinfo` 解析原图地址；`立绘2`、`立绘3` 等后缀变体默认不再同步，以控制图片缓存体积。

---

## 数据安全与版本控制方案 (防篡改/防空回滚)

本项目采用**单 Git 仓库管理模式**，将所有的同步状态和 Wiki 文本全部纳入根目录 Git 中管理。在运行爬虫更新数据时，请严格遵守以下三步安全工作流（详见 `references/docs/data_sources.md` 与 `references/docs/devops.md`）：

1. **同步前检查**：运行 `git status` 确保工作区干净。
2. **执行同步**：运行 `python scripts/sync_wiki.py`、`python scripts/sync_bilibili.py` 或 `python scripts/run_bwiki_image_pipeline.py --clean` 获取最新数据与图片缓存。
3. **数据审核与操作**：
   - 运行 `git diff` 检查修改。
   - **安全回滚**：运行以下指令放弃本次同步结果，完全恢复到同步前的安全状态：
     ```bash
     git restore references/wiki/
     git restore references/bilibili/
     git restore references/wiki/state.json
     ```
     *(注：必须将 state.json 与数据一同回滚，以使同步历史与物理数据对齐，避免状态错乱。)*
   - **确认无误后提交**：如果数据均无损坏，执行 `git commit -a -m "data: 同步星铁最新数据"` 归档。

---

## 核心过滤原则

1. **数据中含有杂质**：因为 BWiki 的原始 Wikitext 中难免会含有角色的战斗属性、升级材料、周本材料或副本解锁引导。
2. **免除物理清洗**：项目不开发专门的清洗逻辑，以保留最完整的上下文背景。
3. **运行时过滤**：在 `SKILL.md` 中已经配置了指令约束。Agent 在激活本 Skill 并读取 `references/wiki/` 的语料数据时，会自动在运行时过滤掉一切关于“数值、配队、战斗、升级材料、光锥遗器推荐”的内容，确保回答完全聚焦于世界观、角色和剧情。
