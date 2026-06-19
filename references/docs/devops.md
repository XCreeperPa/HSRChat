# HSRChat DevOps & 持续优化指南

为了复刻、延续本项目的开发和运维思路，任何加载、修改或维护本 Skill 项目的 Agent 必须严格遵守并执行本指南中定义的研发准则。

---

## 1. 系统架构与设计准则

### 1.1 数据专注原则
* **唯一范围**：仅处理与《崩坏：星穹铁道》世界观（如星神、命途、派系、星系等）、主支线剧情、同行任务和角色设定相关的内容。
* **绝对禁忌**：严禁引入任何角色战斗数值、技能机制、光锥遗器配队、副本关卡打法等与战斗系统相关的干预信息。

### 1.2 动态机制过滤
* **现状**：从 BWiki 爬取的 wikitext 中难免夹杂如角色定位（“主C/辅助”）、升级材料或副本玩法引导等少量杂质。
* **策略**：**禁止开发物理清洗脚本**。我们已通过在 `SKILL.md` 中增加动态约束，使被激活的 Agent 在载入 `references/wiki/` 文本时能自行过滤掉这些战斗数值信息，从而确保参考数据库的原始与完整。

---

## 2. 爬虫工具与目录维护规约 (`scripts/`)

本 Skill 配备了多个 Python 脚本以自动化维护语料库：

### 2.1 查询所有分类 (`scripts/wiki/list_wiki_categories.py`)
* **设计要求**：该脚本用于列出 BWiki 目前的所有页面分类。它必须**仅往命令行控制台标准输出结果**，禁止写入或修改本地任何文件。

### 2.2 智能同步与多余目录物理清理 (`scripts/wiki/sync_wiki.py`)
该并发同步爬虫（最大 8 线程）负责下载数据，它必须实现以下核心机制：
1. **多余分类物理清理**：
   - 启动时扫描 `references/wiki/` 目录。
   - 如果发现有不包含在 `config.json` 指定列表中的分类文件夹，脚本必须**主动将其从本地物理删除**，同时清理 `state.json` 中相关时间戳记录。
2. **基于 `state.json` 的智能版本同步**：
   - 拒绝使用易出现时区误差的本地 mtime（修改时间），改为在 `references/wiki/state.json` 中记录已下载条目的最新 API 时间戳（`timestamp`）。
   - 在抓取前，批量获取线上条目的最新修改时间戳，并与 `state.json` 记录比对。仅在本地不存在该文件、或线上版本更新时，才发起下载网络请求。若无变化则直接跳过，节省流量，保障安全防封控。
3. **支持 `--test` 测试参数**：
   - 运行 `python scripts/wiki/sync_wiki.py --test` 时，必须将每个分类下下载的网页数量硬性限制在 10 个以内，用于高速验证连通性与重构逻辑。

### 2.3 B站官方视频元数据同步 (`scripts/bilibili/sync_bilibili.py`)
该并发增量同步爬虫负责拉取 UP 主指定合集和系列（定义在 `config.json` 的 `bilibili.categories`）的视频详情，它必须实现以下核心机制：
1. **防凭证泄漏（安全至上）**：
   - 绝不能将包含 `sessdata` / `Cookie` 等敏感鉴权信息的代码、变量或数据写入受版本控制的脚本中。
   - 使用机密凭证配置文件 `config_secrets.json` 作为本地独立存储。该文件必须被列在 `.gitignore` 规则内被完全忽略。
   - 脚本必须在启动时尝试动态读取该机密文件并装载 SESSDATA 凭证。
2. **基于本地扫描的智能增量同步**：
   - 遍历 `references/bilibili/{分类名称}` 下已存在的 JSON 文件。读取文件内容并提取其中的 `bvid`。
   - 将线上合集列表与本地已存在集合比对，仅对缺失的 `bvid` 发起详情 API 请求，杜绝重复调用，防止触发防爬风控。
3. **文件名去重清洗**：
   - 使用正则剥离视频标题中前导的 `《崩坏：星穹铁道》` 或 `崩坏：星穹铁道` 前缀（包括可能存在的多余空格或不同类型的冒号），以生成精炼的纯标题文件名。

### 2.4 BWiki 图片多模态信源同步与压缩
图片流水线由 `scripts/bwiki_images/run_bwiki_image_pipeline.py` 串联 `scripts/bwiki_images/sync_bwiki_images.py` 与 `scripts/bwiki_images/compress_bwiki_images.py`。它负责从已同步的 BWiki 文本与角色页命名规则中派生高价值图片索引，在体积预算内下载原图缓存，并生成面向 Agent 的 WebP 参考图。它必须实现以下核心机制：
1. **先估算后下载**：
   - 默认运行 `python scripts/bwiki_images/sync_bwiki_images.py` 只生成 `references/bwiki_images/estimate_report.json`。
   - 只有显式传入 `--download` 时才下载图片。
   - 默认总量阈值为 1 GiB，估算超过阈值时必须中止下载。
   - 全量重建可运行 `python scripts/bwiki_images/run_bwiki_image_pipeline.py --clean`。
2. **高价值筛选**：
   - 保留剧情 CG、书籍/任务大图、短信图片、角色立绘等与剧情、世界观、角色设定直接相关的图片。
   - 默认排除 `{{图标|...}}`、小尺寸 `[[file:...|64px]]` 图标、CSS 装饰图、元素/机制图标。
3. **角色立绘补全**：
   - 角色页立绘通常由 `{{角色图鉴}}` 等模板在渲染 HTML 中生成，不一定存在于本地 wikitext。
   - 脚本通过角色页 `|名称=` 推断主立绘 `角色名立绘.png`，并用 MediaWiki `imageinfo` 验证存在性。
   - `角色名立绘2.png`、`角色名立绘3.jpg/png` 等介绍立绘或卡片变体默认不再同步；若本地只有后缀版且没有主立绘，可作为例外保留。
   - 开拓者不同命途需额外推断 `开拓者星•{命途}` 与 `开拓者穹•{命途}` 形式。
4. **原图解析与去重**：
   - 必须通过 MediaWiki `imageinfo` 解析原图 URL、大小、MIME、宽高、sha1 与更新时间，禁止直接保存页面缩略图 URL。
   - 使用远端 sha1 合并同内容别名，避免 `.jpg` / `.png` 标题指向同一文件时重复下载。
5. **版本控制边界**：
   - `references/bwiki_images/index.json`、`estimate_report.json`、`compressed_index.json`、`references/bwiki_images/vision_index/assets/` 与 `references/bwiki_images/vision_index/assets.jsonl` 是可审计文本产物，可以提交。
   - `references/bwiki_images/assets_webp/` 是面向 Agent 的轻量 WebP 参考图，必须随图片索引一起提交。
   - `references/bwiki_images/assets/` 是本地原图缓存，必须由 `.gitignore` 排除，严禁纳入普通 Git。项目固定规则：**图片二进制只提交 WebP，不提交原图缓存**。
   - `references/bwiki_images/vision_jobs/` 是并发生成图片文本描述的临时任务区，不提交；`references/bwiki_images/vision_review/review_state.json` 是本地审核草稿，不提交。
6. **并发与错误处理**：
   - 估算和下载使用线程池，默认按本机能力选择并发数，可通过 `--workers` 或流水线脚本的 `--network-workers` 调整。
   - WebP 压缩使用进程池，默认使用本机 CPU 核心数，可通过 `--compress-workers` 调整。
   - 单个远端文件解析、下载或压缩失败时，脚本必须记录 `estimate_failed`、`download_failed` 或 `compress_failed`，并继续处理后续文件。
   - CLI 输出必须适配中文路径；在不支持 UTF-8 的 Windows 控制台中，应退化为 ASCII 转义输出，避免日志编码异常中断流水线。

---

### 3. Git 版本控制与数据防污染工作流

本仓库采用**单一 Git 仓库（Single Git Repository）**控制策略。项目所有的脚本、配置、同步状态（`state.json`）以及 `references/wiki/`、`references/bilibili/`、`references/bwiki_images/index.json`、`references/bwiki_images/estimate_report.json`、`references/bwiki_images/vision_index/assets/`、`references/bwiki_images/vision_index/assets.jsonl` 等文本数据库全部纳入根目录 Git 中管理。`references/bwiki_images/assets_webp/` 作为轻量 WebP 参考图纳入 Git；图片原图缓存 `references/bwiki_images/assets/` 不纳入普通 Git。

在运行爬虫更新数据时，必须严格遵守以下**三步安全工作流**以防坏数据污染：

### 第一步：同步前状态检查
运行 `git status` 确保当前工作区干净，如有未归档改动先提交或使用 `git stash` 暂存。特别检查并确认无任何包含机密敏感信息的临时文件或配置未被拉入追踪（必须通过 `.gitignore` 过滤 `config_secrets.json` 等文件）。

### 第二步：执行同步
运行 `python scripts/wiki/sync_wiki.py`、`python scripts/bilibili/sync_bilibili.py` 或 `python scripts/bwiki_images/sync_bwiki_images.py --download` 执行数据拉取。图片同步前应优先运行不带 `--download` 的估算模式。

### 第三步：数据合规审计与回滚/提交
* **运行审计**：执行 `git status` 预览哪些文件被修改/删除。运行 `git diff` 检查具体修改，特别要注意是否有条目因防火墙拦截或网站服务异常变成了空文件/无效元数据。
* **一键安全回滚（数据异常）**：若发现有任何坏数据被下载、或由于限频请求导致的数据大面积清空，直接运行以下命令撤销本次所有修改，完全退回到同步前的安全状态：
  ```bash
  # 回滚 Wiki 数据
  git restore references/wiki/
  git restore references/wiki/state.json
  # 回滚 B站 数据
  git restore references/bilibili/
  # 回滚 BWiki 图片索引与估算报告
  git restore references/bwiki_images/index.json
  git restore references/bwiki_images/estimate_report.json
  ```
  *(注：必须将状态记录与数据一同回滚，以使同步历史与物理数据对齐，避免状态错乱。)*
* **提交归档（确认安全）**：若确认数据完整无误，执行提交。注意只提交 WebP 图片，不提交原图缓存：
  ```bash
  git add . ':!references/bwiki_images/assets/'
  git commit -m "data: 同步星穹铁道 Wiki 及 B站官方视频最新剧情设定语料"
  ```

---

## 4. 版本更新与数据批判认知原则

为了最大程度节约网络与计算资源，并确保数据的权威性，Agent 维护与答复时必须遵循以下两项核心认知原则：

### 4.1 极致节能与按需更新
* **触发条件**：**当且仅当可能需要更新时（例如游戏内发布了新版本、新角色，或者有明显的社区考据新动态）**，方可触发爬虫进行数据同步。
* **目的**：严禁无视需求进行盲目的定时爬取或冗余请求，一切以节约本地计算与带宽资源、避开 Wiki 服务器 WAF 拦截为最高宗旨。

### 4.2 Wiki 数据批判原则
* **核心认知**：**爬取下来的 Wiki 语料数据不一定是最新、最绝对正确的**。
* **处理准则**：Wiki 是社区用户协作维护的产物，其中可能存在错字、时效性滞后或主观编纂偏差。在答复用户提问或分析世界观时，Agent 应对读取到的 references/wiki 文本持批判性怀疑态度。如果数据存在明显矛盾，应以游戏内官方公开的文本、CG 或权威的考据事实为准，不能盲信 Wiki 的字面描述。

