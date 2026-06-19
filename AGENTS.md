# HSRChat Agent 指南

HSRChat 正在从单一 Codex Skill 迁移为可适配多种 Agent 平台的星穹铁道领域知识系统。整个项目以中文为第一语言：规范、说明、提示词、运行输出与维护文档应默认使用中文；英文仅用于必要的技术名词、平台名称、字段名、代码标识和跨平台兼容描述。

## 语言规范

- 项目文档、Skill 正文、Agent 指令、维护流程和示例回答默认使用中文。
- 面向用户的运行时回答默认使用中文，除非用户明确要求其他语言。
- JSON 字段名、脚本参数、目录名、平台 API 名称、manifest 字段等可保留英文。
- 新增英文说明时，应同时提供中文主体语义，避免让英文成为唯一规范来源。
- 翻译或适配到其他 Agent 平台时，以中文核心规则为准，英文只作为平台兼容层。

## 运行时工作

以下任务使用运行时规则：

- 星穹铁道剧情、世界观、角色分析、扮演和视觉资料问答。
- 闲聊、考据、扮演三种模式的判定与切换。
- 将 `references/wiki/`、`references/bilibili/` 和 `references/bwiki_images/` 作为证据来源读取。

普通运行时问答中不得运行同步、下载、压缩、审核、审计、Git 发布或其他维护脚本。

## 维护工作

仅当用户明确要求以下任务时，使用维护规则：

- 同步 Wiki、Bilibili、BWiki 图片或视觉描述数据。
- 修改爬虫、压缩、审核、审计或发布脚本。
- 审计数据质量、敏感文件边界、原图缓存边界或生成索引。
- 提交、推送、发布或回滚 HSRChat 数据与工具变更。

维护工作开始前，必须阅读 `references/docs/devops.md` 和 `references/docs/data_sources.md`。

## 版本控制边界

- 不得提交 `config_secrets.json`。
- 不得提交 `references/bwiki_images/assets/`。
- 只从 `references/bwiki_images/assets_webp/` 提交 WebP 参考图。
- 原始 Wiki 数据是可追溯证据，不做破坏性清洗；玩法污染通过运行时策略或派生索引过滤。
