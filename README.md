# HSRChat - 星穹铁道专属剧情与设定 Skill

HSRChat 是一个基于 **Agent Skills** 开放规范构建的《崩坏：星穹铁道》（Honkai: Star Rail）世界观剧情设定技能包。它旨在为 AI 智能体（Agent）提供一套权威、纯净的官方参考语料，使其能够深度交流崩铁的世界观、主支线剧情以及角色背景故事。

此 Skill 采用**渐进式披露（On-demand Activation）**设计。在交互时，仅在用户提起“星穹铁道”、“崩铁”或相关角色设定时才被激活，将对应的语料引入到 Agent 上下文中以提供事实性背景支撑。

---

## 目录结构

```text
D:\HSRChat\
├── SKILL.md             # Skill 核心声明文件（定义触发词与核心行为指南）
├── config.json          # 爬虫要抓取的官方分类配置列表
├── README.md            # 项目说明文档（本文件）
├── references/
│   └── devops.md        # 开发运维指南与 Git 版本控制规范
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
    ├── get_categories.py # 脚本 1：命令行输出 BWiki 全部分类
    └── crawler.py        # 脚本 2：基于状态文件的智能同步爬虫（带自动目录清理）
```

---

## 安装与获取方法

### 1. 通用 Agent / 知识库克隆
如果你需要在自定义的 AI 智能体或 RAG 本地知识库中使用本数据库，可以直接克隆本仓库：
```bash
git clone https://github.com/XCreeperPa/HSRChat.git
```
克隆完成后，将 `references/wiki/` 目录挂载到你的向量数据库或 Agent 检索路径即可。

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

项目内置了两个 Python 脚本（仅依赖原生 Python 标准库，无需安装第三方依赖包），用于维护和更新 `references/wiki/` 目录中的数据。

### 1. 查询所有分类 (get_categories.py)
用于查询星穹铁道 BWiki（Bilibili Game Wiki）当前的全部页面分类，并将其输出到命令行终端：
```bash
python scripts/get_categories.py
```
*提示：该脚本不会写入或修改本地任何文件，结果完全通过控制台标准输出返回，便于与其他命令行管道结合使用。*

### 2. 智能同步与目录维护 (crawler.py)
该脚本是多线程高并发爬虫（最大支持 8 并发），负责下载页面并将非指定分类的文件夹物理清除：
* **全量同步（默认读取 `config.json` 中的分类）**：
  ```bash
  python scripts/crawler.py
  ```
* **测试同步（每个分类仅同步前 10 个页面，加快测试与验证）**：
  ```bash
  python scripts/crawler.py --test
  ```
* **关于多余分类目录的自动清除**：
  在执行 `crawler.py` 时，脚本会自动对比配置文件中的指定分类。如果 `references/wiki/` 目录下含有**非指定分类**的文件夹，爬虫会在运行时**主动将其从本地物理删除**，同时将其在 `state.json` 中的历史同步时间戳记录一并抹除，以保证数据库只包含所指定的官方内容。
* **基于 `state.json` 的智能增量同步 (Version Sync)**：
  - 脚本不使用容易出现时区或设备误差的本地文件修改时间，而是将已下载条目的最新 API 时间戳记录在 `references/wiki/state.json` 中。
  - 在下载前，脚本会获取线上条目的最新修改时间（`timestamp`），并与 `state.json` 进行对比。
  - 仅在**本地文件不存在**或**线上版本新于 `state.json` 中的记录**时，才会发起网络请求并覆盖下载。若线上版本无更新，则瞬间跳过，极大地节省流量并保障安全防风控。

---

## 数据安全与版本控制方案 (防篡改/防空回滚)

本项目采用**单 Git 仓库管理模式**，将所有的同步状态和 Wiki 文本全部纳入根目录 Git 中管理。在运行爬虫更新数据时，请严格遵守以下三步安全工作流（详见 `references/devops.md`）：

1. **同步前检查**：运行 `git status` 确保工作区干净。
2. **执行同步**：运行 `python scripts/crawler.py` 获取最新数据。
3. **数据审核与操作**：
   - 运行 `git diff references/wiki/` 检查修改。如果发现有页面内容被删除、清空或因为 WAF 防护拦截变成了空文件。
   - **安全回滚**：运行以下指令放弃本次同步结果，完全恢复到同步前的安全状态：
     ```bash
     git restore references/wiki/
     git restore references/wiki/state.json
     ```
     *(注：必须将 state.json 与数据一同回滚，以使同步历史与物理数据对齐，避免状态错乱。)*
   - **确认无误后提交**：如果数据均无损坏，执行 `git commit -a -m "data: 同步星铁最新数据"` 归档。

---

## 核心过滤原则

1. **数据中含有杂质**：因为 BWiki 的原始 Wikitext 中难免会含有角色的战斗属性、升级材料、周本材料或副本解锁引导。
2. **免除物理清洗**：项目不开发专门的清洗逻辑，以保留最完整的上下文背景。
3. **运行时过滤**：在 `SKILL.md` 中已经配置了指令约束。Agent 在激活本 Skill 并读取 `references/wiki/` 的语料数据时，会自动在运行时过滤掉一切关于“数值、配队、战斗、升级材料、光锥遗器推荐”的内容，确保回答完全聚焦于世界观、角色和剧情。
