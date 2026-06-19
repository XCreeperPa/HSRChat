# 检索契约

本文定义 HSRChat 各 adapter 应如何检索和组织证据。

## 输入

一次运行时请求可能包含：

- 用户问题或扮演回合。
- 模式：闲聊、考据或扮演。
- 实体提示：角色、派系、地点、星神、命途、任务、书籍、视频或图片。
- 用户给出的剧透边界。

## 检索范围

默认本地证据位于：

- `references/wiki/`
- `references/bilibili/`
- `references/bwiki_images/index.json`
- `references/bwiki_images/assets_webp/`
- `references/bwiki_images/vision_index/assets/`
- `references/bwiki_images/vision_index/assets.jsonl`

除非用户明确要求外部验证，否则不要为了本地证据检索跳出项目目录。

## 检索方法

考据和扮演语料准备应按以下步骤执行：

1. 从全文内容检索开始，不只依赖文件名。
2. 阅读最强的直接命中。
3. 提取别名、隐藏称谓、地点、组织、事件和反复出现的概念。
4. 对提取出的实体继续检索。
5. 按 `core/policies/source_priority.md` 比较信源强度。
6. 按 `core/policies/gameplay_filter.md` 过滤玩法内容。

## 输出或内部证据格式

检索结果应至少包含：

- 信源路径或媒体标识。
- 信源类型。
- 相关摘录或摘要事实。
- 必要时标注置信度和冲突。
- 当检索文本含玩法机制时，标记玩法污染。

扮演模式只在内部使用证据，不在角色台词中暴露检索细节。
