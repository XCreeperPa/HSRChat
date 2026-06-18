#!/usr/bin/env python3
"""Local GUI for reviewing BWiki image description JSON.

The app is intentionally dependency-free. It serves a small browser UI for
side-by-side image review, Chinese-key JSON editing, and field-level issue
marking. Review data is written under references/bwiki_images/vision_review/
and does not modify the source image index or WebP assets.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import posixpath
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


ROOT_DIR = Path(__file__).resolve().parents[1]
BWiki_DIR = ROOT_DIR / "references" / "bwiki_images"
ASSETS_WEBP_DIR = BWiki_DIR / "assets_webp"
DEFAULT_VISION_JSONL = BWiki_DIR / "vision_index" / "assets.jsonl"
VISION_JOBS_DIR = BWiki_DIR / "vision_jobs"
REVIEW_DIR = BWiki_DIR / "vision_review"
STATE_PATH = REVIEW_DIR / "review_state.json"
APPROVED_JSONL = REVIEW_DIR / "reviewed_assets.jsonl"

IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".avif"}

STATUS_VALUES = ["未审核", "通过", "需修订", "已修订", "跳过"]
ISSUE_TYPES = ["描述不准", "缺少细节", "字段放错", "OCR错误", "过度推测", "冗余", "格式问题", "其他"]


def rel_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT_DIR).as_posix()


def safe_read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def safe_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError:
            records.append(
                {
                    "图片路径": "",
                    "解析错误": f"{path.as_posix()} 第 {line_no} 行不是合法 JSON",
                    "原始内容": stripped[:1000],
                }
            )
    return records


def is_auto_import_jsonl(path: Path) -> bool:
    """Return true for LLM output JSONL files, excluding manifests and shards."""
    name = path.name
    return name.startswith("result_") or "merged_assets" in name


def discover_vision_jsonl(primary_jsonl: Path) -> list[Path]:
    """Find all JSONL sources that should feed the review queue.

    Earlier sources are lower priority; later sources win for the same image path.
    This lets new LLM job outputs show up automatically while keeping reviewed
    edits in review_state.json as the final authority.
    """
    sources: list[Path] = []
    if primary_jsonl.exists():
        sources.append(primary_jsonl.resolve())

    if VISION_JOBS_DIR.exists():
        candidates = [
            path.resolve()
            for path in VISION_JOBS_DIR.rglob("*.jsonl")
            if path.is_file() and is_auto_import_jsonl(path)
        ]
        candidates.sort(key=lambda path: (path.stat().st_mtime, path.as_posix()))
        sources.extend(candidates)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for source in sources:
        if source not in seen:
            deduped.append(source)
            seen.add(source)
    return deduped


def record_has_visual_content(record: dict) -> bool:
    """A path-only manifest row should not count as an LLM description."""
    ignored_keys = {"图片路径", "图片类别", "图片标题", "path", "image"}
    for key, value in record.items():
        if key in ignored_keys:
            continue
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, dict)) and value:
            return True
        if value not in ("", None, [], {}):
            return True
    return False


def load_vision_records(primary_jsonl: Path) -> tuple[dict[str, dict], list[str]]:
    """Load reviewable LLM descriptions from the primary file and auto imports."""
    records_by_path: dict[str, dict] = {}
    sources = discover_vision_jsonl(primary_jsonl)
    for source in sources:
        for record in load_jsonl(source):
            path = image_path_from_record(record)
            if path and record_has_visual_content(record):
                records_by_path[path.replace("\\", "/")] = record
    return records_by_path, [rel_path(source) for source in sources]


def image_path_from_record(record: dict) -> str:
    if isinstance(record.get("图片路径"), str):
        return record["图片路径"]
    image = record.get("image")
    if isinstance(image, dict) and isinstance(image.get("path"), str):
        return image["path"]
    if isinstance(record.get("path"), str):
        return record["path"]
    return ""


def normalize_record(record: dict, image_path: str, category: str, title: str) -> dict:
    """Convert a loaded record into Chinese-key review JSON where possible."""
    if "视觉摘要" in record or "图片路径" in record:
        normalized = dict(record)
        normalized.setdefault("图片路径", image_path)
        normalized.setdefault("图片类别", category)
        normalized.setdefault("图片标题", title)
        return normalized

    # Preserve useful English-schema visual data, but expose it with Chinese keys.
    visual = record.get("visual") if isinstance(record.get("visual"), dict) else {}
    caption = record.get("caption") if isinstance(record.get("caption"), dict) else {}
    elements = record.get("elements") if isinstance(record.get("elements"), dict) else {}

    return {
        "图片路径": image_path,
        "图片类别": category,
        "图片标题": title,
        "图片类型": record.get("type") or visual.get("scene_type") or "",
        "视觉摘要": visual.get("short_caption") or caption.get("short") or record.get("summary") or "",
        "主体": visual.get("subjects") or elements.get("person") or {},
        "服装": record.get("outfit") or {},
        "人物": visual.get("visible_characters") or record.get("people") or [],
        "场景环境": record.get("environment") or record.get("setting") or "",
        "物件": visual.get("visible_objects") or elements.get("objects") or record.get("objects") or [],
        "构图": visual.get("composition") or record.get("composition") or "",
        "色彩质感": record.get("palette_texture") or "",
        "画面文字": record.get("ocr") or "",
    }


def empty_review_record(image_path: str, category: str, title: str) -> dict:
    return {
        "图片路径": image_path,
        "图片类别": category,
        "图片标题": title,
        "图片类型": "",
        "视觉摘要": "",
        "主体": {},
        "服装": {},
        "人物": [],
        "场景环境": "",
        "物件": [],
        "构图": "",
        "色彩质感": "",
        "画面文字": "",
    }


def scan_images() -> list[dict]:
    items: list[dict] = []
    if not ASSETS_WEBP_DIR.exists():
        return items
    for path in sorted(ASSETS_WEBP_DIR.rglob("*"), key=lambda p: rel_path(p)):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        image_rel = rel_path(path)
        try:
            category = path.relative_to(ASSETS_WEBP_DIR).parts[0]
        except IndexError:
            category = ""
        items.append(
            {
                "path": image_rel,
                "category": category,
                "title": path.stem,
            }
        )
    return items


def build_items(vision_jsonl: Path) -> list[dict]:
    image_items = scan_images()
    records_by_path, _ = load_vision_records(vision_jsonl)

    state = safe_read_json(STATE_PATH, {})
    result: list[dict] = []
    for idx, image in enumerate(image_items):
        path = image["path"]
        status = state.get(path, {}).get("status", "未审核")
        issues_count = len(state.get(path, {}).get("issues", []))
        has_record = path in records_by_path
        result.append(
            {
                "index": idx,
                "path": path,
                "category": image["category"],
                "title": image["title"],
                "status": status,
                "issues_count": issues_count,
                "has_description": has_record,
            }
        )
    return result


def review_summary(vision_jsonl: Path) -> dict:
    records_by_path, sources = load_vision_records(vision_jsonl)
    return {
        "vision_sources": sources,
        "descriptions": len(records_by_path),
        "auto_import_dir": rel_path(VISION_JOBS_DIR),
    }


def get_item(index: int, vision_jsonl: Path) -> dict:
    images = scan_images()
    if index < 0 or index >= len(images):
        raise IndexError("item index out of range")

    image = images[index]
    image_path = image["path"]
    records_by_path, vision_sources = load_vision_records(vision_jsonl)
    loaded = records_by_path.get(image_path)
    review_state = safe_read_json(STATE_PATH, {}).get(image_path, {})

    if review_state.get("edited_json") and record_has_visual_content(review_state["edited_json"]):
        review_json = review_state["edited_json"]
    elif loaded:
        review_json = normalize_record(loaded, image_path, image["category"], image["title"])
    else:
        review_json = empty_review_record(image_path, image["category"], image["title"])

    return {
        "index": index,
        "count": len(images),
        "image": image,
        "image_url": "/image?path=" + quote(image_path),
        "review_json": review_json,
        "review_state": {
            "status": review_state.get("status", "未审核"),
            "issues": review_state.get("issues", []),
            "note": review_state.get("note", ""),
        },
        "status_values": STATUS_VALUES,
        "issue_types": ISSUE_TYPES,
        "vision_sources": vision_sources,
    }


def export_reviewed_jsonl(state: dict) -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for path in sorted(state):
        entry = state[path]
        if entry.get("status") in {"通过", "已修订"} and isinstance(entry.get("edited_json"), dict):
            lines.append(json.dumps(entry["edited_json"], ensure_ascii=False, separators=(",", ":")))
    APPROVED_JSONL.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def is_safe_workspace_path(path_text: str) -> Path | None:
    normalized = unquote(path_text).replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        return None
    candidate = (ROOT_DIR / normalized).resolve()
    try:
        candidate.relative_to(ROOT_DIR.resolve())
    except ValueError:
        return None
    return candidate


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HSRChat 图文 JSON 人工审核</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --line: #d7dce8;
      --text: #172033;
      --muted: #667085;
      --accent: #2563eb;
      --accent-2: #0f766e;
      --bad: #b42318;
      --warn: #b54708;
      --ok: #067647;
      --shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      overflow: hidden;
    }
    button, select, textarea, input {
      font: inherit;
    }
    .app {
      display: grid;
      grid-template-columns: 300px minmax(420px, 1fr) minmax(520px, 0.95fr);
      height: 100vh;
      gap: 10px;
      padding: 10px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-height: 0;
      overflow: hidden;
    }
    .sidebar {
      display: flex;
      flex-direction: column;
    }
    .toolbar {
      display: grid;
      gap: 8px;
      padding: 10px;
      border-bottom: 1px solid var(--line);
    }
    .toolbar h1 {
      margin: 0;
      font-size: 17px;
      line-height: 1.3;
    }
    .filters {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .filters.wide {
      grid-template-columns: 1fr;
    }
    .search {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 9px;
    }
    .list {
      overflow: auto;
      padding: 6px;
    }
    .item {
      border: 1px solid transparent;
      border-radius: 7px;
      padding: 8px;
      cursor: pointer;
      display: grid;
      gap: 4px;
      margin-bottom: 5px;
    }
    .item:hover { background: #eef4ff; }
    .item.active {
      border-color: var(--accent);
      background: #eaf1ff;
    }
    .item-title {
      font-size: 13px;
      font-weight: 700;
      line-height: 1.35;
      word-break: break-all;
    }
    .meta {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 12px;
    }
    .pill {
      border: 1px solid var(--line);
      background: #f8fafc;
      border-radius: 999px;
      padding: 1px 7px;
      white-space: nowrap;
    }
    .pill.ok { color: var(--ok); border-color: #abefc6; background: #ecfdf3; }
    .pill.warn { color: var(--warn); border-color: #fedf89; background: #fffaeb; }
    .pill.bad { color: var(--bad); border-color: #fecdca; background: #fef3f2; }
    .viewer {
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    .topbar {
      border-bottom: 1px solid var(--line);
      padding: 10px;
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
    }
    .topbar strong {
      font-size: 15px;
      word-break: break-all;
    }
    .nav {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .btn {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
    }
    .btn:hover { background: #f2f6ff; }
    .btn.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    .btn.good {
      background: var(--accent-2);
      border-color: var(--accent-2);
      color: #fff;
    }
    .btn.bad {
      background: var(--bad);
      border-color: var(--bad);
      color: #fff;
    }
    .image-wrap {
      min-height: 0;
      display: grid;
      place-items: center;
      background:
        linear-gradient(45deg, #e8edf5 25%, transparent 25%),
        linear-gradient(-45deg, #e8edf5 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #e8edf5 75%),
        linear-gradient(-45deg, transparent 75%, #e8edf5 75%);
      background-size: 22px 22px;
      background-position: 0 0, 0 11px, 11px -11px, -11px 0px;
      overflow: auto;
      padding: 12px;
    }
    .image-wrap.dark { background: #101828; }
    #preview {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      image-rendering: auto;
    }
    .viewer-foot {
      padding: 9px 10px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      display: flex;
      justify-content: space-between;
      gap: 10px;
      word-break: break-all;
    }
    .editor {
      display: grid;
      grid-template-rows: auto minmax(240px, 1fr) minmax(230px, 0.75fr);
    }
    .editor-head {
      padding: 10px;
      border-bottom: 1px solid var(--line);
      display: grid;
      gap: 8px;
    }
    .row {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    label { color: var(--muted); font-size: 13px; }
    select, .note-input {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 9px;
      background: #fff;
    }
    .jsonbox {
      width: 100%;
      height: 100%;
      resize: none;
      border: 0;
      border-bottom: 1px solid var(--line);
      padding: 12px;
      line-height: 1.55;
      font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei", monospace;
      font-size: 13px;
      outline: none;
      tab-size: 2;
    }
    .jsonbox.invalid { background: #fff7f7; }
    .issues {
      min-height: 0;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    .issue-head {
      padding: 10px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .issue-list {
      overflow: auto;
      padding: 8px 10px;
    }
    .field-row {
      display: grid;
      grid-template-columns: auto 1fr 112px;
      gap: 7px;
      align-items: center;
      padding: 6px 0;
      border-bottom: 1px dashed #e4e7ec;
    }
    .field-path {
      font-size: 12px;
      color: #344054;
      word-break: break-all;
    }
    .field-preview {
      grid-column: 2 / 4;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .field-note {
      grid-column: 2 / 4;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 8px;
      display: none;
    }
    .field-row.marked .field-note { display: block; }
    .field-row.marked { background: #fff8ed; }
    .status-text {
      font-size: 12px;
      color: var(--muted);
    }
    .status-text.error { color: var(--bad); }
    .status-text.ok { color: var(--ok); }
    .shortcut {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .checkline {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: var(--muted);
      font-size: 13px;
      user-select: none;
    }
    @media (max-width: 1180px) {
      .app {
        grid-template-columns: 260px 1fr;
        grid-template-rows: 52vh 48vh;
      }
      .editor { grid-column: 1 / 3; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="panel sidebar">
      <div class="toolbar">
        <h1>图文 JSON 人工审核</h1>
        <input id="search" class="search" placeholder="搜索文件名 / 分类 / 状态" />
        <div class="filters">
          <select id="categoryFilter"><option value="">全部分类</option></select>
          <select id="statusFilter"><option value="">全部状态</option></select>
        </div>
        <div class="filters wide">
          <select id="descriptionFilter">
            <option value="">全部描述状态</option>
            <option value="described">已有 LLM 描述</option>
            <option value="undescribed">未被 LLM 描述</option>
          </select>
        </div>
        <div class="meta">
          <span id="countLabel">载入中...</span>
          <span id="sourceLabel"></span>
        </div>
        <div class="shortcut">单键阅卷：A 通过并下一张；R 需修订并下一张；S 保存并下一张；D 只保存；N/→ 下一张；P/← 上一张；U 只看未描述；L 只看已描述；0 全部描述状态；B 切换底色。</div>
      </div>
      <div id="list" class="list"></div>
    </aside>

    <section class="panel viewer">
      <div class="topbar">
        <strong id="title">未选择图片</strong>
        <div class="nav">
          <button class="btn" id="prevBtn">上一张</button>
          <button class="btn" id="nextBtn">下一张</button>
          <button class="btn" id="bgBtn">切换底色</button>
        </div>
      </div>
      <div id="imageWrap" class="image-wrap">
        <img id="preview" alt="待审核图片" />
      </div>
      <div class="viewer-foot">
        <span id="pathLabel"></span>
        <span id="indexLabel"></span>
      </div>
    </section>

    <section class="panel editor">
      <div class="editor-head">
        <div class="row">
          <label for="reviewStatus">审核状态</label>
          <select id="reviewStatus"></select>
          <button class="btn primary" id="saveBtn">保存并下一张</button>
          <button class="btn" id="saveStayBtn">只保存</button>
          <button class="btn good" id="passBtn">快速通过</button>
          <button class="btn bad" id="reviseBtn">需修订</button>
          <button class="btn good" id="formatBtn">格式化 JSON</button>
          <span id="saveState" class="status-text"></span>
        </div>
        <div class="row">
          <label class="checkline"><input id="autoNext" type="checkbox" checked />保存后自动下一张</label>
          <label for="reviewNote">整图备注</label>
          <input id="reviewNote" class="note-input" placeholder="例如：服装细节不足、OCR 需要复核" style="flex:1" />
        </div>
      </div>
      <textarea id="jsonEditor" class="jsonbox" spellcheck="false"></textarea>
      <div class="issues">
        <div class="issue-head">
          <strong>错误位点标注</strong>
          <button class="btn" id="refreshFieldsBtn">从 JSON 刷新字段</button>
        </div>
        <div id="fieldList" class="issue-list"></div>
      </div>
    </section>
  </div>

  <script>
    const ISSUE_TYPES = ["描述不准", "缺少细节", "字段放错", "OCR错误", "过度推测", "冗余", "格式问题", "其他"];
    let items = [];
    let filtered = [];
    let currentIndex = 0;
    let currentItem = null;
    let fieldIssueState = new Map();

    const $ = (id) => document.getElementById(id);

    function statusClass(status) {
      if (status === "通过" || status === "已修订") return "ok";
      if (status === "需修订") return "bad";
      if (status === "跳过") return "warn";
      return "";
    }

    async function api(path, options) {
      const res = await fetch(path, options);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
      }
      return res.json();
    }

    async function loadList() {
      const data = await api("/api/list");
      items = data.items;
      setupFilters(data);
      applyFilters();
      if (items.length) await loadItem(0);
    }

    function setupFilters(data) {
      const categories = [...new Set(items.map(x => x.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN"));
      $("categoryFilter").innerHTML = '<option value="">全部分类</option>' + categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
      $("statusFilter").innerHTML = '<option value="">全部状态</option>' + data.status_values.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
      const summary = data.review_summary || {};
      $("sourceLabel").textContent = `LLM 描述 ${summary.descriptions || 0} 条 / 来源 ${(summary.vision_sources || []).length} 个`;
      $("sourceLabel").title = (summary.vision_sources || []).join("\n");
    }

    function applyFilters() {
      const q = $("search").value.trim().toLowerCase();
      const c = $("categoryFilter").value;
      const s = $("statusFilter").value;
      const d = $("descriptionFilter").value;
      filtered = items.filter(item => {
        const text = `${item.path} ${item.category} ${item.title} ${item.status}`.toLowerCase();
        const descOk = !d || (d === "described" && item.has_description) || (d === "undescribed" && !item.has_description);
        return (!q || text.includes(q)) && (!c || item.category === c) && (!s || item.status === s) && descOk;
      });
      renderList();
    }

    function renderList() {
      $("countLabel").textContent = `${filtered.length} / ${items.length} 张`;
      $("list").innerHTML = filtered.map(item => {
        const desc = item.has_description ? "有 LLM 描述" : "未被 LLM 描述";
        const issue = item.issues_count ? ` · ${item.issues_count} 处错误` : "";
        return `
          <div class="item ${item.index === currentIndex ? "active" : ""}" data-index="${item.index}">
            <div class="item-title">${escapeHtml(item.title)}</div>
            <div class="meta">
              <span class="pill">${escapeHtml(item.category)}</span>
              <span class="pill ${statusClass(item.status)}">${escapeHtml(item.status)}</span>
              <span>${desc}${issue}</span>
            </div>
          </div>
        `;
      }).join("");
      document.querySelectorAll(".item").forEach(el => {
        el.addEventListener("click", () => loadItem(Number(el.dataset.index)));
      });
    }

    async function loadItem(index) {
      const data = await api(`/api/item?index=${index}`);
      currentIndex = data.index;
      currentItem = data;
      fieldIssueState = new Map();
      for (const issue of data.review_state.issues || []) {
        fieldIssueState.set(issue.字段路径, issue);
      }

      $("title").textContent = data.image.title;
      $("pathLabel").textContent = data.image.path;
      $("indexLabel").textContent = `${data.index + 1} / ${data.count}`;
      $("preview").src = data.image_url;
      $("reviewStatus").innerHTML = data.status_values.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
      $("reviewStatus").value = data.review_state.status || "未审核";
      $("reviewNote").value = data.review_state.note || "";
      $("jsonEditor").value = JSON.stringify(data.review_json, null, 2);
      $("jsonEditor").classList.remove("invalid");
      $("saveState").textContent = "";
      renderFields();
      renderList();
    }

    function parseEditor() {
      try {
        const parsed = JSON.parse($("jsonEditor").value);
        $("jsonEditor").classList.remove("invalid");
        return parsed;
      } catch (err) {
        $("jsonEditor").classList.add("invalid");
        throw err;
      }
    }

    function flatten(value, prefix = "") {
      const out = [];
      if (value === null || typeof value !== "object") {
        out.push({ path: prefix || "根", preview: stringifyPreview(value) });
        return out;
      }
      if (Array.isArray(value)) {
        out.push({ path: prefix || "根", preview: `数组(${value.length})` });
        value.forEach((v, i) => out.push(...flatten(v, `${prefix}[${i}]`)));
        return out;
      }
      const keys = Object.keys(value);
      if (prefix) out.push({ path: prefix, preview: `对象(${keys.length})` });
      for (const key of keys) {
        const childPath = prefix ? `${prefix}.${key}` : key;
        out.push(...flatten(value[key], childPath));
      }
      return out;
    }

    function stringifyPreview(value) {
      if (value === null) return "null";
      if (typeof value === "string") return value || "空字符串";
      if (typeof value === "number" || typeof value === "boolean") return String(value);
      return JSON.stringify(value);
    }

    function renderFields() {
      let parsed;
      try {
        parsed = parseEditor();
      } catch (err) {
        $("fieldList").innerHTML = `<div class="status-text error">JSON 格式错误：${escapeHtml(err.message)}</div>`;
        return;
      }
      const fields = flatten(parsed).filter(f => f.path !== "根");
      $("fieldList").innerHTML = fields.map(field => {
        const issue = fieldIssueState.get(field.path);
        const marked = Boolean(issue);
        const type = issue?.问题类型 || ISSUE_TYPES[0];
        const note = issue?.说明 || "";
        return `
          <div class="field-row ${marked ? "marked" : ""}" data-path="${escapeHtml(field.path)}">
            <input type="checkbox" ${marked ? "checked" : ""} title="标记该字段有问题" />
            <div class="field-path">${escapeHtml(field.path)}</div>
            <select>${ISSUE_TYPES.map(t => `<option ${t === type ? "selected" : ""}>${escapeHtml(t)}</option>`).join("")}</select>
            <div class="field-preview">${escapeHtml(field.preview)}</div>
            <input class="field-note" value="${escapeHtml(note)}" placeholder="说明该字段错在哪里" />
          </div>
        `;
      }).join("");

      document.querySelectorAll(".field-row").forEach(row => {
        const path = row.dataset.path;
        const checkbox = row.querySelector("input[type='checkbox']");
        const select = row.querySelector("select");
        const note = row.querySelector(".field-note");
        const sync = () => {
          if (checkbox.checked) {
            row.classList.add("marked");
            fieldIssueState.set(path, {
              "字段路径": path,
              "问题类型": select.value,
              "说明": note.value,
              "原值预览": row.querySelector(".field-preview").textContent
            });
          } else {
            row.classList.remove("marked");
            fieldIssueState.delete(path);
          }
        };
        checkbox.addEventListener("change", sync);
        select.addEventListener("change", sync);
        note.addEventListener("input", sync);
      });
    }

    function nextFilteredIndex() {
      const pos = filtered.findIndex(x => x.index === currentIndex);
      if (pos >= 0 && pos < filtered.length - 1) return filtered[pos + 1].index;
      if (filtered.length > 0) return filtered[Math.max(0, filtered.length - 1)].index;
      return currentIndex;
    }

    async function saveReview(options = {}) {
      const autoNext = options.autoNext ?? $("autoNext").checked;
      $("saveState").textContent = "";
      $("saveState").className = "status-text";
      let edited;
      try {
        edited = parseEditor();
      } catch (err) {
        $("saveState").textContent = "JSON 格式错误，未保存";
        $("saveState").classList.add("error");
        return;
      }
      const issues = Array.from(fieldIssueState.values());
      const payload = {
        path: currentItem.image.path,
        status: $("reviewStatus").value,
        note: $("reviewNote").value,
        edited_json: edited,
        issues
      };
      const result = await api("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      $("saveState").textContent = `已保存：${result.saved_at}`;
      $("saveState").classList.add("ok");
      const item = items.find(x => x.path === currentItem.image.path);
      if (item) {
        item.status = payload.status;
        item.issues_count = issues.length;
        item.has_description = true;
      }
      applyFilters();
      if (autoNext) {
        const nextIndex = nextFilteredIndex();
        if (nextIndex !== currentIndex) await loadItem(nextIndex);
      }
    }

    function escapeHtml(text) {
      return String(text ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    $("search").addEventListener("input", applyFilters);
    $("categoryFilter").addEventListener("change", applyFilters);
    $("statusFilter").addEventListener("change", applyFilters);
    $("descriptionFilter").addEventListener("change", applyFilters);
    $("prevBtn").addEventListener("click", () => {
      const pos = filtered.findIndex(x => x.index === currentIndex);
      if (pos > 0) loadItem(filtered[pos - 1].index);
    });
    $("nextBtn").addEventListener("click", () => {
      const pos = filtered.findIndex(x => x.index === currentIndex);
      if (pos >= 0 && pos < filtered.length - 1) loadItem(filtered[pos + 1].index);
    });
    $("bgBtn").addEventListener("click", () => $("imageWrap").classList.toggle("dark"));
    $("saveBtn").addEventListener("click", () => saveReview({ autoNext: true }));
    $("saveStayBtn").addEventListener("click", () => saveReview({ autoNext: false }));
    $("passBtn").addEventListener("click", () => {
      $("reviewStatus").value = "通过";
      fieldIssueState.clear();
      renderFields();
      saveReview({ autoNext: true });
    });
    $("reviseBtn").addEventListener("click", () => {
      $("reviewStatus").value = "需修订";
      saveReview({ autoNext: true });
    });
    $("formatBtn").addEventListener("click", () => {
      const parsed = parseEditor();
      $("jsonEditor").value = JSON.stringify(parsed, null, 2);
      renderFields();
    });
    $("refreshFieldsBtn").addEventListener("click", renderFields);
    $("jsonEditor").addEventListener("blur", () => {
      try { renderFields(); } catch (_) {}
    });
    function isEditingText(event) {
      const tag = event.target?.tagName;
      return tag === "TEXTAREA" || tag === "INPUT" || event.target?.isContentEditable;
    }

    function moveBy(delta) {
      const pos = filtered.findIndex(x => x.index === currentIndex);
      const nextPos = pos + delta;
      if (nextPos >= 0 && nextPos < filtered.length) loadItem(filtered[nextPos].index);
    }

    function setDescriptionFilter(value) {
      $("descriptionFilter").value = value;
      applyFilters();
      if (filtered.length) loadItem(filtered[0].index);
    }

    document.addEventListener("keydown", (event) => {
      if (isEditingText(event)) {
        if (event.ctrlKey && event.key === "Enter") {
          event.preventDefault();
          saveReview({ autoNext: true });
        }
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "a") {
        event.preventDefault();
        $("reviewStatus").value = "通过";
        fieldIssueState.clear();
        renderFields();
        saveReview({ autoNext: true });
      } else if (key === "r") {
        event.preventDefault();
        $("reviewStatus").value = "需修订";
        saveReview({ autoNext: true });
      } else if (key === "s") {
        event.preventDefault();
        saveReview({ autoNext: true });
      } else if (key === "d") {
        event.preventDefault();
        saveReview({ autoNext: false });
      } else if (key === "n" || event.key === "ArrowRight") {
        event.preventDefault();
        moveBy(1);
      } else if (key === "p" || event.key === "ArrowLeft") {
        event.preventDefault();
        moveBy(-1);
      } else if (key === "u") {
        event.preventDefault();
        setDescriptionFilter("undescribed");
      } else if (key === "l") {
        event.preventDefault();
        setDescriptionFilter("described");
      } else if (key === "0") {
        event.preventDefault();
        setDescriptionFilter("");
      } else if (key === "b") {
        event.preventDefault();
        $("imageWrap").classList.toggle("dark");
      } else if (event.ctrlKey && event.key === "Enter") {
        event.preventDefault();
        saveReview({ autoNext: true });
      } else if (event.altKey && event.key === "Enter") {
        event.preventDefault();
        $("reviewStatus").value = "通过";
        fieldIssueState.clear();
        renderFields();
        saveReview({ autoNext: true });
      } else if (event.altKey && event.key.toLowerCase() === "r") {
        event.preventDefault();
        $("reviewStatus").value = "需修订";
        saveReview({ autoNext: true });
      } else if (event.altKey && event.key === "ArrowRight") {
        event.preventDefault();
        moveBy(1);
      } else if (event.altKey && event.key === "ArrowLeft") {
        event.preventDefault();
        moveBy(-1);
      }
    });

    loadList().catch(err => {
      $("countLabel").textContent = "载入失败";
      $("list").innerHTML = `<div class="status-text error">${escapeHtml(err.message)}</div>`;
    });
  </script>
</body>
</html>
"""


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "HSRChatVisionReview/1.0"

    @property
    def vision_jsonl(self) -> Path:
        return self.server.vision_jsonl  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:
        message = fmt % args
        sys.stderr.write(f"[review-ui] {self.address_string()} {message}\n")

    def send_json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self.send_text(HTML)
            elif parsed.path == "/api/list":
                self.send_json(
                    {
                        "items": build_items(self.vision_jsonl),
                        "status_values": STATUS_VALUES,
                        "review_summary": review_summary(self.vision_jsonl),
                    }
                )
            elif parsed.path == "/api/item":
                qs = parse_qs(parsed.query)
                index = int(qs.get("index", ["0"])[0])
                self.send_json(get_item(index, self.vision_jsonl))
            elif parsed.path == "/image":
                self.serve_image(parsed.query)
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # noqa: BLE001 - local GUI should surface readable errors.
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path != "/api/save":
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            image_path = str(payload.get("path", "")).replace("\\", "/")
            if not image_path:
                self.send_json({"error": "missing path"}, HTTPStatus.BAD_REQUEST)
                return
            if not isinstance(payload.get("edited_json"), dict):
                self.send_json({"error": "edited_json must be an object"}, HTTPStatus.BAD_REQUEST)
                return

            state = safe_read_json(STATE_PATH, {})
            saved_at = __import__("datetime").datetime.now().isoformat(timespec="seconds")
            state[image_path] = {
                "status": payload.get("status", "未审核"),
                "note": payload.get("note", ""),
                "edited_json": payload["edited_json"],
                "issues": payload.get("issues", []),
                "saved_at": saved_at,
            }
            safe_write_json(STATE_PATH, state)
            export_reviewed_jsonl(state)
            self.send_json({"ok": True, "saved_at": saved_at, "state_path": rel_path(STATE_PATH)})
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_image(self, query: str) -> None:
        qs = parse_qs(query)
        path_text = qs.get("path", [""])[0]
        candidate = is_safe_workspace_path(path_text)
        if candidate is None or not candidate.exists() or not candidate.is_file():
            self.send_json({"error": "image not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            candidate.relative_to(ASSETS_WEBP_DIR.resolve())
        except ValueError:
            self.send_json({"error": "image outside assets_webp"}, HTTPStatus.FORBIDDEN)
            return

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the HSRChat BWiki image JSON review GUI.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="Bind port. Default: 8765")
    parser.add_argument(
        "--jsonl",
        default=str(DEFAULT_VISION_JSONL),
        help="Vision description JSONL to review. If missing, the UI uses empty Chinese-key templates.",
    )
    args = parser.parse_args()

    if not ASSETS_WEBP_DIR.exists():
        print(f"assets_webp directory not found: {ASSETS_WEBP_DIR}", file=sys.stderr)
        return 2

    vision_jsonl = (ROOT_DIR / args.jsonl).resolve() if not os.path.isabs(args.jsonl) else Path(args.jsonl).resolve()
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        safe_write_json(STATE_PATH, {})

    server = ThreadingHTTPServer((args.host, args.port), ReviewHandler)
    server.vision_jsonl = vision_jsonl  # type: ignore[attr-defined]

    url = f"http://{args.host}:{args.port}/"
    print(f"HSRChat image JSON review GUI: {url}")
    print(f"Assets: {ASSETS_WEBP_DIR}")
    print(f"Vision JSONL: {vision_jsonl} ({'found' if vision_jsonl.exists() else 'not found; using empty templates'})")
    print("Auto-import JSONL sources:")
    for source in discover_vision_jsonl(vision_jsonl):
        print(f"  - {source}")
    print(f"Review state: {STATE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
