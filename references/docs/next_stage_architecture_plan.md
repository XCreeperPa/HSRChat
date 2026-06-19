# HSRChat 下一阶段架构开发计划

本文记录 HSRChat 下一阶段的架构方向：将当前 Codex Skill 形态升级为更通用的、可适配多种 Agent 平台的领域知识与维护系统。

当前结论是：**HSRChat 不应继续以单一 Codex Skill 作为项目本体**。更稳妥的方向是将项目拆成平台无关的核心层、数据层、维护层和平台适配层。Codex Skill 仍然保留，但只作为其中一个 adapter。

---

## 1. 背景

HSRChat 目前已经不只是一个轻量 Skill，而是同时包含：

- 星穹铁道剧情、世界观、角色理解与扮演的运行时规则。
- BWiki 文本、B站官方视频元数据、BWiki 图片索引、WebP 参考图和视觉描述数据。
- Wiki/B站/图片同步脚本、图片压缩脚本、视觉描述审核工具和数据审计流程。
- Git 提交、回滚、敏感凭证隔离、原图缓存排除等维护规范。

这种一体化结构在早期开发中推进很快，但现在已经出现明显耦合：

- 普通运行时问答会暴露过多维护、爬虫和 Git 工作流信息。
- 数据维护任务和剧情问答任务的权限、上下文和风险完全不同。
- 单一 `SKILL.md` 同时承载运行规则与运维规则，不利于 progressive disclosure。
- 未来如果部署到非 Codex 平台，当前目录和说明会过度绑定 Codex Skill 语义。

下一阶段的核心目标是：**把 Codex Skill 从项目本体降级为平台适配层，把 HSRChat 建成 agent-agnostic 的领域知识系统。**

---

## 2. 设计原则

### 2.0 中文第一语言

HSRChat 的核心规则、项目文档、运行提示词、维护流程和面向用户的默认输出都应以中文为第一语言。

- `core/` 中的平台无关策略必须使用中文作为规范主体。
- `adapters/` 可以保留平台要求的英文 `name`、字段名、manifest 键和 API 名称，但正文语义应默认中文。
- 运行时回答、考据、扮演和视觉资料解读默认中文，除非用户明确要求其他语言。
- 维护说明、审计结论、提交前说明和发布说明默认中文；命令、路径、字段名和必要技术名词可保留英文。
- 为 Claude、OpenAI Agents SDK、Cursor、通用 Markdown 等平台生成适配包时，应先消费中文核心规则，再按平台需要生成英文或双语兼容说明。

### 2.1 平台无关优先

项目核心规则不应写成“Codex 必须怎样做”，而应写成任何 Agent 都能理解和复用的领域策略：

- 闲聊、考据、扮演三种运行模式。
- 剧情与世界观优先，玩法攻略过滤。
- 来源可信度分层。
- 剧透边界与版本进度控制。
- 多跳检索与多信源引用。
- 图片、视频、角色语音等资料的使用规则。

Codex、Claude、OpenAI Agents SDK、自建 RAG、Cursor、Dify、Coze、LangChain/LlamaIndex 等平台只通过 adapter 消费这些核心规则。

### 2.2 运行与维护分离

运行时只负责回答问题、检索资料、引用来源和角色扮演。

维护层才负责：

- 同步 BWiki 文本。
- 同步 B站官方视频元数据。
- 下载与压缩图片。
- 生成和审核视觉描述。
- 构建派生索引。
- 执行数据一致性审计。
- 提交和发布数据更新。

运行时不得默认加载维护脚本、同步说明、凭证规则和 Git 回滚流程。

### 2.3 原始数据与运行时数据分离

原始 Wiki 文本需要保持完整可追溯，但运行时不应直接把所有 raw text 当作默认检索入口。

下一阶段应生成更适合 Agent 消费的运行时数据：

- 清洗或标注过的剧情 chunk。
- 玩法污染标记。
- 来源类型和可信度。
- 角色别名与实体关系。
- 角色扮演 profile。
- 图片视觉描述索引。
- 时间线与版本标签。

原始数据作为回查证据，运行时优先使用派生索引。

### 2.4 一个仓库，内部清晰分层

现阶段不建议立即拆成多个仓库。维护工具、数据资产和运行时规则仍然高度联动，monorepo 更容易保证数据更新、脚本变更、文档和索引一起审计。

当出现以下信号时，再考虑拆仓库：

- 数据体积显著增大，普通克隆成本过高。
- 维护脚本需要更严格的私有权限或 CI 环境。
- runtime、data、maintenance 的发布节奏明显分化。
- 多个下游只想依赖数据包，不想克隆维护工具。
- 需要独立版本化发布，例如 `hsrchat-data@YYYY.MM`。

---

## 3. 目标架构

下一阶段目标结构建议如下：

```text
HSRChat/
├── core/
│   ├── policies/
│   │   ├── modes.md
│   │   ├── roleplay.md
│   │   ├── source_priority.md
│   │   ├── spoiler_policy.md
│   │   └── gameplay_filter.md
│   ├── prompts/
│   │   ├── runtime_system.md
│   │   ├── casual_chat.md
│   │   ├── lore_analysis.md
│   │   └── roleplay.md
│   ├── retrieval/
│   │   ├── retrieval_contract.md
│   │   ├── query_patterns.md
│   │   └── citation_rules.md
│   └── schemas/
│       ├── document.schema.json
│       ├── image.schema.json
│       ├── video.schema.json
│       ├── role_profile.schema.json
│       └── timeline_event.schema.json
│
├── data/
│   ├── raw/
│   │   ├── wiki/
│   │   ├── bilibili/
│   │   └── bwiki_images/
│   └── runtime/
│       ├── documents.jsonl
│       ├── chunks.jsonl
│       ├── images.jsonl
│       ├── videos.jsonl
│       ├── role_profiles/
│       ├── timeline.jsonl
│       └── manifest.json
│
├── maintenance/
│   ├── scripts/
│   │   ├── wiki/
│   │   ├── bilibili/
│   │   ├── bwiki_images/
│   │   ├── vision/
│   │   └── audit/
│   └── docs/
│       ├── devops.md
│       ├── data_sources.md
│       ├── maintenance.md
│       ├── source_wiki.md
│       ├── source_bilibili.md
│       └── source_bwiki_images.md
│
├── adapters/
│   ├── codex/
│   │   ├── skills/
│   │   │   ├── hsrchat-runtime/
│   │   │   └── hsrchat-maintenance/
│   │   └── plugin/
│   ├── claude-project/
│   ├── openai-agents/
│   ├── cursor/
│   └── generic-md/
│
├── dist/
│   ├── generic/
│   ├── codex/
│   └── manifest.json
│
├── docs/
├── README.md
└── LICENSE
```

这是一份目标结构，不要求一次性完成。近期改造应以低风险迁移为主。

---

## 4. 分层说明

### 4.1 `core/`

`core/` 是平台无关的项目核心。

它保存 HSRChat 的领域规则、提示词策略、检索契约和数据 schema。这里不应出现 Codex 独有术语，例如 `SKILL.md`、插件 manifest、Codex MCP 等。

核心内容包括：

- 三模式策略：闲聊、考据、扮演。
- 星铁领域边界：剧情、世界观、角色理解、视觉资料、官方物料。
- 玩法过滤：角色数值、技能机制、配队、遗器、光锥适配等内容默认过滤。
- 来源可信度：游戏内文本、角色语音、官方视频、BWiki 文本、图片描述、社区整理、合理推论。
- 剧透策略：按用户进度过滤后续信息。
- 检索契约：输入、输出、过滤条件、引用格式。

### 4.2 `data/`

`data/raw/` 保存原始或接近原始的数据：

- Wiki 文本。
- B站官方视频元数据。
- BWiki 图片索引、WebP、视觉描述。

`data/runtime/` 保存给 Agent 直接消费的派生数据：

- JSONL 文档索引。
- 已切分 chunk。
- 图片描述索引。
- 角色 profile。
- 时间线。
- entity alias。
- manifest。

运行时 adapter 优先消费 `data/runtime/`，必要时再回查 `data/raw/`。

### 4.3 `maintenance/`

`maintenance/` 负责所有数据生产和仓库维护动作。

这里包含脚本、运维文档、审计工具、同步配置说明和发布流程。它可以读写 `data/raw/` 和 `data/runtime/`。

普通剧情问答和角色扮演不应读取这里的文档，也不应执行这里的脚本。

### 4.4 `adapters/`

`adapters/` 保存平台适配层。

第一阶段优先实现 Codex：

- `hsrchat-runtime`：用于星铁剧情问答、考据、角色理解、扮演和视觉资料使用。
- `hsrchat-maintenance`：仅用于数据同步、图片流水线、视觉审核、审计、提交和发布。

后续可添加：

- `claude-project`：生成 Claude Project instructions 和导入清单。
- `openai-agents`：提供工具函数和检索服务。
- `cursor`：提供维护开发规则。
- `generic-md`：输出通用 Markdown 指令包。

### 4.5 `dist/`

`dist/` 是发布产物目录。

它不应该成为手写源文件的主要位置，而应由工具生成：

- Codex skill/plugin 发布包。
- 通用 Markdown 运行包。
- JSONL 数据包。
- manifest。

---

## 5. Codex 适配方案

按 Codex Skill 的职责边界，下一阶段应拆成两个 skill。

### 5.1 `hsrchat-runtime`

触发场景：

- 用户询问星穹铁道剧情、设定、角色、人设、世界观。
- 用户要求考据、时间线、来源、赏析。
- 用户要求角色扮演。
- 用户询问 CG、立绘、光锥卡面、视觉符号、官方视频物料。

不负责：

- 同步数据。
- 下载图片。
- 压缩 WebP。
- 审核视觉描述。
- 修改仓库结构。
- 提交和推送。

### 5.2 `hsrchat-maintenance`

触发场景：

- 用户要求同步 Wiki/B站/图片数据。
- 用户要求更新语料库。
- 用户要求生成或审核图片视觉描述。
- 用户要求运行数据审计。
- 用户要求提交、发布、回滚数据更新。
- 用户要求修改维护脚本或数据源配置。

不负责：

- 普通剧情问答。
- 角色扮演。
- 在未明确维护请求时运行同步或下载脚本。

### 5.3 根级指导

根目录可以新增轻量 `AGENTS.md`，只写项目级分流规则：

```markdown
# HSRChat Agent Guidance

- 星铁剧情、设定考据、角色扮演和视觉资料问答使用运行时 Skill。
- 数据同步、图片流水线、视觉审核、审计、提交和发布使用维护 Skill。
- 普通运行时问答中不得运行同步、下载或压缩脚本。
- 不得提交 `config_secrets.json` 或 `references/bwiki_images/assets/`。
```

不要把复杂运行规则或维护流程塞进 `AGENTS.md`。

---

## 6. 数据契约草案

跨平台适配的关键不是目录，而是稳定 schema。

### 6.1 文本文档记录

```json
{
  "id": "wiki:角色:三月七",
  "source_type": "wiki_text",
  "category": "角色",
  "title": "三月七",
  "path": "data/raw/wiki/角色/三月七.txt",
  "authority": "community_wiki",
  "content_kind": "character_profile",
  "contains_gameplay": true,
  "spoiler_level": "unknown",
  "version": null,
  "text": "...",
  "metadata": {}
}
```

### 6.2 图片记录

```json
{
  "id": "image:bwiki:...",
  "source_type": "bwiki_image",
  "asset_kind": "light_cone_artwork",
  "title": "光锥-立绘-...",
  "image_path": "data/raw/bwiki_images/assets_webp/光锥/example.webp",
  "vision_description_path": "data/raw/bwiki_images/vision_index/assets/光锥/example.json",
  "source_pages": [],
  "authority": "community_wiki_asset",
  "contains_gameplay": false
}
```

### 6.3 官方视频记录

```json
{
  "id": "bilibili:BV...",
  "source_type": "official_video_metadata",
  "title": "...",
  "url": "...",
  "pubdate": "...",
  "category": "千星纪游",
  "authority": "official_metadata",
  "transcript_available": false
}
```

### 6.4 角色扮演 Profile

```json
{
  "character": "景元",
  "addressing": [],
  "speech_style": [],
  "relationship_notes": [],
  "knowledge_boundaries": [],
  "source_paths": []
}
```

---

## 7. 分阶段实施计划

### 阶段 1：文档和入口解耦

目标：不移动数据、不破坏当前 Skill 使用，只先拆清楚概念边界。

任务：

- 新增本计划文档。
- 在 README 中说明下一阶段将采用 `core / data / maintenance / adapters / dist` 分层。
- 将当前 `SKILL.md` 中的维护规则标注为待迁移内容。
- 规划 `hsrchat-runtime` 与 `hsrchat-maintenance` 两个 skill 的触发边界。

验收：

- README 能指向下一阶段计划。
- 维护者能理解后续迁移路径。
- 当前 Codex Skill 使用不受影响。

### 阶段 2：Codex 双 Skill 原型

目标：先在 Codex 中验证运行与维护拆分。

任务：

- 创建 `adapters/codex/skills/hsrchat-runtime/SKILL.md`。
- 创建 `adapters/codex/skills/hsrchat-maintenance/SKILL.md`。
- 将 `roleplay.md` 的运行时内容迁入 runtime skill 或由 runtime skill 明确引用。
- 将 devops、data_sources、maintenance 等维护说明迁入 maintenance skill 的 references。
- 根 `SKILL.md` 暂时保留为兼容入口，但注明将被 adapter 结构替代。

验收：

- 普通星铁问题只触发 runtime skill。
- 数据同步和提交请求只触发 maintenance skill。
- 两个 skill 的 `description` 边界清晰，不互相抢任务。

### 阶段 3：维护目录迁移

目标：把维护脚本和维护文档从运行时根上下文中移出。

任务：

- 将 `scripts/` 迁移到 `maintenance/scripts/`。
- 将维护文档迁移到 `maintenance/docs/`。
- 更新所有脚本路径和文档引用。
- 增加审计脚本，检查敏感文件、原图缓存、图片描述数量、索引一致性。

验收：

- 所有维护脚本能从新路径运行。
- 文档中的命令路径一致。
- `config_secrets.json` 和原图缓存仍不进入 Git。

### 阶段 4：运行时派生数据

目标：减少运行时直接检索 raw Wiki 的比例。

任务：

- 定义 `core/schemas/`。
- 生成 `data/runtime/documents.jsonl`。
- 生成 `data/runtime/chunks.jsonl`。
- 标记 `contains_gameplay`、`source_type`、`authority`、`content_kind`。
- 生成 `data/runtime/images.jsonl` 和 `videos.jsonl`。
- 尝试生成首批 `role_profiles/`。

验收：

- 运行时 adapter 优先消费 `data/runtime/`。
- 原始 Wiki 仍可回查。
- 玩法污染字段被标注或从默认 chunk 中剥离。

### 阶段 5：跨 Agent 通用包

目标：验证项目不再绑定 Codex。

任务：

- 生成 `dist/generic/hsrchat-runtime.md`。
- 生成 `dist/generic/hsrchat-documents.jsonl`。
- 生成 `dist/generic/manifest.json`。
- 输出 Claude Project instructions 草案。
- 输出 OpenAI Agents SDK tool contract 草案。

验收：

- 非 Codex Agent 可以读取 generic runtime 文档和 JSONL 数据。
- Codex Skill 只是 adapter，不再是唯一项目形态。

---

## 8. 当前阶段的具体落点

短期内不建议立刻改动所有目录。下一步应采用低风险顺序：

1. 保持当前根目录结构可用。
2. 新增本计划文档。
3. 在 README 中挂入口。
4. 后续新建 `adapters/codex/skills/` 进行双 Skill 原型。
5. 原有根 `SKILL.md` 在过渡期保留。
6. 等双 Skill 原型稳定，再迁移 `scripts/` 和维护文档。

这样可以避免一次性大搬家导致 Skill 安装、脚本路径和数据同步流程同时失效。

### 8.1 已落地的第一批改造

截至 2026-06-19，已完成以下低风险骨架：

- 新增 `AGENTS.md`，作为项目级运行/维护分流入口。
- 新增 `core/policies/`，沉淀三模式、玩法过滤、信源优先级与扮演策略。
- 新增 `core/retrieval/retrieval_contract.md`，定义平台无关的多跳检索契约。
- 新增 `core/schemas/`，提供文本与图片运行时记录 schema 草案。
- 新增 `adapters/codex/skills/hsrchat-runtime/`，作为 Codex 运行时 Skill 原型。
- 新增 `adapters/codex/skills/hsrchat-maintenance/`，作为 Codex 维护 Skill 原型。
- 根 `SKILL.md` 继续保留为兼容入口，但已标注运行与维护分流。

这些改动不移动现有 `references/` 数据和 `scripts/` 脚本，目标是先验证职责边界，再进入脚本迁移和运行时派生数据阶段。

---

## 9. 风险与注意事项

- 不要为了“平台无关”过早牺牲当前 Codex 可用性。
- 不要把 `core/` 写成另一个巨型 `SKILL.md`，核心规则也要模块化。
- 不要让 adapter 反向污染 core。
- 不要把维护脚本默认暴露给运行时问答。
- 不要物理删除 raw Wiki 中的玩法字段；应通过派生索引标注或过滤。
- 不要过早拆仓库；先把 monorepo 内部边界做清楚。

---

## 10. 一句话结论

HSRChat 下一阶段应从“单一 Codex Skill 仓库”升级为“平台无关的星铁领域知识系统”：

```text
core + data + maintenance + adapters + dist
```

其中 Codex Skill 是 adapter，运行与维护应拆成两个独立 skill；共享数据由维护层生产，由运行层消费。当前阶段先保持一个仓库，通过目录和文档边界完成解耦，等数据体积、权限和发布节奏真正分化后，再考虑拆成多个仓库。
