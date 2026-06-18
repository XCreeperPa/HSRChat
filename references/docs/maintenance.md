# HSRChat 维护与脚本说明

本文收纳 README 中较技术性的维护内容。日常使用 HSRChat 不需要运行这些脚本；只有在更新本地语料、图片索引或官方视频元数据时才需要阅读。

在执行任何同步前，先阅读：

- `references/docs/devops.md`
- `references/docs/data_sources.md`

并确认工作区干净：

```bash
git status
```

---

## 1. 查询 Wiki 分类

脚本：

```bash
python scripts/list_wiki_categories.py
```

用途：

- 查询星穹铁道 BWiki 当前全部页面分类。
- 只向终端输出，不写入或修改本地文件。

---

## 2. Wiki 设定文本同步

脚本：

```bash
python scripts/sync_wiki.py
```

测试模式：

```bash
python scripts/sync_wiki.py --test
```

核心机制：

- 读取 `config.json` 中的 `wiki.categories`。
- 基于 `references/wiki/state.json` 做增量同步。
- 每个页面按线上 API 时间戳判断是否需要更新。
- 自动清理 `references/wiki/` 下不在配置内的多余分类目录。
- `--test` 模式下每个分类最多同步 10 个页面。

---

## 3. B站官方视频元数据同步

脚本：

```bash
python scripts/sync_bilibili.py
```

测试模式：

```bash
python scripts/sync_bilibili.py --test
```

敏感凭证：

如需登录态请求，可在根目录创建被 `.gitignore` 排除的 `config_secrets.json`：

```json
{
  "sessdata": "您的 SESSDATA Cookie 值"
}
```

注意：

- 不得把 `sessdata`、Cookie 或其他鉴权信息写入受版本控制的脚本。
- `config_secrets.json` 只保留在本地。
- 视频元数据输出到 `references/bilibili/{分类名称}/`。
- 文件名会去除标题里的《崩坏：星穹铁道》前缀。

---

## 4. BWiki 图片信源

图片流水线用于从 Wiki 文本和角色页规则中识别高价值图片，生成索引、下载原图缓存，并压缩出 WebP 参考图。

估算模式，不下载：

```bash
python scripts/sync_bwiki_images.py
```

下载模式：

```bash
python scripts/sync_bwiki_images.py --download
```

压缩模式：

```bash
python scripts/compress_bwiki_images.py --overwrite
```

一键全量重建：

```bash
python scripts/run_bwiki_image_pipeline.py --clean
```

版本控制边界：

- 可以提交：`references/bwiki_images/index.json`
- 可以提交：`references/bwiki_images/estimate_report.json`
- 可以提交：`references/bwiki_images/compressed_index.json`
- 可以提交：`references/bwiki_images/assets_webp/`
- 不得提交：`references/bwiki_images/assets/`

项目固定规则：图片二进制只提交轻量 WebP，不提交原图缓存。

---

## 5. 图片文本描述与人工审核

图片文本描述用于让非多模态模型快速读取 `assets_webp/` 下图片的可见元素。正式索引文件为：

```text
references/bwiki_images/vision_index/assets.jsonl
```

当前版本包含 208 张 WebP 参考图的审核通过版中文描述。每行是一个 JSON 对象，使用中文字段，保留 `图片路径` 作为定位字段，其余字段只描述图片中可见元素，不重复 Wiki 来源、文件名推测或页面元数据。

本地审核 GUI：

```bash
python scripts/review_bwiki_vision_json.py --port 8765
```

打开：

```text
http://127.0.0.1:8765/
```

审核 GUI 会自动合入以下 LLM 输出来源：

```text
references/bwiki_images/vision_index/assets.jsonl
references/bwiki_images/vision_jobs/outputs/result_*.jsonl
references/bwiki_images/vision_jobs/outputs/full_result_*.jsonl
references/bwiki_images/vision_jobs/*merged_assets*.jsonl
```

人工审核状态写入：

```text
references/bwiki_images/vision_review/review_state.json
```

该文件属于本地审核草稿，默认不提交。审核通过或修订通过的结果会导出到：

```text
references/bwiki_images/vision_review/reviewed_assets.jsonl
```

正式发布图片文本描述版本时，将审核通过导出同步到主索引：

```powershell
Copy-Item references\bwiki_images\vision_review\reviewed_assets.jsonl references\bwiki_images\vision_index\assets.jsonl -Force
```

并发生成或试水过程文件位于：

```text
references/bwiki_images/vision_jobs/
```

该目录只作为临时任务区，不提交。可使用以下脚本生成试水分片和合并校验 worker 输出：

```bash
python scripts/bwiki_vision_make_trial_jobs.py --limit-per-category 10 --shard-size 13 --prefix trial
python scripts/bwiki_vision_merge_jobs.py --manifest references/bwiki_images/vision_jobs/full_manifest.jsonl --outputs-dir references/bwiki_images/vision_jobs/outputs --pattern full_result_*.jsonl --merged references/bwiki_images/vision_jobs/full_merged_assets.jsonl --report references/bwiki_images/vision_jobs/full_validation_report.json
```

图片文本描述必须遵守 HSRChat 数据边界：

- 只描述图片中可见的主体、服装、物件、环境、构图、色彩、文字等元素。
- 不写战斗玩法、角色数值、技能机制、配队、光锥、遗器等内容。
- 不把文件名、BWiki 页面来源或上下文推测混入视觉描述正文。
- 对遮挡、模糊、小字或不可辨认区域使用“无法确认”，不要脑补。
- 角色立绘的服装描述必须具体到上衣、外套、腰部、下装、腿脚、配饰等可见结构，避免空泛标签。

---

## 6. 同步后的审计

同步后先检查：

```bash
git status
git diff
```

重点确认：

- 没有空文件或异常截断文件。
- 没有机密配置被加入 Git。
- 没有原图缓存进入暂存区。
- `state.json` 与实际文件变更一致。
- `references/bwiki_images/vision_index/assets.jsonl` 能解析为 JSONL，且图片路径无重复、无缺失文件、无空视觉描述。

如果发现坏数据，按 `references/docs/devops.md` 中的回滚命令恢复。

