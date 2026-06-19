---
name: hsrchat-maintenance
description: "HSRChat 仓库与数据流水线维护 Skill。用户要求同步或修复 Wiki、Bilibili、BWiki 图片、WebP、视觉描述数据，修改爬虫、压缩、审核、审计、schema 或发布工具，检查敏感文件边界，审计数据质量，提交、推送、发布或回滚 HSRChat 变更时使用。不要用于普通星铁剧情问答或角色扮演。"
---

# HSRChat 维护

本 Skill 只处理仓库、数据和工具维护。普通剧情问答和角色扮演应交给运行时 Skill。

## 语言规范

HSRChat 以中文为第一语言。维护说明、审计结论、提交前说明和用户沟通默认使用中文；命令、路径、字段名、API 名称和 commit message 可按项目惯例保留英文。

## 必读文档

维护前必须阅读：

- `AGENTS.md`：项目级运行/维护分流与语言规范。
- `references/docs/devops.md`：安全、Git 与数据污染防护规则。
- `references/docs/data_sources.md`：各信源同步工作流。
- `references/docs/maintenance.md`：修改或运行脚本时的维护说明。
- `references/docs/next_stage_architecture_plan.md`：修改架构、adapter、core 规则或目录布局时的计划。

按需阅读信源专项文档：

- Wiki 文本：`references/docs/source_wiki.md`
- Bilibili 元数据：`references/docs/source_bilibili.md`
- BWiki 图片与视觉索引：`references/docs/source_bwiki_images.md`

## 维护流程

1. 修改数据或运行同步脚本前检查 `git status`。
2. 确认 `config_secrets.json` 和 `references/bwiki_images/assets/` 被忽略且未暂存。
3. 优先运行最小相关命令；有测试模式或估算模式时先用测试/估算。
4. 生成或同步后检查 `git status` 和 `git diff`。
5. 提交前审计生成索引，尤其是图片数量、JSON/JSONL 可解析性、重复路径和空描述。
6. 只有确认数据和版本控制边界安全后才提交。

## 脚本边界

当前兼容脚本路径仍位于 `scripts/`：

- `scripts/wiki/`
- `scripts/bilibili/`
- `scripts/bwiki_images/`
- `scripts/vision/`

目标架构后续会将维护工具迁移到 `maintenance/scripts/`。在路径迁移和文档同步完成前，必须保持现有命令可用。

## 运行时边界

本 Skill 不回答普通剧情或扮演请求。如果用户没有要求修改数据或工具，而是在询问星铁剧情、角色、派系、官方视频、CG 或角色扮演，应切换到运行时 Skill。
