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

## 5. 同步后的审计

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

如果发现坏数据，按 `references/docs/devops.md` 中的回滚命令恢复。

