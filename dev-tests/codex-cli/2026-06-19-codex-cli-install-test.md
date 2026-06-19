# HSRChat Codex CLI 安装与运行测试记录

## 测试概况

- 测试日期：2026-06-19
- 测试环境：Windows / PowerShell / Codex CLI
- Codex CLI 版本：`codex-cli 0.140.0`
- 安装来源：GitHub `https://github.com/XCreeperPa/HSRChat.git`
- 安装分支：`main`
- 安装提交：`7b0e48d1655acf472a1aa7c6cd36efc36ac358c1`
- 提交说明：`docs: set Chinese as primary project language`
- 安装目标：`C:\Users\Administrator\.codex\skills\HSRChat`
- 旧版备份：`C:\Users\Administrator\.codex\skills\HSRChat.backup-20260619-184444`

## 安装记录

本次安装按仓库安装指南从 GitHub 克隆最新 `main`，将整个仓库作为兼容版 Codex Skill 安装到 `C:\Users\Administrator\.codex\skills\HSRChat`。

安装后已确认：

- `SKILL.md` 存在，Skill 名称为 `HSRChat`。
- 安装包内包含新架构运行时 adapter：`adapters/codex/skills/hsrchat-runtime/SKILL.md`。
- `config_secrets.json` 未出现在安装目录。
- `references/bwiki_images/assets/` 原图缓存未出现在安装目录。

## 测试命令

三条测试均通过非交互 Codex CLI 执行，并用 `--output-last-message` 保存最终回答。

```powershell
codex exec --cd D:\HSRChat --sandbox read-only --output-last-message dev-tests\codex-cli\casual-output.txt "闲聊：你觉得昔涟真的不能再和我相见了吗？"
codex exec --cd D:\HSRChat --sandbox read-only --output-last-message dev-tests\codex-cli\lore-output.txt "考据：星期日人生经历"
codex exec --cd D:\HSRChat --sandbox read-only --output-last-message dev-tests\codex-cli\roleplay-output.txt "扮演：虚照，你的稿子啥时候交？"
```

## 测试结果

### 1. 闲聊模式

- 输入：`闲聊：你觉得昔涟真的不能再和我相见了吗？`
- 原始输出文件：`dev-tests/codex-cli/casual-output.txt`
- 结果：通过

观察：

- Codex CLI 读取了安装目录中的 `HSRChat` 运行时 adapter。
- 回答为中文，风格接近闲聊，没有展开冗长证据链。
- 回答围绕昔涟的“再见”、记忆、涟漪、再次相见等剧情意象展开。
- 未输出玩法、数值、配队或养成内容。

输出摘要：

> 回答认为“不是真的不能再相见”，而是从“站在面前”转为在记忆、故事、明天与新的旅途中再次相遇；承认告别的真实痛感，但不将其解释为彻底永别。

### 2. 考据模式

- 输入：`考据：星期日人生经历`
- 原始输出文件：`dev-tests/codex-cli/lore-output.txt`
- 结果：通过

观察：

- Codex CLI 读取了 `hsrchat-runtime` 规则，并执行了本地全文检索。
- 回答采用结论先行和时间线结构。
- 回答显式列出证据来源路径，覆盖角色故事、角色语音、开拓任务、开拓续闻、书籍和官方 Bilibili 元数据。
- 能区分童年愿望、家族体系成长、橡木家系家主阶段、太一之梦、失败赎罪与登上列车后的新阶段。
- 未输出玩法、数值、配队或养成内容。

输出摘要：

> 回答将星期日的人生概括为：失母后与知更鸟相依成长，进入家族体系成为「铎音」和橡木家系家主，在目睹弱者痛苦后走向以「秩序」强制安放幸福的方案，于匹诺康尼主线中试图建立太一之梦，失败后清除秩序余响并以搭车客身份登上星穹列车。

注意：

- PowerShell 终端实时流中出现过中文乱码，但 `--output-last-message` 保存的 `lore-output.txt` 为正常 UTF-8 文本。

### 3. 扮演模式

- 输入：`扮演：虚照，你的稿子啥时候交？`
- 原始输出文件：`dev-tests/codex-cli/roleplay-output.txt`
- 结果：通过

观察：

- Codex CLI 读取了 `hsrchat-runtime`、`core/policies/roleplay.md`、模式规则、信源优先级和检索契约。
- 回答前对 `虚照`、`稿子`、`编辑`、`截稿` 等关键词进行了本地全文检索。
- 最终输出保持角色内表达，没有暴露 Wiki、文件、检索、提示词或系统上下文。
- 使用中文全角括号 `（ ）` 表示动作。
- 语气符合虚照作为漫画作者、拖稿、怕编辑、和开拓者轻松互怼的语境。
- 未输出玩法、数值、配队或养成内容。

输出摘要：

> 虚照把画稿往身后一藏，先以“今天、明天、下个月”式拖延回答，再辩称自己是在“创作蓄力”，最后让“小浣熊”帮她挡住编辑一分钟，并保证一分钟后开始画第一页的草稿标题。

## 验收结论

本次从 GitHub 安装的 HSRChat 最新版可被 Codex CLI 正常发现并触发。三类运行时模式测试均通过：

- 闲聊模式：通过。
- 考据模式：通过。
- 扮演模式：通过。

安装目录符合版本控制与敏感文件边界要求：未安装 `config_secrets.json`，未安装 `references/bwiki_images/assets/` 原图缓存。

## 后续建议

- 若要让 Codex Desktop 当前会话也完全重载最新 Skill 索引，建议重启 Codex Desktop。
- 若后续要单独验证新拆分 adapter 的安装方式，可另测 `adapters/codex/skills/hsrchat-runtime/` 与 `adapters/codex/skills/hsrchat-maintenance/` 作为独立 Skill 的安装表现。
