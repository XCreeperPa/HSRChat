# HSRChat Core

`core/` 存放 HSRChat 的平台无关规则与数据契约，应可被 Codex、Claude Project instructions、OpenAI Agents SDK、Cursor、通用 Markdown 包或未来的 RAG 服务复用。

整个 `core/` 以中文为第一语言。除字段名、代码标识、平台名称和必要技术名词外，新增规则、说明和示例应默认使用中文。

不要把特定平台的 Skill、plugin、MCP、安装流程或 Git 工作流说明放进 `core/`。这些内容属于 `adapters/` 或维护文档。

## 内容

- `policies/`：运行模式、玩法过滤、信源优先级和扮演行为。
- `retrieval/`：adapter 应如何检索本地证据并表达检索结果。
- `schemas/`：未来 `data/runtime/` 或 `dist/` 运行时数据的 JSON schema 草案。

## 当前状态

这里是第一阶段架构骨架。现有原始数据仍保留在 `references/`，现有脚本仍保留在 `scripts/`；后续迁移稳定后，再将维护工具移动到 `maintenance/`。
