# HSRChat 安装指南

本文记录 HSRChat 在不同 Agent / CLI 环境中的安装方式。安装后通常需要重启对应客户端，让 Skill 索引重新加载。

---

## 1. Codex CLI / Codex Desktop

Codex 会从用户目录下的 `skills` 目录发现本地 Skill。Windows 默认路径通常是：

```text
C:\Users\<用户名>\.codex\skills
```

PowerShell 安装示例：

```powershell
git clone https://github.com/XCreeperPa/HSRChat.git
$dest = "$HOME\.codex\skills\HSRChat"
Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force .\HSRChat $dest
Remove-Item -Recurse -Force "$dest\.git" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$dest\config_secrets.json" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$dest\references\bwiki_images\assets" -ErrorAction SilentlyContinue
```

说明：

- `.git` 不需要放进 Codex 的 skill 安装目录。
- `config_secrets.json` 是本地敏感配置，不能安装或提交。
- `references/bwiki_images/assets/` 是原图缓存，体积大且不入 Git；安装 Skill 时应移除。
- `references/bwiki_images/assets_webp/` 是轻量 WebP 参考图，可以保留。

安装完成后重启 Codex。

可以用非交互 CLI 做一个快速测试：

```powershell
codex exec --skip-git-repo-check --sandbox read-only "介绍星穹铁道的看板娘"
```

如果日志中出现 HSRChat 被读取，且回答聚焦三月七、帕姆、星穹列车等剧情/角色内容，说明安装成功。

---

## 2. Gemini CLI

如果使用支持 Agent Skill 动态安装的 Gemini CLI，可以从仓库 URL 安装：

全局安装：

```bash
gemini skills install https://github.com/XCreeperPa/HSRChat.git
```

项目本地安装：

```bash
gemini skills install https://github.com/XCreeperPa/HSRChat.git --scope workspace
```

安装后重新打开会话。

---

## 3. 通用 Agent / RAG 知识库

如果你的 Agent 不支持 Skills 规范，也可以把 HSRChat 当成本地剧情语料库使用：

```bash
git clone https://github.com/XCreeperPa/HSRChat.git
```

常用挂载目录：

- `references/wiki/`：Wiki 剧情、角色、书籍、任务、语音文本。
- `references/bilibili/`：官方视频元数据。
- `references/bwiki_images/index.json`：图片索引。
- `references/bwiki_images/assets_webp/`：轻量 WebP 参考图。

不要把 `references/bwiki_images/assets/` 原图缓存作为默认知识库输入；它体积大，且不属于 Git 追踪数据。

---

## 4. 验证要点

安装后建议测试三类问题：

```text
介绍星穹铁道的看板娘
```

预期：闲聊模式，简洁介绍三月七与帕姆，不主动展开玩法属性、技能或配队。

```text
赏析三月七在二相乐园的剧情
```

预期：考据 / 赏析风格，能结合本地任务文本和角色线索，不把猜测写成事实。

```text
请你扮演三月七，回答：你觉得苍天航路绒绒号怎么样？
```

预期：扮演模式，读取 `roleplay.md`，使用中文全角括号表达动作或思想，括号外为三月七说出口的话。
