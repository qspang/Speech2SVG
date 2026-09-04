"""
HTML Generator - simplified HTML renderer
=========================================

Layout:
- Left: video player + overlays
- Left bottom: enhancement gallery with inline timeline
- Right: subtitles

The generator keeps the old public API but removes legacy concept-graph,
modal-preview, shortcut-help, and complex gallery logic.
"""

import html as html_module
import json
import os
from typing import Dict, List


class HTMLGenerator:
    """Minimal HTML generator for enhanced video playback."""

    LAYOUT_CANVAS_W = 1920
    LAYOUT_CANVAS_H = 1080

    def generate_skeleton(
        self,
        video_source: str,
        transcript_path: str,
        html_path: str,
        concept_graph: Dict = None,
    ) -> str:
        video_src = self._resolve_video_source(video_source)
        transcript_data = self._parse_transcript(transcript_path)
        html_content = self._build_skeleton_html(video_src, transcript_data)

        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"  ✓ HTML skeleton generated: {html_path}")
        return html_path

    def append_content(self, html_path: str, point: Dict, idx: int):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        overlay_html = self._generate_overlay_html(point, idx)
        gallery_html = self._generate_gallery_item_html(point, idx)

        html_content = html_content.replace(
            "<!-- OVERLAY_MARKER -->",
            overlay_html + "\n            <!-- OVERLAY_MARKER -->",
        )
        html_content = html_content.replace(
            "<!-- GALLERY_MARKER -->",
            gallery_html + "\n                <!-- GALLERY_MARKER -->",
        )

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"    ✓ Appended [{point.get('content_type', 'unknown')}] #{idx} to HTML")

    def generate(
        self,
        video_source: str,
        enhancement_points: List[Dict],
        transcript_path: str = None,
    ) -> str:
        video_src = self._resolve_video_source(video_source)
        transcript_data = self._parse_transcript(transcript_path) if transcript_path else []
        html_content = self._build_skeleton_html(video_src, transcript_data)

        for idx, point in enumerate(enhancement_points):
            overlay_html = self._generate_overlay_html(point, idx)
            gallery_html = self._generate_gallery_item_html(point, idx)
            html_content = html_content.replace(
                "<!-- OVERLAY_MARKER -->",
                overlay_html + "\n            <!-- OVERLAY_MARKER -->",
            )
            html_content = html_content.replace(
                "<!-- GALLERY_MARKER -->",
                gallery_html + "\n                <!-- GALLERY_MARKER -->",
            )

        return html_content

    def _build_skeleton_html(self, video_src: str, transcript_data: List[Dict]) -> str:
        transcript_json = json.dumps(transcript_data, ensure_ascii=False)
        subtitle_entries_html = self._generate_subtitle_entries(transcript_data)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Enhancement Studio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
{self._generate_css()}
    </style>
</head>
<body>
    <header class="app-header">
        <div class="header-left">
            <div class="logo">
                <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                    <rect width="28" height="28" rx="6" fill="url(#logoGrad)"/>
                    <path d="M8 14L12 10L16 14L20 10" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M8 18L12 14L16 18L20 14" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.6"/>
                    <defs>
                        <linearGradient id="logoGrad" x1="0" y1="0" x2="28" y2="28">
                            <stop stop-color="#2f5f98"/>
                            <stop offset="1" stop-color="#3f7fb8"/>
                        </linearGradient>
                    </defs>
                </svg>
                <span class="logo-text">Video Enhancement Studio</span>
            </div>
        </div>
        <div class="header-right">
            <button id="toggleOverlays" class="header-tool-btn active" onclick="toggleOverlays()" title="切换浮层显示">浮层</button>
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="搜索字幕内容..." autocomplete="off">
                <button id="searchBtn" onclick="searchSubtitles()">搜索</button>
                <button id="clearBtn" onclick="clearSearch()" style="display:none">清除</button>
            </div>
        </div>
    </header>

    <div class="main-content">
        <div class="left-panel">
            <section class="video-section">
                <div class="video-wrapper">
                    <video id="mainVideo" controls>
                        <source src="{video_src}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                    <div id="overlayContainer">
            <!-- OVERLAY_MARKER -->
                    </div>
                </div>
            </section>

            <section class="gallery-section">
                <div class="section-mini-header">
                    <h3>增强内容画廊</h3>
                    <span class="gallery-count" id="galleryCount">0 个增强点</span>
                </div>
                <div class="gallery-timeline-inline" id="enhancementTimelineTrack">
                    <div class="enhancement-timeline-progress" id="enhancementTimelineProgress"></div>
                    <div class="enhancement-timeline-dots" id="enhancementTimelineDots"></div>
                </div>
                <div class="gallery-strip" id="galleryStrip"></div>
                <div class="gallery-source" id="gallerySource">
                <!-- GALLERY_MARKER -->
                </div>
                <div class="gallery-empty" id="galleryEmpty">
                    <p>等待内容生成中...</p>
                    <p class="hint">生成后会在这里显示缩略图和时间。</p>
                </div>
            </section>
        </div>

        <aside class="right-panel">
            <section class="subtitle-section">
                <div class="subtitle-header">
                    <h3>字幕</h3>
                    <span class="subtitle-count">{len(transcript_data)} 条字幕</span>
                </div>
                <div class="subtitle-list" id="subtitleList">
{subtitle_entries_html}
                </div>
            </section>
        </aside>
    </div>

    <script>
{self._generate_javascript(transcript_json, "{}")}
    </script>
</body>
</html>"""

    def _generate_overlay_html(self, point: Dict, idx: int) -> str:
        layout = point.get("layout", {})
        content = point.get("content", {})
        content_type = content.get("type", "text")

        if content_type == "svg":
            style = self._get_svg_container_style(layout, content)
        else:
            x = layout.get("x", 50)
            y = layout.get("y", 50)
            width = layout.get("width", 350)
            height = layout.get("height", 250)
            left_pct = x / self.LAYOUT_CANVAS_W * 100
            top_pct = y / self.LAYOUT_CANVAS_H * 100
            desired_w_pct = max(width / self.LAYOUT_CANVAS_W * 100, 22.0)
            available_right_pct = max(16.0, 98.0 - left_pct)
            fit_w_pct = min(desired_w_pct, available_right_pct)
            available_bottom_pct = max(10.0, 92.0 - top_pct)
            h_pct_max = min(max(height / self.LAYOUT_CANVAS_H * 100 * 1.55, 22.0), available_bottom_pct)
            scale = max(0.72, min(1.0, fit_w_pct / max(desired_w_pct, 1.0)))
            style = (
                f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; "
                f"width: {fit_w_pct:.2f}%; max-width: {fit_w_pct:.2f}%; "
                f"height: auto; max-height: {h_pct_max:.2f}%; min-height: 5%; "
                f"--overlay-scale: {scale:.3f};"
            )

        content_html = self._generate_content_html(content, point)
        container_class = "enhancement-container"
        if content_type == "svg":
            container_class += " svg-overlay"

        timestamp = point.get("timestamp", 0)
        duration = point.get("duration", 5)

        return f"""            <div class="{container_class}"
                 id="container-{idx}"
                 data-start="{timestamp}"
                 data-end="{timestamp + duration}"
                 data-type="{point.get('content_type', 'unknown')}"
                 style="{style}">
                {content_html}
            </div>"""

    def _generate_gallery_item_html(self, point: Dict, idx: int) -> str:
        content = point.get("content", {})
        content_type = content.get("type", "text")
        point_content_type = point.get("content_type", "")
        timestamp = point.get("timestamp", 0)
        topic = (point.get("text", "") or "")[:120]
        svg_path = content.get("path", "")

        if point_content_type == "text_card":
            category = "text"
            icon = "文"
        elif content_type == "svg":
            category = "image"
            icon = "图"
        else:
            category = "text"
            icon = "文"

        attrs = {
            "data-idx": str(idx),
            "data-start": str(timestamp),
            "data-category": category,
            "data-title": content.get("title", topic)[:60] or topic[:60],
            "data-icon": icon,
            "data-svg-path": svg_path,
        }
        attr_html = " ".join(
            f'{key}="{html_module.escape(value, quote=True)}"' for key, value in attrs.items()
        )
        return f'                <div class="gallery-source-item" {attr_html}></div>'

    def _generate_content_html(self, content: Dict, point: Dict) -> str:
        content_type = content.get("type", "text")

        if content_type == "svg":
            svg_path = content.get("path", "")
            svg_intent = content.get("svg_intent", "")
            shell_class = "svg-shell image-svg-shell"
            if "assets/t2svg/" in svg_path or svg_intent in ("knowledge_note", "mechanism_process"):
                shell_class = "svg-shell text-svg-shell"

            if svg_path:
                return (
                    f'<div class="{shell_class}" style="{self._build_overlay_shell_style(content)}">'
                    f'<img src="{svg_path}" data-svg-src="{svg_path}" class="svg-content svg-content-image" alt="SVG enhancement" draggable="false">'
                    f"</div>"
                )
            return '<div class="placeholder">SVG Content</div>'

        label = content.get("label", "[ Note ]")
        hero_text = content.get("hero_text", "")
        explanation = content.get("explanation", "")
        style_dict = content.get("style", {})
        if not hero_text and not explanation:
            text = point.get("text", "")
            return f'<div class="text-content premium-glassmorphism"><div class="card-hero">{text}</div></div>'

        accent_color = style_dict.get("accent_color", "#4a79ba")
        result = f'<div class="text-content premium-glassmorphism" style="--card-accent: {accent_color};">'
        if label:
            result += f'<div class="card-label">{html_module.escape(label)}</div>'
        if hero_text:
            result += f'<h3 class="card-hero">{html_module.escape(hero_text)}</h3>'
        if explanation:
            result += f'<div class="card-explanation">{html_module.escape(explanation)}</div>'
        result += "</div>"
        return result

    def _build_overlay_shell_style(self, content: Dict) -> str:
        return (
            "background: transparent !important; "
            "border: none !important; "
            "border-radius: 0; "
            "overflow: visible; "
            "box-shadow: none !important;"
        )

    def _generate_subtitle_entries(self, transcript_data: List[Dict]) -> str:
        if not transcript_data:
            return '                <div class="subtitle-empty">暂无字幕数据</div>'

        entries = []
        for item in transcript_data:
            start = item.get("start", 0)
            end = item.get("end", 0)
            text = html_module.escape(item.get("text", ""))
            time_str = self._format_time(start)
            entries.append(
                f'                <div class="subtitle-item" data-start="{start}" data-end="{end}" onclick="jumpTo({start})">'
                f'<span class="sub-time">{time_str}</span>'
                f'<span class="sub-text">{text}</span>'
                f"</div>"
            )
        return "\n".join(entries)

    def _get_svg_container_style(self, layout: Dict, content: Dict | None = None) -> str:
        x = layout.get("x")
        y = layout.get("y")
        w = layout.get("width")
        h = layout.get("height")

        if x is not None and y is not None and w is not None and h is not None:
            left_pct = x / self.LAYOUT_CANVAS_W * 100
            top_pct = y / self.LAYOUT_CANVAS_H * 100
            w_pct = w / self.LAYOUT_CANVAS_W * 100
            h_pct = h / self.LAYOUT_CANVAS_H * 100
            svg_path = (content or {}).get("path", "")
            svg_intent = (content or {}).get("svg_intent", "")
            is_t2svg = "assets/t2svg/" in svg_path or svg_intent in ("knowledge_note", "mechanism_process")

            if is_t2svg:
                original_w_pct = w_pct
                original_h_pct = h_pct
                w_pct *= 1.30
                h_pct *= 1.30
                left_pct -= (w_pct - original_w_pct) / 2
                top_pct -= (h_pct - original_h_pct) / 2

            w_pct = max(w_pct, 18.0 if is_t2svg else 14.0)
            h_pct = max(h_pct, 15.0 if is_t2svg else 10.5)
            margin_x = 1.8
            margin_y = 2.0
            left_pct = max(margin_x, left_pct)
            top_pct = max(margin_y, top_pct)
            if left_pct + w_pct > 100 - margin_x:
                left_pct = max(margin_x, 100 - margin_x - w_pct)
            if top_pct + h_pct > 100 - margin_y:
                top_pct = max(margin_y, 100 - margin_y - h_pct)
            return f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {w_pct:.2f}%; height: {h_pct:.2f}%;"

        position = layout.get("position", "center")
        fallback_map = {
            "top-left": "left: 2%; top: 2%; width: 55%; height: 55%;",
            "top-right": "right: 2%; top: 2%; width: 55%; height: 55%;",
            "bottom-left": "left: 2%; bottom: 2%; width: 55%; height: 55%;",
            "bottom-right": "right: 2%; bottom: 2%; width: 55%; height: 55%;",
            "middle-left": "left: 4.5%; top: 18%; width: 46%; height: 54%;",
            "middle-right": "right: 4.5%; top: 18%; width: 46%; height: 54%;",
            "full": "left: 5%; top: 5%; width: 90%; height: 90%;",
            "center": "left: 5%; top: 5%; width: 90%; height: 90%;",
        }
        return fallback_map.get(position, fallback_map["center"])

    def _resolve_video_source(self, video_source: str) -> str:
        if os.path.isabs(video_source):
            return f"file:///{video_source.replace(os.sep, '/')}"
        return video_source

    def _parse_transcript(self, transcript_path: str) -> List[Dict]:
        if not transcript_path or not os.path.exists(transcript_path):
            return []

        transcript = []
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        transcript.append(
                            {
                                "start": float(parts[0]),
                                "end": float(parts[1]),
                                "text": parts[2],
                            }
                        )
        except Exception as e:
            print(f"  ⚠ 解析字幕文件失败: {e}")
        return transcript

    def _format_time(self, seconds: float) -> str:
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"

    def _generate_css(self) -> str:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg-page: #f4f8fd;
            --bg-card: #ffffff;
            --bg-soft: #eef5fb;
            --border: #d7e4f2;
            --accent: #4a79ba;
            --accent-soft: #6b97cd;
            --text-main: #1d3a58;
            --text-sub: #607a96;
            --text-faint: #97adc2;
            --header-height: 56px;
        }

        body {
            font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(180deg, #fbfdff 0%, var(--bg-page) 100%);
            color: var(--text-main);
            overflow: hidden;
            height: 100vh;
        }

        .app-header {
            height: var(--header-height);
            padding: 0 16px;
            border-bottom: 1px solid var(--border);
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header-left, .header-right, .logo, .search-box {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo-text {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-main);
        }

        .header-tool-btn,
        .search-box button {
            height: 34px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: #fff;
            color: var(--accent);
            padding: 0 12px;
            font: inherit;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
        }

        .header-tool-btn.active { background: #edf5fd; }

        .search-box input {
            width: 280px;
            height: 34px;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0 12px;
            font: inherit;
            color: var(--text-main);
            background: #fff;
        }

        #searchBtn {
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
        }

        .main-content {
            height: calc(100vh - var(--header-height));
            padding: 12px;
            display: grid;
            grid-template-columns: minmax(0, 6fr) minmax(340px, 4fr);
            gap: 14px;
        }

        .left-panel,
        .right-panel {
            min-width: 0;
            min-height: 0;
        }

        .left-panel {
            display: grid;
            grid-template-rows: minmax(0, 1fr) minmax(240px, 34vh);
            gap: 14px;
        }

        .video-section,
        .gallery-section,
        .subtitle-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 10px 28px rgba(74,121,186,0.08);
            min-height: 0;
        }

        .video-section { background: #000; }

        .video-wrapper {
            position: relative;
            width: 100%;
            height: 100%;
            overflow: hidden;
        }

        #mainVideo {
            width: 100%;
            height: 100%;
            object-fit: cover;
            background: #000;
            display: block;
        }

        #overlayContainer {
            position: absolute;
            inset: 0;
            pointer-events: none;
            z-index: 10;
        }

        .enhancement-container {
            position: absolute;
            opacity: 0;
            transition: opacity 0.35s ease;
            pointer-events: none;
            min-width: 0;
        }

        .enhancement-container.active { opacity: 1; }

        .svg-overlay,
        .svg-shell,
        .svg-content {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            filter: none !important;
        }

        .svg-shell {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: visible;
        }

        .svg-content {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }

        .text-svg-shell .svg-content { object-fit: fill; }

        .premium-glassmorphism {
            width: 100%;
            height: 100%;
            border-radius: 14px;
            padding: 20px 24px;
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(151,184,219,0.42);
            border-left: 4px solid var(--card-accent, var(--accent));
            box-shadow: 0 16px 38px rgba(47,111,178,0.12);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            gap: 10px;
            color: var(--text-main);
        }

        .text-content { width: 100%; min-width: 0; }
        .card-label { font-size: calc(12px * var(--overlay-scale, 1)); color: var(--card-accent, var(--accent)); font-weight: 700; text-transform: uppercase; }
        .card-hero { font-size: calc(17px * var(--overlay-scale, 1)); line-height: 1.35; font-weight: 600; overflow-wrap: anywhere; }
        .card-explanation { font-size: calc(14px * var(--overlay-scale, 1)); line-height: 1.55; color: var(--text-sub); overflow-wrap: anywhere; }

        .section-mini-header,
        .subtitle-header {
            padding: 12px 14px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .section-mini-header h3,
        .subtitle-header h3 {
            font-size: 14px;
            font-weight: 600;
        }

        .gallery-count,
        .subtitle-count {
            font-size: 12px;
            color: var(--text-faint);
        }

        .gallery-section {
            display: grid;
            grid-template-rows: auto auto minmax(0, 1fr);
        }

        .gallery-timeline-inline {
            position: relative;
            height: 22px;
            margin: 10px 14px 0;
            border-radius: 999px;
            background: linear-gradient(180deg, #f9fcff 0%, #eef5fb 100%);
            border: 1px solid #dbe8f4;
            overflow: hidden;
        }

        .gallery-timeline-inline::before {
            content: '';
            position: absolute;
            left: 10px;
            right: 10px;
            top: 50%;
            height: 3px;
            transform: translateY(-50%);
            border-radius: 999px;
            background: #d9e6f3;
        }

        .enhancement-timeline-progress {
            position: absolute;
            left: 10px;
            top: 50%;
            height: 3px;
            width: 0;
            transform: translateY(-50%);
            border-radius: 999px;
            background: linear-gradient(90deg, #5b8ec7 0%, #7aa8d9 100%);
            z-index: 1;
            transition: width 0.08s linear;
        }

        .enhancement-timeline-dots {
            position: absolute;
            inset: 0;
        }

        .enhancement-dot {
            position: absolute;
            top: 50%;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            background: var(--accent);
            border: 2px solid #fff;
            box-shadow: 0 4px 10px rgba(74,121,186,0.18);
            cursor: pointer;
            z-index: 2;
        }

        .enhancement-dot.text-dot { background: #8eacd2; }
        .enhancement-dot.image-dot { background: #4a79ba; }
        .enhancement-dot.active { transform: translate(-50%, -50%) scale(1.22); }

        .gallery-strip {
            padding: 12px 14px 14px;
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            overflow-y: auto;
            align-content: start;
            min-height: 0;
            background: #fbfdff;
        }

        .gallery-card {
            position: relative;
            min-height: 152px;
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid var(--border);
            background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
            cursor: pointer;
            transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        }

        .gallery-card:hover,
        .gallery-card.active {
            transform: translateY(-2px);
            border-color: var(--accent);
            box-shadow: 0 12px 24px rgba(74,121,186,0.14);
        }

        .gallery-card-media {
            width: 100%;
            height: 100%;
            min-height: 152px;
            background: var(--bg-soft);
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .gallery-card-media img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
            background: transparent;
        }

        .gallery-card-placeholder {
            font-size: 42px;
            color: var(--accent);
        }

        .gallery-card-time {
            position: absolute;
            left: 10px;
            bottom: 10px;
            font-size: 12px;
            color: #fff;
            background: rgba(18, 30, 43, 0.78);
            border-radius: 999px;
            padding: 4px 9px;
            font-variant-numeric: tabular-nums;
        }

        .gallery-source { display: none; }

        .gallery-empty {
            display: none;
            padding: 20px 14px 24px;
            text-align: center;
            color: var(--text-faint);
        }

        .gallery-empty .hint {
            margin-top: 6px;
            font-size: 12px;
        }

        .right-panel {
            display: flex;
            flex-direction: column;
            min-height: 0;
        }

        .subtitle-section {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .subtitle-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px 0;
            background: var(--bg-card);
        }

        .subtitle-item {
            padding: 10px 18px;
            display: flex;
            gap: 14px;
            cursor: pointer;
            border-left: 3px solid transparent;
            transition: background 0.15s ease;
        }

        .subtitle-item:hover,
        .subtitle-item.active {
            background: rgba(74,121,186,0.08);
        }

        .subtitle-item.active { border-left-color: var(--accent); }

        .sub-time {
            min-width: 42px;
            font-size: 13px;
            font-weight: 700;
            color: var(--accent-soft);
            font-variant-numeric: tabular-nums;
        }

        .sub-text {
            font-size: 13px;
            line-height: 1.6;
            color: var(--text-sub);
        }

        .subtitle-item.active .sub-text { color: var(--text-main); }

        .subtitle-item mark {
            background: #ffe08a;
            color: #000;
            border-radius: 3px;
            padding: 0 2px;
        }

        .subtitle-empty {
            padding: 40px 20px;
            text-align: center;
            color: var(--text-faint);
        }

        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #c7d9eb; border-radius: 999px; }

        @media (max-width: 1180px) {
            .main-content { grid-template-columns: 1fr; }
            .left-panel { grid-template-rows: minmax(0, 58vh) minmax(240px, 34vh); }
            .right-panel { min-height: 32vh; }
            .gallery-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        """

    def _generate_javascript(self, transcript_json: str, concept_graph_json: str) -> str:
        return f"""
        const transcriptData = {transcript_json};
        const video = document.getElementById('mainVideo');
        const overlayContainer = document.getElementById('overlayContainer');
        const subtitleList = document.getElementById('subtitleList');
        const searchInput = document.getElementById('searchInput');
        const gallerySource = document.getElementById('gallerySource');
        const galleryStrip = document.getElementById('galleryStrip');
        const galleryEmpty = document.getElementById('galleryEmpty');
        const galleryCount = document.getElementById('galleryCount');
        const enhancementTimelineDots = document.getElementById('enhancementTimelineDots');
        const enhancementTimelineProgress = document.getElementById('enhancementTimelineProgress');

        let overlaysEnabled = true;
        let isUserScrollingSubs = false;
        let scrollTimeout = null;
        let galleryEntries = [];

        function restartSvgAnimationInContainer(container) {{
            if (!container) return;
            const imgs = container.querySelectorAll('img.svg-content-image[data-svg-src]');
            imgs.forEach(img => {{
                const baseSrc = img.getAttribute('data-svg-src');
                if (!baseSrc) return;
                img.src = baseSrc + (baseSrc.includes('?') ? '&' : '?') + 'anim_restart=' + Date.now();
            }});
        }}

        function updateOverlayVisibility(currentTime) {{
            document.querySelectorAll('.enhancement-container').forEach(el => {{
                const start = parseFloat(el.dataset.start);
                const end = parseFloat(el.dataset.end);
                const shouldBeActive = currentTime >= start && currentTime <= end;
                const wasActive = el.classList.contains('active');
                if (shouldBeActive) {{
                    el.classList.add('active');
                    if (!wasActive) restartSvgAnimationInContainer(el);
                }} else {{
                    el.classList.remove('active');
                }}
            }});
        }}

        function updateSubtitleHighlight(currentTime) {{
            let activeItem = null;
            document.querySelectorAll('.subtitle-item').forEach(item => {{
                const start = parseFloat(item.dataset.start);
                const end = parseFloat(item.dataset.end);
                if (currentTime >= start && currentTime < end) {{
                    item.classList.add('active');
                    activeItem = item;
                }} else {{
                    item.classList.remove('active');
                }}
            }});
            if (activeItem && !isUserScrollingSubs) {{
                activeItem.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }}

        function updateTimelineProgress(currentTime) {{
            if (!video.duration) {{
                enhancementTimelineProgress.style.width = '0px';
                return;
            }}
            const trackWidth = enhancementTimelineDots.clientWidth || 0;
            const usableWidth = Math.max(0, trackWidth - 20);
            const width = Math.max(0, Math.min(usableWidth, usableWidth * (currentTime / video.duration)));
            enhancementTimelineProgress.style.width = width + 'px';

            document.querySelectorAll('.enhancement-dot').forEach(dot => {{
                const start = parseFloat(dot.dataset.start || '0');
                dot.classList.toggle('active', Math.abs(currentTime - start) <= 4.5);
            }});
        }}

        function adjustOverlayToVideo() {{
            const wrapper = video.parentElement;
            if (!wrapper) return;
            overlayContainer.style.left = '0px';
            overlayContainer.style.top = '0px';
            overlayContainer.style.width = wrapper.clientWidth + 'px';
            overlayContainer.style.height = wrapper.clientHeight + 'px';
        }}

        function collectGalleryEntries() {{
            galleryEntries = Array.from(gallerySource.querySelectorAll('.gallery-source-item')).map(node => ({{
                idx: Number(node.dataset.idx || 0),
                start: Number(node.dataset.start || 0),
                category: node.dataset.category || 'text',
                icon: node.dataset.icon || '文',
                svgPath: node.dataset.svgPath || '',
                title: node.dataset.title || ''
            }})).sort((a, b) => a.start - b.start);
        }}

        function renderGalleryStrip() {{
            if (!galleryEntries.length) {{
                galleryStrip.innerHTML = '';
                galleryEmpty.style.display = '';
                galleryCount.textContent = '0 个增强点';
                return;
            }}

            galleryEmpty.style.display = 'none';
            galleryCount.textContent = galleryEntries.length + ' 个增强点';
            let html = '';
            galleryEntries.forEach(item => {{
                const imageHtml = item.svgPath
                    ? '<img src="' + escapeAttr(item.svgPath) + '" alt="">'
                    : '<div class="gallery-card-placeholder">' + escapeHtml(item.icon || '文') + '</div>';
                html += '<div class="gallery-card" data-idx="' + item.idx + '" onclick="jumpTo(' + item.start + ')">';
                html += '<div class="gallery-card-media">' + imageHtml + '</div>';
                html += '<div class="gallery-card-time">' + formatTime(item.start) + '</div>';
                html += '</div>';
            }});
            galleryStrip.innerHTML = html;
        }}

        function renderEnhancementTimeline() {{
            if (!galleryEntries.length || !video.duration) {{
                enhancementTimelineDots.innerHTML = '';
                enhancementTimelineProgress.style.width = '0px';
                return;
            }}
            const trackWidth = enhancementTimelineDots.clientWidth || 0;
            const usableWidth = Math.max(0, trackWidth - 20);
            const dotsHtml = galleryEntries.map(item => {{
                const left = 10 + (usableWidth * (item.start / video.duration));
                const dotClass = item.category === 'image' ? 'image-dot' : 'text-dot';
                return '<button class="enhancement-dot ' + dotClass + '" '
                    + 'style="left:' + left + 'px" '
                    + 'data-start="' + item.start + '" '
                    + 'title="' + escapeAttr(formatTime(item.start) + ' ' + (item.title || '增强内容')) + '" '
                    + 'onclick="jumpTo(' + item.start + ')"></button>';
            }}).join('');
            enhancementTimelineDots.innerHTML = dotsHtml;
            updateTimelineProgress(video.currentTime || 0);
        }}

        function refreshGallerySelection(currentTime) {{
            document.querySelectorAll('.gallery-card').forEach(card => {{
                const idx = Number(card.dataset.idx || -1);
                const entry = galleryEntries.find(item => item.idx === idx);
                if (!entry) return;
                card.classList.toggle('active', Math.abs(currentTime - entry.start) <= 4.5);
            }});
        }}

        function jumpTo(time) {{
            video.currentTime = time;
            if (overlaysEnabled) updateOverlayVisibility(time);
            updateSubtitleHighlight(time);
            updateTimelineProgress(time);
            refreshGallerySelection(time);
            video.play().catch(() => {{}});
        }}

        function toggleOverlays() {{
            overlaysEnabled = !overlaysEnabled;
            const btn = document.getElementById('toggleOverlays');
            if (!overlaysEnabled) {{
                document.querySelectorAll('.enhancement-container').forEach(el => el.classList.remove('active'));
                btn.classList.remove('active');
            }} else {{
                btn.classList.add('active');
                updateOverlayVisibility(video.currentTime || 0);
            }}
        }}

        function searchSubtitles() {{
            const query = searchInput.value.toLowerCase().trim();
            const clearBtn = document.getElementById('clearBtn');
            if (!query) {{
                clearSearch();
                return;
            }}
            clearBtn.style.display = '';
            document.querySelectorAll('.subtitle-item').forEach(item => {{
                const textEl = item.querySelector('.sub-text');
                const originalText = textEl.textContent;
                if (originalText.toLowerCase().includes(query)) {{
                    item.style.display = '';
                    const regex = new RegExp('(' + escapeRegex(query) + ')', 'gi');
                    textEl.innerHTML = originalText.replace(regex, '<mark>$1</mark>');
                }} else {{
                    item.style.display = 'none';
                }}
            }});
        }}

        function clearSearch() {{
            searchInput.value = '';
            document.getElementById('clearBtn').style.display = 'none';
            document.querySelectorAll('.subtitle-item').forEach(item => {{
                item.style.display = '';
                const textEl = item.querySelector('.sub-text');
                textEl.innerHTML = textEl.textContent;
            }});
        }}

        function escapeRegex(str) {{
            return str.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
        }}

        function escapeHtml(str) {{
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }}

        function escapeAttr(str) {{
            return escapeHtml(str);
        }}

        function formatTime(seconds) {{
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
        }}

        if (subtitleList) {{
            subtitleList.addEventListener('scroll', function() {{
                isUserScrollingSubs = true;
                clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {{ isUserScrollingSubs = false; }}, 3000);
            }});
        }}

        searchInput.addEventListener('keydown', function(e) {{
            if (e.key === 'Enter') searchSubtitles();
        }});

        document.addEventListener('keydown', function(e) {{
            if (e.target.tagName === 'INPUT') return;
            if (e.code === 'Space') {{
                e.preventDefault();
                video.paused ? video.play() : video.pause();
            }} else if (e.code === 'KeyC') {{
                toggleOverlays();
            }} else if (e.code === 'KeyF') {{
                e.preventDefault();
                searchInput.focus();
            }}
        }});

        video.addEventListener('timeupdate', function() {{
            const currentTime = video.currentTime;
            if (overlaysEnabled) updateOverlayVisibility(currentTime);
            updateSubtitleHighlight(currentTime);
            updateTimelineProgress(currentTime);
            refreshGallerySelection(currentTime);
        }});

        video.addEventListener('loadedmetadata', function() {{
            adjustOverlayToVideo();
            collectGalleryEntries();
            renderGalleryStrip();
            renderEnhancementTimeline();
        }});

        window.addEventListener('resize', function() {{
            adjustOverlayToVideo();
            renderEnhancementTimeline();
        }});

        function ensureReady() {{
            collectGalleryEntries();
            renderGalleryStrip();
            renderEnhancementTimeline();
            adjustOverlayToVideo();
        }}

        ensureReady();
        requestAnimationFrame(ensureReady);
        setTimeout(ensureReady, 80);
        setTimeout(ensureReady, 240);

        const galleryObserver = new MutationObserver(function() {{
            ensureReady();
        }});
        if (gallerySource) {{
            galleryObserver.observe(gallerySource, {{ childList: true, subtree: true }});
        }}

        document.getElementById('toggleOverlays').classList.add('active');
        console.log('Video Enhancement Studio loaded');
        console.log('Transcript entries:', transcriptData.length);
        """


def test_generator():
    generator = HTMLGenerator()
    test_points = [
        {
            "timestamp": 0.0,
            "duration": 5.0,
            "content_type": "svg_animation",
            "text": "Test SVG",
            "layout": {"x": 50, "y": 50, "width": 350, "height": 250, "position": "center"},
            "content": {"type": "svg", "path": "assets/svg/test.svg"},
        },
        {
            "timestamp": 6.0,
            "duration": 4.0,
            "content_type": "text_card",
            "text": "Test Text",
            "layout": {"x": 500, "y": 100, "width": 300, "height": 200},
            "content": {
                "type": "text",
                "label": "[ Insight ]",
                "hero_text": "Test Hero",
                "explanation": "Test explanation content",
            },
        },
    ]

    html = generator.generate("test.mp4", test_points)
    with open("test_output.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✓ Test HTML generated: test_output.html")


if __name__ == "__main__":
    test_generator()
