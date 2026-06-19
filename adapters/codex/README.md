# HSRChat Codex Adapter

此 adapter 用于在 Codex 中验证运行/维护分离，同时不破坏根目录 `SKILL.md` 的既有安装方式。

## 语言规范

Codex adapter 同样以中文为第一语言。Skill 正文、触发说明和 UI 元信息默认写中文；`name`、路径、manifest 字段等技术标识可保留英文。

## Skills

- `skills/hsrchat-runtime/`：星铁剧情、设定考据、角色扮演和视觉资料问答。
- `skills/hsrchat-maintenance/`：数据同步、爬虫与图片流水线、视觉索引审核、审计、提交、推送和发布。

迁移期内根目录 `SKILL.md` 仍作为兼容入口保留。后续可以从该 adapter 生成 `dist/codex/` 发布产物。
