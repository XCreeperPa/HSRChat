# HSRChat - 星穹铁道专属剧情与设定 Skill

HSRChat 是一个面向 Agent Skills 的《崩坏：星穹铁道》（Honkai: Star Rail）剧情、角色与世界观技能包。它把本地 Wiki 文本、官方视频元数据、BWiki 图片索引与角色语音语料组织成可检索参考，让 Agent 在聊星铁时更像“懂剧情的人”，而不是只靠泛泛印象回答。

这个 Skill 的重点不是玩法攻略，而是：

- 世界观设定：星神、命途、派系、星系、历史事件。
- 主支线剧情：开拓任务、开拓续闻、同行任务、冒险任务。
- 角色理解：人物背景、台词风格、关系网络、视觉与主题表达。
- 角色扮演：在不 OOC 的前提下，用角色自己的语气和认知回应。

HSRChat 会在用户提到“星穹铁道”“崩铁”或相关角色、剧情、设定时激活。

---

## 语言规范

HSRChat 整个项目以中文为第一语言。

- 项目文档、Skill 正文、Agent 指令、维护流程、运行时回答和示例默认使用中文。
- 用户未指定语言时，剧情问答、考据、扮演和维护说明都应使用中文。
- 英文仅用于必要的专有名词、平台名称、字段名、代码标识、路径、命令、API 名称和跨平台兼容说明。
- 新增 adapter 或发布包时，应以中文核心规则为准；英文说明只能作为平台兼容层，不应成为唯一规范来源。

---

## 多种信源

HSRChat 不是单一文本库，而是把几类互补信源放在一起使用：

| 信源 | 路径 | 主要用途 |
| :--- | :--- | :--- |
| Wiki 文本 | `references/wiki/` | 主线、支线、书籍、角色、NPC、角色语音等剧情与设定文本 |
| 官方视频元数据 | `references/bilibili/` | 角色 PV、动画短片、千星纪游、EP、版本宣传等官方物料的标题、简介与发布时间 |
| BWiki 图片索引 | `references/bwiki_images/index.json` | 任务 CG、书籍插图、短信图、角色立绘等视觉信源的来源页、上下文和原图元数据 |
| WebP 参考图 | `references/bwiki_images/assets_webp/` | 面向 Agent 的轻量图片参考，用于角色外观、美术风格和剧情画面分析 |
| 图片文本描述 | `references/bwiki_images/vision_index/assets/` | 与 WebP 参考图一一对应的审核通过版中文视觉描述，目录结构与 `assets_webp/` 一致；`assets.jsonl` 保留为聚合兼容索引 |
| 数据源说明 | `references/docs/` | 各信源的同步逻辑、边界、维护方式和版本控制规则 |

这些信源的分工大致是：

- **问剧情和设定**：优先查 Wiki 文本，必要时多跳检索相关角色、任务、书籍和隐藏概念。
- **问官方物料或时间线**：结合 B站官方视频元数据，核对 PV、动画短片和版本宣传中的信息。
- **问美术、立绘、CG 或视觉符号**：结合 BWiki 图片索引和 WebP 参考图，不只靠文字描述。
- **非多模态环境读图**：优先读取 `references/bwiki_images/vision_index/assets/` 下与图片同目录、同名的 JSON 描述，再按需回查原 WebP 图和 BWiki 图片索引。
- **问角色扮演**：优先检索角色语音、角色故事和相关任务台词，提取称谓、口吻、关系和认知边界。

Wiki 是社区协作整理的文本库，可能存在错字、滞后或主观整理痕迹。考据模式下如果多信源冲突，应优先采用游戏内文本、角色台词、官方视频与图像中直接呈现的内容，并明确区分事实、推论和留白。

---

## 三种模式

HSRChat 现在按“设定的使用方式”分成三种模式，而不是按回答长短分：

| 模式 | 目标 | 设定怎么用 | 适合的问题 |
| :--- | :--- | :--- | :--- |
| 闲聊 | 简洁、直白、好聊 | 作为背景约束，不堆设定 | “介绍星铁的看板娘”“你怎么看星期日？” |
| 考据 | 细致、准确、可追溯 | 作为论证材料，大量准确运用 | “考据三月七和长夜月的关系”“分析二相乐园剧情” |
| 扮演 | 真实、自然、合理 | 内化为角色语言、情绪和反应 | “扮演三月七回答我”“景元，你怎么看丹枫？” |

一句话概括：

- 闲聊要“懂但不显摆”。
- 考据要“细且有依据”。
- 扮演要“像且合理”。

---

## 使用示例

### 闲聊：介绍角色

用户：

```text
介绍星穹铁道的看板娘
```

期望风格：

```text
《崩坏：星穹铁道》里大家常说的“看板娘”，一般指三月七。她是星穹列车组的核心成员之一，也是开拓者最早同行的伙伴之一。

三月七的辨识度很强：粉发、相机、元气少女、吐槽役，遇到新鲜事总想拍下来。她不像远处的大人物，更像旅途中一直在旁边吵吵闹闹的朋友。

她名字的来源也很有记忆点：三月七曾被封在一块特殊的冰中，被星穹列车救下；醒来后失去了过去的记忆，于是把被发现的日期当作自己的名字。
```

这个场景应避免主动介绍属性、战斗命途、技能、配队、光锥、遗器或新手实用性。

### 考据 / 赏析：剧情分析

用户：

```text
赏析三月七在二相乐园的剧情
```

期望风格：

```text
三月七在二相乐园里的作用，可以概括成一句话：她不是主线谜题的解答者，却是这段高密度剧情里最稳定的“人味锚点”。

在本地任务文本中，《误以为结束的错觉》让三月七承担了很重要的情感校准功能。她关注新闻是否可信，也关注开拓者是否变得太沉重。二相乐园到处是表演、关注、英雄包装和信息污染，而三月七总是在把目光拉回具体的人。

她的吐槽也不是单纯插科打诨，而是一种抗压方式。星神游戏、灾难传播、画中世界和英雄叙事全都压过来时，三月七的轻快让剧情重新有了呼吸。
```

考据模式可以显式说明参考了哪些任务、角色文本或官方物料；赏析类回答可以轻一点，但不能把猜测写成事实。

### 扮演：角色回应

用户：

```text
请你扮演三月七，回答：你觉得苍天航路绒绒号怎么样？
```

期望风格：

```text
（她一听到书名，眼睛立刻亮了一下，像是已经在脑子里翻开了漫画页。）

《苍天航路绒绒号》？当然很可爱啦！毛茸茸的列车、毛茸茸的大家，还有那个活泼可爱的三月兔……咳咳，虽然被画成那样有点不好意思，但不得不说，马老师还是挺懂的嘛。

不过呢，艺术加工也太多了吧！开拓者，你别笑！尤其是你，你在里面那个“球棒浣熊”的形象明明也很离谱，但居然还挺受欢迎的，真让人不甘心。
```

扮演模式默认使用中文全角括号 `（ ）` 表示动作、神态、环境互动或短暂思想；括号外是角色实际说出口的话。不要写“根据 Wiki 记载”之类跳戏说明。

---

## 安装

详细安装方式见 [references/docs/installation.md](references/docs/installation.md)。

最常用的 Codex 安装方式：

```powershell
git clone https://github.com/XCreeperPa/HSRChat.git
$dest = "$HOME\.codex\skills\HSRChat"
Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force .\HSRChat "$HOME\.codex\skills\HSRChat"
Remove-Item -Recurse -Force "$HOME\.codex\skills\HSRChat\.git" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$HOME\.codex\skills\HSRChat\references\bwiki_images\assets" -ErrorAction SilentlyContinue
```

安装后重启 Codex，使新 Skill 被重新发现。

---

## 目录结构

```text
D:\HSRChat\
├── AGENTS.md            # Agent 分流入口：运行与维护职责边界
├── SKILL.md             # 兼容期 Skill 入口与三模式行为规范
├── roleplay.md          # 扮演模式指南
├── config.json          # Wiki 与 B站分类配置
├── README.md            # 项目入口说明
├── core/                # 平台无关的运行策略、检索契约与数据 schema
│   ├── policies/        # 三模式、玩法过滤、信源优先级与扮演策略
│   ├── retrieval/       # 多跳检索与引用契约
│   └── schemas/         # 运行时派生数据 schema 草案
├── adapters/
│   └── codex/
│       └── skills/
│           ├── hsrchat-runtime/      # Codex 运行时 Skill 原型
│           └── hsrchat-maintenance/  # Codex 维护 Skill 原型
├── references/
│   ├── docs/            # 安装、维护、数据源与运维文档
│   ├── bwiki_images/    # BWiki 图片索引、WebP 参考图与审核通过的图片文本描述
│   ├── bilibili/        # 官方视频元数据 JSON
│   └── wiki/            # Wiki 剧情、角色、书籍、任务与语音文本
└── scripts/             # 维护脚本，按信源和用途分组
    ├── wiki/            # BWiki 文本分类查询与同步
    ├── bilibili/        # B站官方视频元数据同步
    ├── bwiki_images/    # BWiki 图片索引、下载、压缩与流水线
    └── vision/          # 图片文本描述生成、合并、拆分与人工审核
```

当前根目录 `SKILL.md` 仍然保留，保证既有 Codex 安装方式不失效。新的 `core/` 与 `adapters/codex/skills/` 是下一阶段架构的原型入口：运行时问答走 `hsrchat-runtime`，数据同步、审计、脚本修改和发布走 `hsrchat-maintenance`。

更多技术细节：

- [下一阶段架构开发计划](references/docs/next_stage_architecture_plan.md)
- [安装指南](references/docs/installation.md)
- [维护与脚本说明](references/docs/maintenance.md)
- [统一数据源同步与运维指南](references/docs/data_sources.md)
- [开发运维与 Git 工作流](references/docs/devops.md)
- [Wiki 文本信源设计](references/docs/source_wiki.md)
- [B站官方视频信源设计](references/docs/source_bilibili.md)
- [BWiki 图片信源设计](references/docs/source_bwiki_images.md)

---

## 数据边界

HSRChat 只面向剧情、世界观、角色理解和扮演，不提供玩法攻略。

即使本地 Wiki 原始文本中包含少量玩法杂质，Agent 也必须在运行时过滤掉：

- 角色数值、技能机制、星魂效果。
- 光锥、遗器、配队、深渊、虚构叙事等玩法建议。
- 晋阶材料、周本材料、副本解锁指引。
- “主 C / 辅助 / 盾奶”等战斗定位。

项目保留原始语料的完整性，不对 Wiki 文本做物理清洗；过滤逻辑由 `SKILL.md` 的行为规范约束。
