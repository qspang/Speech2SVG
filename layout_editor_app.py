"""
Layout Editor App
=================

交互式微调 enhanced_video.html 中 SVG / t2svg 浮层位置，并同步回写
enhanced_video.html 与 temp_analysis/layout_positions.txt。
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_file


LAYOUT_CANVAS_W = 1920.0
LAYOUT_CANVAS_H = 1080.0
T2SVG_SCALE = 1.30
EDGE_MARGIN_X = 1.8
EDGE_MARGIN_Y = 2.0

DEFAULT_PROJECT_ROOT = Path("/home/ubuntu/sysu/svgagent/video_enhance/enhanced_videos")

app = Flask(__name__)


def list_projects(base_dir: Path = DEFAULT_PROJECT_ROOT) -> List[Dict[str, str]]:
    items = []
    if not base_dir.exists():
        return items
    for html_path in sorted(base_dir.rglob("enhanced_video.html")):
        rel = html_path.relative_to(base_dir)
        items.append(
            {
                "name": rel.parts[0] if rel.parts else html_path.stem,
                "html_path": str(html_path),
            }
        )
    return items


def resolve_html_path(raw_path: str) -> Path:
    candidate = Path(unquote(raw_path)).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    candidate = candidate.resolve()
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"HTML file not found: {candidate}")
    return candidate


def parse_file_src(src: str) -> str:
    if src.startswith("file:///"):
        return src[7:]
    if src.startswith("file://"):
        return src[7:]
    if src.startswith("file:/"):
        return src[5:]
    return src


def resolve_project_asset_path(html_path: Path, asset_ref: str) -> Path:
    asset_ref = asset_ref.strip()
    if not asset_ref:
        raise FileNotFoundError("Empty asset path")
    if asset_ref.startswith("file:"):
        return Path(parse_file_src(asset_ref)).resolve()
    asset_path = Path(asset_ref)
    if asset_path.is_absolute():
        return asset_path.resolve()
    return (html_path.parent / asset_path).resolve()


def load_layout_positions(html_path: Path) -> List[Dict[str, Any]]:
    layout_path = html_path.parent / "temp_analysis" / "layout_positions.txt"
    if not layout_path.exists():
        return []
    with open(layout_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_layout_positions(html_path: Path, layouts: List[Dict[str, Any]]) -> Path:
    layout_path = html_path.parent / "temp_analysis" / "layout_positions.txt"
    backup_if_needed(layout_path)
    with open(layout_path, "w", encoding="utf-8") as f:
        json.dump(layouts, f, ensure_ascii=False, indent=2)
    return layout_path


def backup_if_needed(path: Path):
    backup = path.with_suffix(path.suffix + ".layout_editor.bak")
    if path.exists() and not backup.exists():
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def parse_pct_style(style: str) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for key in ("left", "top", "width", "height"):
        match = re.search(rf"{key}\s*:\s*([0-9.]+)%", style or "")
        values[key] = float(match.group(1)) if match else 0.0
    return values


def style_pct_to_logical(style_pct: Dict[str, float], is_t2svg: bool) -> Dict[str, int]:
    left_pct = style_pct["left"]
    top_pct = style_pct["top"]
    width_pct = style_pct["width"]
    height_pct = style_pct["height"]

    if is_t2svg:
        logical_width_pct = width_pct / T2SVG_SCALE
        logical_height_pct = height_pct / T2SVG_SCALE
        logical_left_pct = left_pct + (width_pct - logical_width_pct) / 2.0
        logical_top_pct = top_pct + (height_pct - logical_height_pct) / 2.0
    else:
        logical_width_pct = width_pct
        logical_height_pct = height_pct
        logical_left_pct = left_pct
        logical_top_pct = top_pct

    x = int(round(logical_left_pct / 100.0 * LAYOUT_CANVAS_W))
    y = int(round(logical_top_pct / 100.0 * LAYOUT_CANVAS_H))
    w = int(round(logical_width_pct / 100.0 * LAYOUT_CANVAS_W))
    h = int(round(logical_height_pct / 100.0 * LAYOUT_CANVAS_H))
    return {
        "x": max(0, x),
        "y": max(0, y),
        "width": max(20, w),
        "height": max(20, h),
    }


def logical_to_svg_style(layout: Dict[str, Any], is_t2svg: bool) -> str:
    x = float(layout.get("x", 0))
    y = float(layout.get("y", 0))
    w = float(layout.get("width", 320))
    h = float(layout.get("height", 180))

    left_pct = x / LAYOUT_CANVAS_W * 100.0
    top_pct = y / LAYOUT_CANVAS_H * 100.0
    width_pct = w / LAYOUT_CANVAS_W * 100.0
    height_pct = h / LAYOUT_CANVAS_H * 100.0

    if is_t2svg:
        orig_w_pct = width_pct
        orig_h_pct = height_pct
        width_pct *= T2SVG_SCALE
        height_pct *= T2SVG_SCALE
        left_pct -= (width_pct - orig_w_pct) / 2.0
        top_pct -= (height_pct - orig_h_pct) / 2.0
        width_pct = max(width_pct, 18.0)
        height_pct = max(height_pct, 15.0)
    else:
        width_pct = max(width_pct, 14.0)
        height_pct = max(height_pct, 10.5)

    left_pct = max(EDGE_MARGIN_X, left_pct)
    top_pct = max(EDGE_MARGIN_Y, top_pct)
    if left_pct + width_pct > 100.0 - EDGE_MARGIN_X:
        left_pct = max(EDGE_MARGIN_X, 100.0 - EDGE_MARGIN_X - width_pct)
    if top_pct + height_pct > 100.0 - EDGE_MARGIN_Y:
        top_pct = max(EDGE_MARGIN_Y, 100.0 - EDGE_MARGIN_Y - height_pct)

    return (
        f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; "
        f"width: {width_pct:.2f}%; height: {height_pct:.2f}%;"
    )


def determine_position_name(layout: Dict[str, int]) -> str:
    cx = layout["x"] + layout["width"] / 2.0
    cy = layout["y"] + layout["height"] / 2.0
    if cy < LAYOUT_CANVAS_H * 0.28:
        return "top-left" if cx < LAYOUT_CANVAS_W / 2 else "top-right"
    if cy > LAYOUT_CANVAS_H * 0.72:
        return "bottom-left" if cx < LAYOUT_CANVAS_W / 2 else "bottom-right"
    return "middle-left" if cx < LAYOUT_CANVAS_W / 2 else "middle-right"


def find_matching_layout_index(layouts: List[Dict[str, Any]], start: float, end: float) -> Optional[int]:
    for idx, item in enumerate(layouts):
        if abs(float(item.get("timestamp", -999)) - float(start)) <= 1e-2 and abs(float(item.get("end", -999)) - float(end)) <= 1e-2:
            return idx
    return None


def parse_project(html_path: Path) -> Dict[str, Any]:
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    video_tag = soup.find("video", id="mainVideo")
    if video_tag is None:
        raise ValueError("mainVideo not found in HTML")

    source = video_tag.find("source")
    video_src = source.get("src", "") if source else video_tag.get("src", "")
    video_file = resolve_project_asset_path(html_path, video_src)

    layout_positions = load_layout_positions(html_path)
    overlays = []
    for div in soup.select("#overlayContainer .enhancement-container"):
        img = div.select_one("img.svg-content-image")
        if img is None:
            continue

        container_id = div.get("id", "")
        start = float(div.get("data-start", 0.0))
        end = float(div.get("data-end", 0.0))
        style = div.get("style", "")
        style_pct = parse_pct_style(style)

        asset_ref = img.get("data-svg-src") or img.get("src") or ""
        asset_path = resolve_project_asset_path(html_path, asset_ref)
        is_t2svg = "assets/t2svg/" in asset_ref.replace("\\", "/")

        layout_index = find_matching_layout_index(layout_positions, start, end)
        layout_entry = layout_positions[layout_index] if layout_index is not None else None
        if layout_entry:
            logical_layout = {
                "x": int(layout_entry["layout"]["x"]),
                "y": int(layout_entry["layout"]["y"]),
                "width": int(layout_entry["layout"]["width"]),
                "height": int(layout_entry["layout"]["height"]),
            }
            text_excerpt = layout_entry.get("text", "")
        else:
            logical_layout = style_pct_to_logical(style_pct, is_t2svg)
            text_excerpt = ""

        overlays.append(
            {
                "container_id": container_id,
                "start": start,
                "end": end,
                "duration": round(end - start, 3),
                "display_style": style_pct,
                "logical_layout": logical_layout,
                "is_t2svg": is_t2svg,
                "asset_name": asset_path.name,
                "asset_ref": asset_ref,
                "asset_url": f"/project-file?html_path={html_path}&asset={asset_ref}",
                "text_excerpt": text_excerpt[:140],
                "layout_index": layout_index,
            }
        )

    overlays.sort(key=lambda item: item["start"])
    return {
        "project_name": html_path.parent.name,
        "html_path": str(html_path),
        "video_url": f"/project-file?html_path={html_path}&asset={video_src}",
        "overlay_count": len(overlays),
        "overlays": overlays,
    }


def save_project_layouts(html_path: Path, overlays_payload: List[Dict[str, Any]]) -> Dict[str, Any]:
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    layouts = load_layout_positions(html_path)
    updated = 0

    by_id = {item["container_id"]: item for item in overlays_payload}
    for div in soup.select("#overlayContainer .enhancement-container"):
        container_id = div.get("id", "")
        payload = by_id.get(container_id)
        if not payload:
            continue

        start = float(div.get("data-start", 0.0))
        end = float(div.get("data-end", 0.0))
        is_t2svg = bool(payload.get("is_t2svg"))
        display_style = payload["display_style"]
        logical_layout = style_pct_to_logical(display_style, is_t2svg)
        logical_layout["position"] = determine_position_name(logical_layout)

        div["style"] = logical_to_svg_style(logical_layout, is_t2svg)

        layout_index = find_matching_layout_index(layouts, start, end)
        if layout_index is not None:
            current_layout = layouts[layout_index].setdefault("layout", {})
            current_layout["x"] = logical_layout["x"]
            current_layout["y"] = logical_layout["y"]
            current_layout["width"] = logical_layout["width"]
            current_layout["height"] = logical_layout["height"]
            current_layout["position"] = logical_layout["position"]
        updated += 1

    backup_if_needed(html_path)
    html_path.write_text(str(soup), encoding="utf-8")
    layout_path = save_layout_positions(html_path, layouts)

    return {
        "updated_count": updated,
        "html_path": str(html_path),
        "layout_path": str(layout_path),
    }


@app.get("/project-file")
def project_file():
    html_path = resolve_html_path(request.args["html_path"])
    asset = request.args["asset"]
    asset_path = resolve_project_asset_path(html_path, asset)
    return send_file(asset_path)


@app.get("/api/projects")
def api_projects():
    return jsonify({"projects": list_projects()})


@app.post("/api/load")
def api_load():
    payload = request.get_json(force=True)
    html_path = resolve_html_path(payload["html_path"])
    project = parse_project(html_path)
    return jsonify(project)


@app.post("/api/save")
def api_save():
    payload = request.get_json(force=True)
    html_path = resolve_html_path(payload["html_path"])
    result = save_project_layouts(html_path, payload.get("overlays", []))
    return jsonify({"ok": True, **result})


INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Layout Editor</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "IBM Plex Sans", system-ui, sans-serif; background: #eef3f8; color: #18344f; }
    .app { display: grid; grid-template-columns: minmax(0, 1fr) 360px; height: 100vh; gap: 12px; padding: 12px; }
    .stage-panel, .side-panel { background: #fff; border: 1px solid #d6e1ec; border-radius: 18px; overflow: hidden; }
    .toolbar { display: flex; gap: 10px; padding: 14px; border-bottom: 1px solid #e1e8f0; align-items: center; }
    .toolbar input { flex: 1; height: 38px; padding: 0 12px; border: 1px solid #c8d7e6; border-radius: 10px; }
    .toolbar button { height: 38px; padding: 0 14px; border: 0; border-radius: 10px; background: #2e6fb3; color: #fff; cursor: pointer; font-weight: 600; }
    .toolbar button.secondary { background: #eff5fb; color: #29527a; border: 1px solid #d1deea; }
    .video-shell { padding: 14px; height: calc(100% - 67px); display: flex; flex-direction: column; gap: 10px; }
    .project-meta { font-size: 13px; color: #5c7692; }
    .stage { position: relative; flex: 1; background: #000; border-radius: 16px; overflow: hidden; }
    video { width: 100%; height: 100%; object-fit: contain; display: block; background: #000; }
    .overlay-layer { position: absolute; inset: 0; pointer-events: none; }
    .editor-overlay { position: absolute; border: 2px solid #ff5e57; box-shadow: 0 0 0 1px rgba(255,255,255,0.6) inset; cursor: move; pointer-events: auto; display: none; }
    .editor-overlay.selected { border-color: #ff8a00; box-shadow: 0 0 0 2px rgba(255,138,0,0.16); }
    .editor-overlay.visible { display: block; }
    .editor-overlay img { width: 100%; height: 100%; object-fit: contain; display: block; pointer-events: none; user-select: none; }
    .resize-handle { position: absolute; width: 18px; height: 18px; right: -9px; bottom: -9px; background: #ff8a00; border: 2px solid #fff; border-radius: 50%; cursor: nwse-resize; }
    .badge { position: absolute; top: -28px; left: 0; background: rgba(15,29,44,0.86); color: #fff; padding: 5px 8px; font-size: 12px; border-radius: 8px; white-space: nowrap; }
    .coord-box { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
    .coord-box div { background: #f5f9fd; border: 1px solid #dde7f0; border-radius: 10px; padding: 8px; font-size: 12px; }
    .side-panel { display: flex; flex-direction: column; }
    .side-top { padding: 14px; border-bottom: 1px solid #e1e8f0; }
    .project-list, .overlay-list { overflow: auto; }
    .project-list { max-height: 180px; margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
    .overlay-list { flex: 1; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
    .item, .project-item { border: 1px solid #d8e2ec; border-radius: 12px; padding: 10px 12px; cursor: pointer; background: #fff; }
    .item.active, .project-item.active { border-color: #2e6fb3; box-shadow: 0 0 0 3px rgba(46,111,179,0.12); }
    .item-title { font-weight: 700; font-size: 13px; margin-bottom: 4px; }
    .item-sub { font-size: 12px; color: #57728d; line-height: 1.4; }
    .status { font-size: 12px; color: #55718c; padding: 0 14px 12px; }
  </style>
</head>
<body>
  <div class="app">
    <section class="stage-panel">
      <div class="toolbar">
        <input id="htmlPath" placeholder="选择或粘贴 enhanced_video.html 的绝对路径">
        <button id="loadBtn">加载项目</button>
        <button id="saveBtn">保存坐标</button>
        <button id="jumpBtn" class="secondary">跳到当前</button>
      </div>
      <div class="video-shell">
        <div class="project-meta" id="projectMeta">未加载项目</div>
        <div class="coord-box">
          <div>X: <span id="coordX">-</span></div>
          <div>Y: <span id="coordY">-</span></div>
          <div>W: <span id="coordW">-</span></div>
          <div>H: <span id="coordH">-</span></div>
        </div>
        <div class="stage" id="stage">
          <video id="video" controls></video>
          <div class="overlay-layer" id="overlayLayer"></div>
        </div>
      </div>
    </section>
    <aside class="side-panel">
      <div class="side-top">
        <strong>项目</strong>
        <div class="project-list" id="projectList"></div>
      </div>
      <div class="status" id="status">等待加载</div>
      <div class="overlay-list" id="overlayList"></div>
    </aside>
  </div>
  <script>
    const htmlPathInput = document.getElementById('htmlPath');
    const loadBtn = document.getElementById('loadBtn');
    const saveBtn = document.getElementById('saveBtn');
    const jumpBtn = document.getElementById('jumpBtn');
    const projectList = document.getElementById('projectList');
    const overlayList = document.getElementById('overlayList');
    const overlayLayer = document.getElementById('overlayLayer');
    const video = document.getElementById('video');
    const stage = document.getElementById('stage');
    const projectMeta = document.getElementById('projectMeta');
    const statusEl = document.getElementById('status');
    const coordEls = {
      x: document.getElementById('coordX'),
      y: document.getElementById('coordY'),
      w: document.getElementById('coordW'),
      h: document.getElementById('coordH')
    };

    let currentProject = null;
    let selectedIndex = -1;
    let interaction = null;

    async function fetchProjects() {
      const res = await fetch('/api/projects');
      const data = await res.json();
      projectList.innerHTML = '';
      data.projects.forEach(project => {
        const item = document.createElement('div');
        item.className = 'project-item';
        item.textContent = project.name;
        item.title = project.html_path;
        item.onclick = () => {
          htmlPathInput.value = project.html_path;
          loadProject(project.html_path);
          document.querySelectorAll('.project-item').forEach(el => el.classList.remove('active'));
          item.classList.add('active');
        };
        projectList.appendChild(item);
      });
    }

    async function loadProject(path) {
      statusEl.textContent = '加载中...';
      const res = await fetch('/api/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html_path: path })
      });
      if (!res.ok) {
        statusEl.textContent = '加载失败';
        alert(await res.text());
        return;
      }
      currentProject = await res.json();
      selectedIndex = currentProject.overlays.length ? 0 : -1;
      video.src = currentProject.video_url;
      renderProject();
      statusEl.textContent = `已加载 ${currentProject.overlay_count} 个可编辑浮层`;
    }

    function renderProject() {
      if (!currentProject) return;
      projectMeta.textContent = `${currentProject.project_name} | ${currentProject.overlay_count} overlays`;
      overlayLayer.innerHTML = '';
      overlayList.innerHTML = '';

      currentProject.overlays.forEach((overlay, index) => {
        const box = document.createElement('div');
        box.className = 'editor-overlay' + (index === selectedIndex ? ' selected visible' : '');
        box.dataset.index = index;
        applyDisplayStyle(box, overlay.display_style);

        const badge = document.createElement('div');
        badge.className = 'badge';
        badge.textContent = `${overlay.container_id} | ${overlay.start.toFixed(1)}s`;
        box.appendChild(badge);

        const img = document.createElement('img');
        img.src = overlay.asset_url;
        box.appendChild(img);

        const handle = document.createElement('div');
        handle.className = 'resize-handle';
        box.appendChild(handle);

        box.addEventListener('pointerdown', (event) => startDrag(event, index, false));
        handle.addEventListener('pointerdown', (event) => startDrag(event, index, true));

        overlayLayer.appendChild(box);

        const item = document.createElement('div');
        item.className = 'item' + (index === selectedIndex ? ' active' : '');
        item.innerHTML = `
          <div class="item-title">${overlay.container_id} | ${overlay.asset_name}</div>
          <div class="item-sub">${overlay.start.toFixed(1)}s - ${overlay.end.toFixed(1)}s</div>
          <div class="item-sub">${overlay.text_excerpt || '(无文本摘要)'}</div>
        `;
        item.onclick = () => selectOverlay(index, true);
        overlayList.appendChild(item);
      });

      updateCoordinateBox();
      if (selectedIndex >= 0) {
        jumpToSelected();
      }
    }

    function applyDisplayStyle(el, style) {
      el.style.left = style.left.toFixed(2) + '%';
      el.style.top = style.top.toFixed(2) + '%';
      el.style.width = style.width.toFixed(2) + '%';
      el.style.height = style.height.toFixed(2) + '%';
    }

    function selectOverlay(index, jump) {
      selectedIndex = index;
      document.querySelectorAll('.editor-overlay').forEach((el, idx) => {
        el.classList.toggle('selected', idx === index);
        el.classList.toggle('visible', idx === index);
      });
      document.querySelectorAll('.overlay-list .item').forEach((el, idx) => {
        el.classList.toggle('active', idx === index);
      });
      updateCoordinateBox();
      if (jump) jumpToSelected();
    }

    function jumpToSelected() {
      if (!currentProject || selectedIndex < 0) return;
      const overlay = currentProject.overlays[selectedIndex];
      video.currentTime = overlay.start;
      video.pause();
    }

    function updateCoordinateBox() {
      if (!currentProject || selectedIndex < 0) {
        coordEls.x.textContent = coordEls.y.textContent = coordEls.w.textContent = coordEls.h.textContent = '-';
        return;
      }
      const layout = currentProject.overlays[selectedIndex].logical_layout;
      coordEls.x.textContent = layout.x;
      coordEls.y.textContent = layout.y;
      coordEls.w.textContent = layout.width;
      coordEls.h.textContent = layout.height;
    }

    function syncLogicalLayout(index) {
      const overlay = currentProject.overlays[index];
      const ds = overlay.display_style;
      const leftPct = ds.left;
      const topPct = ds.top;
      const widthPct = ds.width;
      const heightPct = ds.height;

      let logicalWidthPct = widthPct;
      let logicalHeightPct = heightPct;
      let logicalLeftPct = leftPct;
      let logicalTopPct = topPct;
      if (overlay.is_t2svg) {
        logicalWidthPct = widthPct / 1.3;
        logicalHeightPct = heightPct / 1.3;
        logicalLeftPct = leftPct + (widthPct - logicalWidthPct) / 2.0;
        logicalTopPct = topPct + (heightPct - logicalHeightPct) / 2.0;
      }
      overlay.logical_layout = {
        x: Math.max(0, Math.round(logicalLeftPct / 100 * 1920)),
        y: Math.max(0, Math.round(logicalTopPct / 100 * 1080)),
        width: Math.max(20, Math.round(logicalWidthPct / 100 * 1920)),
        height: Math.max(20, Math.round(logicalHeightPct / 100 * 1080))
      };
    }

    function startDrag(event, index, resizeMode) {
      event.stopPropagation();
      event.preventDefault();
      selectOverlay(index, false);
      const overlay = currentProject.overlays[index];
      const box = overlayLayer.children[index];
      const rect = box.getBoundingClientRect();
      const stageRect = stage.getBoundingClientRect();
      interaction = {
        index,
        resizeMode,
        startX: event.clientX,
        startY: event.clientY,
        initial: { ...overlay.display_style },
        stageWidth: stageRect.width,
        stageHeight: stageRect.height
      };
      window.addEventListener('pointermove', onPointerMove);
      window.addEventListener('pointerup', stopDrag);
    }

    function onPointerMove(event) {
      if (!interaction) return;
      const overlay = currentProject.overlays[interaction.index];
      const dxPct = (event.clientX - interaction.startX) / interaction.stageWidth * 100;
      const dyPct = (event.clientY - interaction.startY) / interaction.stageHeight * 100;

      if (interaction.resizeMode) {
        overlay.display_style.width = Math.max(6, interaction.initial.width + dxPct);
        overlay.display_style.height = Math.max(6, interaction.initial.height + dyPct);
      } else {
        overlay.display_style.left = interaction.initial.left + dxPct;
        overlay.display_style.top = interaction.initial.top + dyPct;
      }

      overlay.display_style.left = Math.max(0, Math.min(100 - overlay.display_style.width, overlay.display_style.left));
      overlay.display_style.top = Math.max(0, Math.min(100 - overlay.display_style.height, overlay.display_style.top));

      const box = overlayLayer.children[interaction.index];
      applyDisplayStyle(box, overlay.display_style);
      syncLogicalLayout(interaction.index);
      updateCoordinateBox();
    }

    function stopDrag() {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', stopDrag);
      interaction = null;
    }

    async function saveProject() {
      if (!currentProject) return;
      statusEl.textContent = '保存中...';
      const res = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          html_path: currentProject.html_path,
          overlays: currentProject.overlays
        })
      });
      const data = await res.json();
      if (!res.ok) {
        statusEl.textContent = '保存失败';
        alert(JSON.stringify(data));
        return;
      }
      statusEl.textContent = `已保存 ${data.updated_count} 项`;
      await loadProject(currentProject.html_path);
    }

    loadBtn.onclick = () => {
      if (htmlPathInput.value.trim()) loadProject(htmlPathInput.value.trim());
    };
    saveBtn.onclick = saveProject;
    jumpBtn.onclick = jumpToSelected;

    fetchProjects();
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    return INDEX_HTML


def main():
    parser = argparse.ArgumentParser(description="Interactive layout editor for enhanced_video.html")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
