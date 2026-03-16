"""
HTML Generator - HTML生成器 (重构版)
============================

支持增量生成和四区域布局:
- 左上: 视频播放器 + 浮层DIV
- 左下: SVG图片画廊
- 右侧: 时间戳 + 字幕面板 (搜索框在顶部)

关键特性:
1. generate_skeleton() - 先生成骨架HTML (含视频、字幕、空画廊)
2. append_content()   - 每生成一个内容就追加到HTML中
3. generate()         - 兼容旧接口，一次性生成完整HTML
"""

import os
import json
import html as html_module
from typing import List, Dict, Any, Optional


class HTMLGenerator:
    """HTML生成器 - 支持增量生成"""

    def __init__(self):
        pass

    # ================================================================
    # Public API
    # ================================================================

    def generate_skeleton(
        self,
        video_source: str,
        transcript_path: str,
        html_path: str,
        concept_graph: Dict = None
    ) -> str:
        """
        生成初始HTML骨架 (含视频、字幕面板、空SVG画廊)
        在Phase 6之前调用，用户可立即在浏览器中打开
        """
        video_src = self._resolve_video_source(video_source)
        transcript_data = self._parse_transcript(transcript_path)

        html_content = self._build_skeleton_html(video_src, transcript_data, concept_graph or {})

        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"  ✓ HTML skeleton generated: {html_path}")
        return html_path

    def append_content(self, html_path: str, point: Dict, idx: int):
        """
        将一个新的enhancement_point追加到现有HTML文件中
        每次生成一个SVG/文字后调用，实现增量更新
        """
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 生成overlay HTML (视频浮层)
        overlay_html = self._generate_overlay_html(point, idx)
        # 生成gallery item HTML (画廊缩略图)
        gallery_html = self._generate_gallery_item_html(point, idx)
        focus_html = self._generate_focus_panel_item_html(point, idx)
        content_type = point.get('content', {}).get('type', 'text')

        # 在标记位置插入新内容
        html_content = html_content.replace(
            '<!-- OVERLAY_MARKER -->',
            overlay_html + '\n            <!-- OVERLAY_MARKER -->'
        )
        html_content = html_content.replace(
            '<!-- GALLERY_MARKER -->',
            gallery_html + '\n                <!-- GALLERY_MARKER -->'
        )
        if content_type == 'mechanism_chain':
            html_content = html_content.replace(
                '<!-- MECHANISM_PANEL_MARKER -->',
                focus_html + '\n                    <!-- MECHANISM_PANEL_MARKER -->'
            )
        elif content_type == 'misconception':
            html_content = html_content.replace(
                '<!-- MISCONCEPTION_PANEL_MARKER -->',
                focus_html + '\n                    <!-- MISCONCEPTION_PANEL_MARKER -->'
            )

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"    ✓ Appended [{point.get('content_type', 'unknown')}] #{idx} to HTML")

    def generate(
        self,
        video_source: str,
        enhancement_points: List[Dict],
        transcript_path: str = None
    ) -> str:
        """
        兼容旧接口: 一次性生成完整HTML
        """
        video_src = self._resolve_video_source(video_source)
        transcript_data = self._parse_transcript(transcript_path) if transcript_path else []

        html_content = self._build_skeleton_html(video_src, transcript_data, {})

        # 依次追加所有enhancement points
        for idx, point in enumerate(enhancement_points):
            overlay_html = self._generate_overlay_html(point, idx)
            gallery_html = self._generate_gallery_item_html(point, idx)
            focus_html = self._generate_focus_panel_item_html(point, idx)
            content_type = point.get('content', {}).get('type', 'text')

            html_content = html_content.replace(
                '<!-- OVERLAY_MARKER -->',
                overlay_html + '\n            <!-- OVERLAY_MARKER -->'
            )
            html_content = html_content.replace(
                '<!-- GALLERY_MARKER -->',
                gallery_html + '\n                <!-- GALLERY_MARKER -->'
            )
            if content_type == 'mechanism_chain':
                html_content = html_content.replace(
                    '<!-- MECHANISM_PANEL_MARKER -->',
                    focus_html + '\n                    <!-- MECHANISM_PANEL_MARKER -->'
                )
            elif content_type == 'misconception':
                html_content = html_content.replace(
                    '<!-- MISCONCEPTION_PANEL_MARKER -->',
                    focus_html + '\n                    <!-- MISCONCEPTION_PANEL_MARKER -->'
                )

        return html_content

    # ================================================================
    # Private: HTML骨架构建
    # ================================================================

    def _build_skeleton_html(self, video_src: str, transcript_data: List[Dict], concept_graph: Dict) -> str:
        """构建完整HTML骨架"""
        transcript_json = json.dumps(transcript_data, ensure_ascii=False)
        concept_graph_json = json.dumps(concept_graph or {}, ensure_ascii=False)
        subtitle_entries_html = self._generate_subtitle_entries(transcript_data)
        concept_graph_html = self._generate_concept_graph_html(concept_graph or {})

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Enhancement Studio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
{self._generate_css()}
    </style>
</head>
<body>
    <!-- ========== Header ========== -->
    <header class="app-header">
        <div class="header-left">
            <div class="logo">
                <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                    <rect width="28" height="28" rx="6" fill="url(#logoGrad)"/>
                    <path d="M8 14L12 10L16 14L20 10" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M8 18L12 14L16 18L20 14" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.6"/>
                    <defs>
                        <linearGradient id="logoGrad" x1="0" y1="0" x2="28" y2="28">
                            <stop stop-color="#6366f1"/>
                            <stop offset="1" stop-color="#8b5cf6"/>
                        </linearGradient>
                    </defs>
                </svg>
                <span class="logo-text">Video Enhancement Studio</span>
            </div>
        </div>
        <div class="header-right">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="搜索字幕内容..." autocomplete="off">
                <button id="searchBtn" onclick="searchSubtitles()">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.5"/>
                        <path d="M11 11L14 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    搜索
                </button>
                <button id="clearBtn" onclick="clearSearch()" style="display:none">清除</button>
            </div>
        </div>
    </header>

    <!-- ========== Main Content ========== -->
    <div class="main-content">
        <!-- Left Panel: Video + Gallery -->
        <div class="left-panel">
            <!-- Video Section -->
            <div class="video-section">
                <div class="video-wrapper">
                    <video id="mainVideo" controls>
                        <source src="{video_src}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                    <!-- Overlay Container -->
                    <div id="overlayContainer">
            <!-- OVERLAY_MARKER -->
                    </div>
                </div>
                <!-- Timeline Markers Bar -->
                <div class="timeline-bar" id="timelineBar">
                    <div class="timeline-progress" id="timelineProgress"></div>
                </div>
                <!-- Video Controls -->
                <div class="video-controls">
                    <button id="toggleOverlays" onclick="toggleOverlays()" title="切换浮层显示">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                            <rect x="1" y="3" width="14" height="10" rx="1" stroke="currentColor" stroke-width="1.2" fill="none"/>
                            <rect x="3" y="5" width="5" height="4" rx="0.5" fill="currentColor" opacity="0.4"/>
                        </svg>
                        浮层
                    </button>
                    <span class="video-time" id="videoTimeDisplay">00:00 / 00:00</span>
                </div>
            </div>
            <div class="insight-row">
                <div class="focus-panel mechanism-panel">
                    <div class="focus-panel-header">
                        <h3>⚙️ 机制链</h3>
                        <span class="focus-panel-count" id="mechanismCount">0 条</span>
                    </div>
                    <div class="focus-panel-list" id="mechanismList">
                    <!-- MECHANISM_PANEL_MARKER -->
                    </div>
                    <div class="focus-panel-empty" id="mechanismEmpty">暂无机制链命中</div>
                </div>
                <div class="focus-panel misconception-panel">
                    <div class="focus-panel-header">
                        <h3>⚠️ 误解纠正</h3>
                        <span class="focus-panel-count" id="misconceptionCount">0 条</span>
                    </div>
                    <div class="focus-panel-list" id="misconceptionList">
                    <!-- MISCONCEPTION_PANEL_MARKER -->
                    </div>
                    <div class="focus-panel-empty" id="misconceptionEmpty">暂无误解纠正命中</div>
                </div>
            </div>
        </div>

        <!-- Right Panel: Subtitles (Top) & Gallery (Bottom) -->
        <div class="right-panel">
            <div class="subtitle-section">
                <div class="subtitle-header">
                    <h3>📝 字幕时间线</h3>
                    <span class="subtitle-count">{len(transcript_data)} 条字幕</span>
                </div>
                <div class="subtitle-list" id="subtitleList">
{subtitle_entries_html}
                </div>
            </div>
            
            <!-- SVG Gallery Section (Moved from left to bottom-right) -->
            <div class="gallery-section">
                <div class="gallery-header">
                    <h3>📊 增强内容画廊</h3>
                    <span class="gallery-count" id="galleryCount">0 个增强点</span>
                </div>
                <div class="gallery-grid" id="galleryGrid">
                <!-- GALLERY_MARKER -->
                </div>
                <div class="gallery-empty" id="galleryEmpty">
                    <p>⏳ 等待内容生成中...</p>
                    <p class="hint">生成的SVG动画和文字卡片将显示在此处</p>
                </div>
            </div>
            {concept_graph_html}
        </div>
    </div>

    <!-- ========== SVG Preview Modal ========== -->
    <div class="modal-overlay" id="svgModal" onclick="closeSvgModal(event)">
        <div class="modal-content" id="svgModalContent">
            <button class="modal-close" onclick="closeSvgModal()">&times;</button>
            <div class="modal-body" id="svgModalBody"></div>
        </div>
    </div>

    <!-- ========== Keyboard Shortcuts Panel ========== -->
    <div class="shortcuts-panel" id="shortcutsPanel">
        <div class="shortcuts-header">
            <span>⌨️ 快捷键</span>
            <button onclick="toggleShortcuts()">×</button>
        </div>
        <div class="shortcuts-list">
            <div><kbd>Space</kbd> 播放/暂停</div>
            <div><kbd>C</kbd> 切换浮层</div>
            <div><kbd>F</kbd> 搜索字幕</div>
            <div><kbd>Esc</kbd> 关闭弹窗</div>
            <div><kbd>?</kbd> 快捷键帮助</div>
        </div>
    </div>
    <button class="shortcuts-trigger" onclick="toggleShortcuts()" title="快捷键帮助">⌨️</button>

    <script>
{self._generate_javascript(transcript_json, concept_graph_json)}
    </script>
</body>
</html>'''

    # ================================================================
    # Private: 内容HTML生成
    # ================================================================

    # 布局画布常量 (layout_agent 使用的坐标系)
    LAYOUT_CANVAS_W = 1920
    LAYOUT_CANVAS_H = 1080

    def _generate_overlay_html(self, point: Dict, idx: int) -> str:
        """生成单个overlay容器HTML
        
        关键：所有坐标从 layout_agent 的 1920x1080 绝对坐标
        转换为百分比定位，这样 overlay 会随容器自适应缩放
        """
        layout = point.get('layout', {})
        content = point.get('content', {})
        content_type = content.get('type', 'text')

        if content_type == 'svg':
            style = self._get_svg_container_style(layout)
        else:
            # 将绝对坐标转为百分比（相对于1920x1080画布）
            x = layout.get('x', 50)
            y = layout.get('y', 50)
            width = layout.get('width', 350)
            height = layout.get('height', 250)
            left_pct = x / self.LAYOUT_CANVAS_W * 100
            top_pct = y / self.LAYOUT_CANVAS_H * 100

            desired_w_pct = max(width / self.LAYOUT_CANVAS_W * 100, 22.0)
            available_right_pct = max(16.0, 98.0 - left_pct)
            fit_w_pct = min(desired_w_pct, available_right_pct)
            h_pct_max = max(height / self.LAYOUT_CANVAS_H * 100 * 2.15, 42.0)
            scale = max(0.72, min(1.0, fit_w_pct / max(desired_w_pct, 1.0)))
            edge_class = " right-edge-card" if left_pct > 58.0 else ""
            style = (
                f'left: {left_pct:.2f}%; top: {top_pct:.2f}%; '
                f'width: {fit_w_pct:.2f}%; max-width: {fit_w_pct:.2f}%; '
                f'height: auto; max-height: {h_pct_max:.2f}%; min-height: 5%; '
                f'--overlay-scale: {scale:.3f};'
            )

        content_html = self._generate_content_html(content, point)
        container_class = "enhancement-container"
        if content_type == 'svg':
            container_class += " svg-overlay"
        elif content_type == 'mechanism_chain':
            container_class += " mechanism-overlay"
        elif content_type == 'misconception':
            container_class += " misconception-overlay"
        if content_type != 'svg' and left_pct > 58.0:
            container_class += edge_class

        timestamp = point.get('timestamp', 0)
        duration = point.get('duration', 5)

        return f'''            <div class="{container_class}"
                 id="container-{idx}"
                 data-start="{timestamp}"
                 data-end="{timestamp + duration}"
                 data-type="{point.get('content_type', 'unknown')}"
                 style="{style}">
                {content_html}
            </div>'''

    def _generate_gallery_item_html(self, point: Dict, idx: int) -> str:
        """生成单个画廊项目HTML"""
        content = point.get('content', {})
        content_type = content.get('type', 'text')
        timestamp = point.get('timestamp', 0)
        time_str = self._format_time(timestamp)
        topic = point.get('text', '')[:50]
        escaped_topic = html_module.escape(topic)

        if content_type == 'svg':
            svg_path = content.get('path', '')
            # 缩略图使用img标签加载外部文件，大幅缩小HTML体积
            if svg_path:
                thumb_html = f'<div class="gallery-thumb svg-thumb"><img src="{svg_path}" loading="lazy" style="width: 100%; height: 100%; object-fit: contain;"></div>'
            else:
                thumb_html = '<div class="gallery-thumb svg-thumb placeholder-thumb">SVG</div>'

            return f'''                <div class="gallery-item" data-start="{timestamp}"
                     onclick="jumpTo({timestamp})"
                     ondblclick="previewSvg({idx})"
                     title="{escaped_topic}&#10;单击跳转 | 双击预览">
                    {thumb_html}
                    <div class="gallery-info">
                        <span class="gallery-time">{time_str}</span>
                        <span class="gallery-label">🎨 SVG</span>
                    </div>
                </div>'''
        elif content_type == 'mechanism_chain':
            title = html_module.escape(content.get('chain_title', topic)[:34])
            return f'''                <div class="gallery-item mechanism-gallery-item" data-start="{timestamp}"
                     onclick="jumpTo({timestamp})"
                     title="{escaped_topic}">
                    <div class="gallery-thumb text-thumb mechanism-thumb">
                        <span class="text-thumb-icon">⚙️</span>
                        <span class="text-thumb-title">{title}</span>
                    </div>
                    <div class="gallery-info">
                        <span class="gallery-time">{time_str}</span>
                        <span class="gallery-label">机制链</span>
                    </div>
                </div>'''
        elif content_type == 'misconception':
            title = html_module.escape(content.get('hero_text', topic)[:34])
            return f'''                <div class="gallery-item misconception-gallery-item" data-start="{timestamp}"
                     onclick="jumpTo({timestamp})"
                     title="{escaped_topic}">
                    <div class="gallery-thumb text-thumb misconception-thumb">
                        <span class="text-thumb-icon">⚠️</span>
                        <span class="text-thumb-title">{title}</span>
                    </div>
                    <div class="gallery-info">
                        <span class="gallery-time">{time_str}</span>
                        <span class="gallery-label">误解纠正</span>
                    </div>
                </div>'''
        else:
            title = content.get('title', topic)[:30]
            escaped_title = html_module.escape(title)

            return f'''                <div class="gallery-item text-gallery-item" data-start="{timestamp}"
                     onclick="jumpTo({timestamp})"
                     title="{escaped_topic}">
                    <div class="gallery-thumb text-thumb">
                        <span class="text-thumb-icon">📝</span>
                        <span class="text-thumb-title">{escaped_title}</span>
                    </div>
                    <div class="gallery-info">
                        <span class="gallery-time">{time_str}</span>
                        <span class="gallery-label">文字</span>
                    </div>
                </div>'''

    def _generate_focus_panel_item_html(self, point: Dict, idx: int) -> str:
        content = point.get('content', {})
        content_type = content.get('type', 'text')
        if content_type not in ('mechanism_chain', 'misconception'):
            return ''

        timestamp = point.get('timestamp', 0)
        time_str = self._format_time(timestamp)

        if content_type == 'mechanism_chain':
            title = html_module.escape(content.get('chain_title', point.get('text', '机制链'))[:48])
            stages = content.get('stages', [])[:3]
            stage_preview = " → ".join(html_module.escape(str(stage)) for stage in stages)
            return (
                f'                    <div class="focus-item mechanism-focus-item" data-start="{timestamp}" onclick="jumpTo({timestamp})">'
                f'<div class="focus-item-top"><span class="focus-item-time">{time_str}</span><span class="focus-item-badge">机制链</span></div>'
                f'<div class="focus-item-title">{title}</div>'
                f'<div class="focus-item-sub">{stage_preview}</div>'
                f'</div>'
            )

        hero_text = html_module.escape(content.get('hero_text', point.get('text', '误解纠正'))[:60])
        explanation = html_module.escape(content.get('explanation', '')[:90])
        return (
            f'                    <div class="focus-item misconception-focus-item" data-start="{timestamp}" onclick="jumpTo({timestamp})">'
            f'<div class="focus-item-top"><span class="focus-item-time">{time_str}</span><span class="focus-item-badge">误解纠正</span></div>'
            f'<div class="focus-item-title">{hero_text}</div>'
            f'<div class="focus-item-sub">{explanation}</div>'
            f'</div>'
        )

    def _generate_content_html(self, content: Dict, point: Dict) -> str:
        """生成内容HTML (复用原有逻辑)"""
        content_type = content.get('type', 'text')

        if content_type == 'svg':
            svg_path = content.get('path', '')

            # 视频浮层使用 object 标签加载，保留SVG内部CSS动画特性
            if svg_path:
                return f'<object data="{svg_path}" type="image/svg+xml" class="svg-content" style="width: 100%; height: 100%; overflow: hidden; pointer-events: none;"></object>'
            else:
                return '<div class="placeholder">SVG Content</div>'

        elif content_type == 'text':
            label = content.get('label', '[ 💬 Note ]')
            hero_text = content.get('hero_text', '')
            explanation = content.get('explanation', '')
            style_dict = content.get('style', {})

            if not hero_text and not explanation:
                text = point.get('text', '')
                return f'<div class="text-content premium-glassmorphism"><div class="card-hero">{text}</div></div>'
            
            # CSS inline variables for dynamic accent coloring
            accent_color = style_dict.get('accent_color', '#00f3ff')
            style_attr = f'style="--card-accent: {accent_color};"'

            result = f'<div class="text-content premium-glassmorphism" {style_attr}>'
            if label:
                result += f'<div class="card-label">{label}</div>'
            if hero_text:
                result += f'<h3 class="card-hero">{hero_text}</h3>'
            if explanation:
                result += f'<div class="card-explanation">{explanation}</div>'
            result += '</div>'
            return result
        elif content_type == 'misconception':
            label = content.get('label', '[ ⚠ Misconception Alert ]')
            hero_text = html_module.escape(content.get('hero_text', ''))
            explanation = html_module.escape(content.get('explanation', ''))
            why_confusing = html_module.escape(content.get('why_confusing', ''))
            wrong_detail = html_module.escape(content.get('wrong_detail', ''))
            correct_detail = html_module.escape(content.get('correct_detail', ''))
            variant = content.get('variant', 'compare')
            accent_color = content.get('style', {}).get('accent_color', '#f59e0b')
            if variant == 'stacked':
                board_html = (
                    f'<div class="misconception-stack">'
                    f'<div class="misconception-lane wrong-lane"><span class="misconception-tag">易错理解</span>'
                    f'<div class="misconception-main">{hero_text}</div>'
                    f'<div class="misconception-detail">{wrong_detail}</div></div>'
                    f'<div class="misconception-arrow stack-arrow">↓</div>'
                    f'<div class="misconception-lane correct-lane"><span class="misconception-tag correct">正确理解</span>'
                    f'<div class="card-explanation">{explanation}</div>'
                    f'<div class="misconception-detail">{correct_detail}</div></div>'
                    f'</div>'
                )
            else:
                board_html = (
                    f'<div class="misconception-board">'
                    f'<div class="misconception-lane wrong-lane"><span class="misconception-tag">易错理解</span>'
                    f'<div class="misconception-main">{hero_text}</div>'
                    f'<div class="misconception-detail">{wrong_detail}</div></div>'
                    f'<div class="misconception-arrow">→</div>'
                    f'<div class="misconception-lane correct-lane"><span class="misconception-tag correct">正确理解</span>'
                    f'<div class="card-explanation">{explanation}</div>'
                    f'<div class="misconception-detail">{correct_detail}</div></div>'
                    f'</div>'
                )
            return (
                f'<div class="text-content misconception-card premium-glassmorphism" '
                f'style="--card-accent: {accent_color};">'
                f'<div class="card-label">{html_module.escape(label)}</div>'
                f'{board_html}'
                f'<div class="misconception-why">{why_confusing}</div>'
                f'</div>'
            )
        elif content_type == 'mechanism_chain':
            accent_color = content.get('style', {}).get('accent_color', '#00f3ff')
            title = html_module.escape(content.get('chain_title', 'Mechanism Chain'))
            stages = content.get('stages', [])
            current_focus = int(content.get('current_focus_stage', 0))
            variant = content.get('variant', 'path')
            stage_html = []
            for idx, stage in enumerate(stages):
                cls = 'mechanism-stage'
                if idx < current_focus:
                    cls += ' completed'
                elif idx == current_focus:
                    cls += ' active'
                if variant == 'stacked':
                    stage_html.append(
                        f'<div class="{cls} stacked-stage"><span class="stage-index">STEP {idx + 1}</span><span class="mechanism-stage-text">{html_module.escape(str(stage))}</span></div>'
                    )
                else:
                    connector_class = 'mechanism-connector active' if idx < current_focus else 'mechanism-connector'
                    connector = f'<div class="{connector_class}"><span class="mechanism-connector-line"></span><span class="mechanism-connector-dot"></span></div>' if idx < len(stages) - 1 else ''
                    stage_html.append(
                        f'<div class="mechanism-path-segment">'
                        f'<div class="{cls} node-stage"><div class="mechanism-node-core"></div><div class="mechanism-node-copy"><span class="stage-index">STEP {idx + 1}</span><span class="mechanism-stage-text">{html_module.escape(str(stage))}</span></div></div>'
                        f'{connector}'
                        f'</div>'
                    )
            track_class = 'mechanism-stack-track' if variant == 'stacked' else 'mechanism-path-track'
            return (
                f'<div class="mechanism-chain-card premium-glassmorphism" style="--card-accent: {accent_color};">'
                f'<div class="card-label">[ ⚙ Mechanism Chain ]</div>'
                f'<div class="mechanism-title">{title}</div>'
                f'<div class="{track_class}">{"".join(stage_html)}</div>'
                f'</div>'
            )

        return '<div class="placeholder">Content</div>'

    def _generate_concept_graph_html(self, concept_graph: Dict) -> str:
        if not concept_graph or not concept_graph.get('nodes'):
            return ''

        title = html_module.escape(concept_graph.get('graph_title', 'Global Concept Graph'))
        summary = html_module.escape(concept_graph.get('summary', ''))
        nodes_html = []
        for node in concept_graph.get('nodes', []):
            label = html_module.escape(node.get('label', 'Node'))
            node_id = html_module.escape(node.get('id', ''))
            nodes_html.append(
                f'<div class="concept-node" data-node-id="{node_id}">'
                f'<span class="concept-node-label">{label}</span>'
                f'<span class="concept-node-weight">{node.get("weight", 1)}</span>'
                f'</div>'
            )

        edges_html = []
        for edge in concept_graph.get('edges', [])[:6]:
            edges_html.append(
                f'<div class="concept-edge" data-source="{html_module.escape(edge.get("source", ""))}" data-target="{html_module.escape(edge.get("target", ""))}">'
                f'<span class="concept-edge-label">{html_module.escape(edge.get("label", edge.get("source", "")) or "linked")}</span>'
                f'<span class="concept-edge-route">{html_module.escape(edge.get("source", ""))} → {html_module.escape(edge.get("target", ""))}</span>'
                f'</div>'
            )

        return f'''
            <div class="concept-graph-section" id="conceptGraphSection">
                <div class="concept-graph-header">
                    <h3>🧠 全局概念图</h3>
                    <span class="concept-graph-count">{len(concept_graph.get('nodes', []))} 个节点</span>
                </div>
                <div class="concept-graph-title">{title}</div>
                <div class="concept-graph-summary">{summary}</div>
                <div class="concept-graph-nodes" id="conceptGraphNodes">
                    {"".join(nodes_html)}
                </div>
                <div class="concept-graph-edges" id="conceptGraphEdges">
                    {"".join(edges_html)}
                </div>
            </div>'''

    def _generate_subtitle_entries(self, transcript_data: List[Dict]) -> str:
        """生成字幕条目HTML"""
        if not transcript_data:
            return '                <div class="subtitle-empty">暂无字幕数据</div>'

        entries = []
        for item in transcript_data:
            start = item.get('start', 0)
            end = item.get('end', 0)
            text = html_module.escape(item.get('text', ''))
            time_str = self._format_time(start)

            entries.append(
                f'                <div class="subtitle-item" data-start="{start}" data-end="{end}" onclick="jumpTo({start})">'
                f'<span class="sub-time">{time_str}</span>'
                f'<span class="sub-text">{text}</span>'
                f'</div>'
            )

        return '\n'.join(entries)

    # ================================================================
    # Private: SVG容器样式
    # ================================================================

    def _get_svg_container_style(self, layout: Dict) -> str:
        """计算SVG容器样式
        
        使用 layout_agent 给出的 (x, y, w, h) 像素值，
        转为百分比定位（相对于1920x1080画布）
        """
        # 优先使用精确坐标
        x = layout.get('x', None)
        y = layout.get('y', None)
        w = layout.get('width', None)
        h = layout.get('height', None)
        
        if x is not None and y is not None and w is not None and h is not None:
            left_pct = x / self.LAYOUT_CANVAS_W * 100
            top_pct = y / self.LAYOUT_CANVAS_H * 100
            w_pct = w / self.LAYOUT_CANVAS_W * 100
            h_pct = h / self.LAYOUT_CANVAS_H * 100
            return f'left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {w_pct:.2f}%; height: {h_pct:.2f}%;'
        
        # 回退：使用位置名称
        position = layout.get('position', 'center')
        if position == 'top-left':
            return 'left: 2%; top: 2%; width: 55%; height: 55%;'
        elif position == 'top-right':
            return 'right: 2%; top: 2%; width: 55%; height: 55%;'
        elif position == 'bottom-left':
            return 'left: 2%; bottom: 2%; width: 55%; height: 55%;'
        elif position == 'bottom-right':
            return 'right: 2%; bottom: 2%; width: 55%; height: 55%;'
        elif position in ('full', 'center'):
            return 'left: 5%; top: 5%; width: 90%; height: 90%;'
        else:
            return 'left: 5%; top: 5%; width: 90%; height: 90%;'

    # ================================================================
    # Private: 辅助函数
    # ================================================================

    def _resolve_video_source(self, video_source: str) -> str:
        """解析视频路径"""
        if os.path.isabs(video_source):
            return f"file:///{video_source.replace(os.sep, '/')}"
        return video_source

    def _parse_transcript(self, transcript_path: str) -> List[Dict]:
        """解析whisper_transcript.txt"""
        if not transcript_path or not os.path.exists(transcript_path):
            return []

        transcript = []
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        transcript.append({
                            'start': float(parts[0]),
                            'end': float(parts[1]),
                            'text': parts[2]
                        })
        except Exception as e:
            print(f"  ⚠ 解析字幕文件失败: {e}")

        return transcript

    def _format_time(self, seconds: float) -> str:
        """格式化时间为 MM:SS"""
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"

    # ================================================================
    # Private: CSS样式
    # ================================================================

    def _generate_css(self) -> str:
        return '''
        /* ========== Reset & Base ========== */
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg-primary: #0f1117;
            --bg-secondary: #1a1b25;
            --bg-tertiary: #22233a;
            --bg-card: #282940;
            --border: #2d2e45;
            --border-light: #3d3e55;
            --accent: #6366f1;
            --accent-light: #818cf8;
            --accent-glow: rgba(99, 102, 241, 0.3);
            --success: #34d399;
            --warning: #fbbf24;
            --text-primary: #f1f1f4;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --highlight-bg: rgba(99, 102, 241, 0.15);
            --header-height: 56px;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            overflow: hidden;
            height: 100vh;
        }

        /* ========== Header ========== */
        .app-header {
            height: var(--header-height);
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            z-index: 100;
        }

        .header-left { display: flex; align-items: center; }

        .logo {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo-text {
            font-size: 16px;
            font-weight: 600;
            background: linear-gradient(135deg, var(--accent-light), #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.3px;
        }

        .header-right { display: flex; align-items: center; }

        .search-box {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .search-box input {
            width: 280px;
            height: 34px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0 12px;
            color: var(--text-primary);
            font-size: 13px;
            font-family: inherit;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        .search-box input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }

        .search-box input::placeholder {
            color: var(--text-muted);
        }

        .search-box button {
            height: 34px;
            padding: 0 14px;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-family: inherit;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.2s;
        }

        #searchBtn {
            background: var(--accent);
            color: white;
        }

        #searchBtn:hover { background: var(--accent-light); }

        #clearBtn {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }

        #clearBtn:hover { background: var(--bg-card); }

        /* ========== Main Layout ========== */
        .main-content {
            display: flex;
            height: calc(100vh - var(--header-height));
        }

        .left-panel {
            width: 66.66%;
            display: grid;
            grid-template-rows: minmax(0, 75%) minmax(180px, 25%);
            border-right: 1px solid var(--border);
            min-width: 0;
            background: var(--bg-primary);
        }

        .right-panel {
            width: 33.33%;
            display: grid;
            grid-template-rows: minmax(0, 40%) minmax(0, 28%) minmax(200px, 32%);
            min-width: 0;
            background: var(--bg-secondary);
        }

        .subtitle-section {
            display: flex;
            flex-direction: column;
            min-height: 0;
        }

        /* ========== Video Section ========== */
        .video-section {
            display: flex;
            flex-direction: column;
            background: #000;
            border-bottom: 1px solid var(--border);
            min-height: 0;
        }

        .insight-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            padding: 12px;
            background: var(--bg-secondary);
            min-height: 0;
        }

        .video-wrapper {
            flex: 1;
            position: relative;
            overflow: hidden;
        }

        #mainVideo {
            width: 100%;
            height: 100%;
            object-fit: contain;
            background: #000;
        }

        #overlayContainer {
            position: absolute;
            /* 由JS动态计算，匹配object-fit:contain后的实际视频区域 */
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 10;
        }

        .enhancement-container {
            position: absolute;
            opacity: 0;
            transition: opacity 0.5s ease-in-out;
            pointer-events: none;
            min-width: 0;
        }

        .enhancement-container.active { opacity: 1; }

        .right-edge-card .premium-glassmorphism {
            padding: 18px 22px;
        }

        /* SVG Overlay */
        .svg-overlay {
            display: flex;
            align-items: center;
            justify-content: center;
            /* In-Video Cinematic Effect: blend with background */
            mix-blend-mode: screen; 
            filter: drop-shadow(0 0 20px rgba(0,0,0,0.5));
        }

        .mechanism-overlay,
        .misconception-overlay {
            display: flex;
            align-items: stretch;
            justify-content: center;
        }

        .svg-wrapper {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .svg-wrapper svg {
            width: 100%;
            height: 100%;
            max-width: 100%;
            max-height: 100%;
        }

        .svg-content {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

        /* Glassmorphism & Theme - Premium Minimalist Upgrade */
        .premium-glassmorphism {
            background: rgba(10, 10, 15, 0.45);
            backdrop-filter: blur(35px) saturate(180%);
            -webkit-backdrop-filter: blur(35px) saturate(180%);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-left: 4px solid var(--card-accent, #6366f1);
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255,255,255,0.1);
            border-radius: 14px;
            padding: 24px 32px;
            color: #ffffff;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            gap: 12px;
            /* In-Video effect */
            mix-blend-mode: normal; 
            width: 100%;
            height: 100%;
            overflow: hidden;
        }

        .text-content {
            width: 100%;
            height: auto;
            display: flex;
            overflow: hidden;
            min-width: 0;
        }

        .card-label { 
            font-size: calc(13px * var(--overlay-scale, 1));
            font-weight: 600;
            letter-spacing: 0.5px;
            color: var(--card-accent, #a78bfa);
            text-transform: uppercase;
            background: rgba(255, 255, 255, 0.1);
            padding: 4px 10px;
            border-radius: 20px;
            align-self: flex-start;
            margin-bottom: 4px;
        }
        
        .card-hero { 
            font-size: calc(17px * var(--overlay-scale, 1)); 
            font-weight: 300; 
            line-height: 1.3; 
            letter-spacing: -0.5px;
            margin: 0; 
            text-shadow: 0 2px 10px rgba(0,0,0,0.5);
            color: #ffffff;
            overflow-wrap: anywhere;
        }
        
        .card-explanation { 
            font-size: calc(15px * var(--overlay-scale, 1)); 
            line-height: 1.6; 
            color: rgba(255, 255, 255, 0.75); 
            margin-top: 4px;
            font-weight: 400;
            overflow-wrap: break-word;
            word-break: normal;
        }

        .misconception-card,
        .mechanism-chain-card {
            width: 100%;
            height: 100%;
            overflow-y: auto;
        }

        .misconception-row {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .misconception-board {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
            gap: 12px;
            align-items: stretch;
        }

        .misconception-lane {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 14px;
            background: rgba(255,255,255,0.04);
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-width: 0;
        }

        .misconception-stack {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .wrong-lane {
            background: linear-gradient(180deg, rgba(245,158,11,0.14), rgba(245,158,11,0.04));
        }

        .correct-lane {
            background: linear-gradient(180deg, rgba(52,211,153,0.14), rgba(52,211,153,0.04));
        }

        .misconception-arrow {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: calc(28px * var(--overlay-scale, 1));
            color: var(--card-accent, #f59e0b);
            font-weight: 700;
            opacity: 0.9;
            animation: misconceptionShift 1.6s ease-in-out infinite;
        }

        .misconception-tag {
            font-size: calc(11px * var(--overlay-scale, 1));
            font-weight: 700;
            color: #fbbf24;
            text-transform: uppercase;
            letter-spacing: 0.7px;
        }

        .misconception-tag.correct { color: #34d399; }

        .misconception-main {
            font-size: calc(20px * var(--overlay-scale, 1));
            line-height: 1.45;
            color: #fff7ed;
            overflow-wrap: break-word;
            word-break: normal;
        }

        .misconception-detail {
            font-size: calc(12px * var(--overlay-scale, 1));
            line-height: 1.45;
            color: rgba(255, 255, 255, 0.60);
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
        }

        .misconception-why {
            font-size: calc(13px * var(--overlay-scale, 1));
            line-height: 1.5;
            color: rgba(255, 255, 255, 0.68);
            padding-top: 6px;
            border-top: 1px solid rgba(255,255,255,0.08);
            overflow-wrap: break-word;
            word-break: normal;
        }

        .mechanism-title {
            font-size: calc(22px * var(--overlay-scale, 1));
            font-weight: 500;
            line-height: 1.35;
        }

        .mechanism-path-track {
            display: flex;
            align-items: stretch;
            gap: 8px;
            margin-top: 10px;
            min-width: 0;
            overflow: hidden;
        }

        .mechanism-stack-track {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 10px;
            min-width: 0;
        }

        .mechanism-path-segment {
            display: flex;
            align-items: center;
            min-width: 0;
            flex: 1 1 0;
        }

        .mechanism-stage {
            display: flex;
            gap: 8px;
            color: rgba(255,255,255,0.82);
            min-width: 0;
            flex: 1 1 0;
            animation: mechanismReveal 0.7s ease forwards;
        }

        .node-stage {
            align-items: center;
        }

        .mechanism-node-core {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: rgba(255,255,255,0.16);
            border: 2px solid rgba(34,211,238,0.35);
            box-shadow: 0 0 0 6px rgba(34,211,238,0.06);
            flex-shrink: 0;
            position: relative;
        }

        .mechanism-node-copy {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-left: 10px;
            min-width: 0;
            padding: 10px 12px 10px 0;
        }

        .mechanism-stage.active {
            color: #ffffff;
        }

        .mechanism-stage.active .mechanism-node-core {
            background: #67e8f9;
            border-color: #a5f3fc;
            box-shadow: 0 0 0 8px rgba(34,211,238,0.10), 0 0 22px rgba(103,232,249,0.75);
            animation: mechanismPulse 1.5s ease-in-out infinite;
        }

        .mechanism-stage.completed {
            color: rgba(255,255,255,0.92);
        }

        .mechanism-stage.completed .mechanism-node-core {
            background: rgba(34,211,238,0.78);
            border-color: rgba(103,232,249,0.9);
            box-shadow: 0 0 0 7px rgba(34,211,238,0.08), 0 0 16px rgba(34,211,238,0.28);
        }

        .mechanism-stage-text {
            overflow-wrap: break-word;
            word-break: normal;
            line-height: 1.45;
            font-size: calc(14px * var(--overlay-scale, 1));
        }

        .stacked-stage {
            min-height: auto;
        }

        .mechanism-connector {
            width: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            flex-shrink: 0;
        }

        .mechanism-connector-line {
            display: block;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, rgba(34,211,238,0.08), rgba(34,211,238,0.24));
            transform-origin: left center;
            animation: mechanismFlow 1.1s ease forwards;
        }

        .mechanism-connector-dot {
            position: absolute;
            right: -1px;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: rgba(34,211,238,0.35);
            box-shadow: 0 0 10px rgba(34,211,238,0.22);
        }

        .mechanism-connector.active .mechanism-connector-line {
            background: linear-gradient(90deg, rgba(34,211,238,0.65), rgba(34,211,238,1));
            box-shadow: 0 0 14px rgba(34,211,238,0.22);
        }

        .mechanism-connector.active .mechanism-connector-dot {
            background: #67e8f9;
            box-shadow: 0 0 24px rgba(103,232,249,0.75);
        }

        .stage-index {
            font-size: calc(11px * var(--overlay-scale, 1));
            font-weight: 700;
            color: var(--card-accent, #818cf8);
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }

        /* Timeline Bar */
        .timeline-bar {
            height: 6px;
            background: var(--bg-tertiary);
            position: relative;
            cursor: pointer;
            flex-shrink: 0;
        }

        .timeline-progress {
            height: 100%;
            background: var(--accent);
            width: 0%;
            transition: width 0.1s linear;
        }

        .timeline-dot {
            position: absolute;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--warning);
            border: 1.5px solid var(--bg-primary);
            cursor: pointer;
            z-index: 2;
            transition: transform 0.15s;
        }

        .timeline-dot:hover { transform: translate(-50%, -50%) scale(1.5); }
        .timeline-dot.svg-dot { background: var(--success); }
        .timeline-dot.text-dot { background: var(--warning); }
        .timeline-dot.mechanism-dot { background: #22d3ee; }
        .timeline-dot.misconception-dot { background: #f59e0b; }

        /* Video Controls */
        .video-controls {
            height: 36px;
            background: var(--bg-secondary);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 12px;
            flex-shrink: 0;
        }

        .video-controls button {
            height: 28px;
            padding: 0 10px;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 12px;
            font-family: inherit;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.2s;
        }

        .video-controls button:hover { background: var(--bg-card); color: var(--text-primary); }
        .video-controls button.active { background: var(--accent); color: white; border-color: var(--accent); }

        .video-time {
            font-size: 12px;
            color: var(--text-muted);
            font-variant-numeric: tabular-nums;
        }

        /* ========== Gallery Section ========== */
        .gallery-section {
            display: flex;
            flex-direction: column;
            background: var(--bg-secondary);
            overflow: hidden;
            border-top: 1px solid var(--border);
            min-height: 0;
        }

        .gallery-header {
            padding: 12px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
            flex-shrink: 0;
        }

        .gallery-header h3 {
            font-size: 14px;
            font-weight: 600;
        }

        .gallery-count {
            font-size: 12px;
            color: var(--text-muted);
        }

        .gallery-grid {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            grid-auto-rows: min-content;
            gap: 16px;
            min-height: 0;
        }

        .gallery-item {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            cursor: pointer;
            transition: all 0.2s;
        }

        .gallery-item:hover {
            border-color: var(--accent);
            box-shadow: 0 4px 12px var(--accent-glow);
            transform: translateY(-3px);
        }

        .mechanism-gallery-item:hover {
            border-color: #22d3ee;
            box-shadow: 0 4px 12px rgba(34, 211, 238, 0.22);
        }

        .misconception-gallery-item:hover {
            border-color: #f59e0b;
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.22);
        }

        .gallery-thumb {
            aspect-ratio: 16 / 9;
            width: 100%;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-primary);
        }

        .svg-thumb svg {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .text-thumb {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 4px;
            padding: 12px;
        }

        .mechanism-thumb { background: linear-gradient(135deg, rgba(34,211,238,0.18), rgba(14,116,144,0.16)); }
        .misconception-thumb { background: linear-gradient(135deg, rgba(245,158,11,0.18), rgba(146,64,14,0.16)); }

        .text-thumb-icon { font-size: 24px; }

        .text-thumb-title {
            font-size: 11px;
            color: var(--text-secondary);
            text-align: center;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 100%;
        }

        .placeholder-thumb {
            font-size: 14px;
            color: var(--text-muted);
        }

        .gallery-info {
            padding: 8px 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-top: 1px solid var(--border);
            background: var(--bg-card);
        }

        .gallery-time {
            font-size: 11px;
            color: var(--accent-light);
            font-weight: 500;
            font-variant-numeric: tabular-nums;
        }

        .gallery-label {
            font-size: 10px;
            color: var(--text-muted);
        }

        .gallery-empty {
            padding: 40px 20px;
            text-align: center;
            color: var(--text-muted);
        }

        .gallery-empty .hint {
            font-size: 12px;
            margin-top: 8px;
            opacity: 0.6;
        }

        .focus-panel {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            min-height: 0;
            display: flex;
            flex-direction: column;
        }

        .focus-panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
        }

        .focus-panel-header h3 {
            font-size: 13px;
            font-weight: 600;
        }

        .focus-panel-count {
            font-size: 11px;
            color: var(--text-muted);
        }

        .focus-panel-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            padding: 10px 12px;
            flex: 1;
            overflow-y: auto;
            min-height: 0;
        }

        .focus-panel-empty {
            padding: 0 12px 12px;
            color: var(--text-muted);
            font-size: 12px;
        }

        .focus-item {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .focus-item:hover {
            transform: translateY(-2px);
        }

        .mechanism-focus-item:hover {
            border-color: #22d3ee;
            box-shadow: 0 4px 12px rgba(34, 211, 238, 0.16);
        }

        .misconception-focus-item:hover {
            border-color: #f59e0b;
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.16);
        }

        .focus-item-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 6px;
            gap: 8px;
        }

        .focus-item-time {
            font-size: 11px;
            color: var(--accent-light);
            font-variant-numeric: tabular-nums;
        }

        .focus-item-badge {
            font-size: 10px;
            color: var(--text-secondary);
        }

        .focus-item-title {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.45;
            margin-bottom: 4px;
            white-space: normal;
            overflow-wrap: break-word;
            word-break: normal;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .focus-item-sub {
            font-size: 11px;
            color: var(--text-secondary);
            line-height: 1.45;
            white-space: normal;
            overflow-wrap: break-word;
            word-break: normal;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .concept-graph-section {
            border-top: 1px solid var(--border);
            background: linear-gradient(180deg, rgba(26,27,37,0.98), rgba(18,19,29,0.98));
            padding: 14px 16px 18px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            overflow: hidden;
            min-height: 0;
        }

        .concept-graph-header,
        .concept-graph-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .concept-graph-header h3,
        .concept-graph-title {
            font-size: 14px;
            font-weight: 600;
        }

        .concept-graph-count {
            font-size: 12px;
            color: var(--text-muted);
        }

        .concept-graph-summary {
            font-size: 12px;
            line-height: 1.55;
            color: var(--text-secondary);
        }

        .concept-graph-nodes {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            overflow-y: auto;
        }

        .concept-node {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 10px;
            border-radius: 999px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.06);
            color: var(--text-secondary);
            transition: all 0.2s ease;
            opacity: 0.28;
            transform: scale(0.96);
        }

        .concept-node.revealed {
            opacity: 0.75;
            transform: scale(1);
        }

        .concept-node.active {
            color: #ffffff;
            border-color: var(--accent);
            background: rgba(99,102,241,0.18);
            box-shadow: 0 0 0 1px rgba(99,102,241,0.15) inset;
        }

        .concept-node-label { font-size: 12px; }
        .concept-node-weight {
            font-size: 10px;
            color: var(--accent-light);
            font-weight: 700;
        }

        .concept-graph-edges {
            display: grid;
            grid-template-columns: 1fr;
            gap: 4px;
            font-size: 11px;
            color: var(--text-muted);
            overflow-y: auto;
        }

        .concept-edge {
            font-size: 12px;
            color: var(--text-secondary);
            padding: 8px 10px;
            border-radius: 10px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.05);
            display: flex;
            flex-direction: column;
            gap: 4px;
            opacity: 0.22;
            transform: translateX(-4px);
            transition: all 0.2s ease;
        }

        .concept-edge.revealed {
            opacity: 0.68;
            transform: translateX(0);
        }

        .concept-edge.active {
            border-color: var(--accent-light);
            background: rgba(99,102,241,0.12);
            color: var(--text-primary);
        }

        .concept-edge-label {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: var(--accent-light);
        }

        .concept-edge-route {
            font-size: 12px;
        }

        @keyframes mechanismReveal {
            from { opacity: 0; transform: translateY(12px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes mechanismFlow {
            from { transform: scaleX(0); opacity: 0.4; }
            to { transform: scaleX(1); opacity: 1; }
        }

        @keyframes mechanismPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.12); }
        }

        @keyframes misconceptionShift {
            0%, 100% { transform: translateX(0); opacity: 0.75; }
            50% { transform: translateX(4px); opacity: 1; }
        }

        /* ========== Subtitle Panel ========== */
        .subtitle-header {
            padding: 14px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
            background: var(--bg-secondary);
            flex-shrink: 0;
        }

        .subtitle-header h3 { font-size: 14px; font-weight: 600; }
        .subtitle-count { font-size: 12px; color: var(--text-muted); }

        .subtitle-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px 0;
        }

        .subtitle-item {
            padding: 10px 20px;
            display: flex;
            gap: 14px;
            cursor: pointer;
            transition: all 0.15s;
            border-left: 3px solid transparent;
            line-height: 1.6;
        }

        .subtitle-item:hover {
            background: var(--highlight-bg);
        }

        .subtitle-item.active {
            background: var(--highlight-bg);
            border-left-color: var(--accent);
        }

        .sub-time {
            flex-shrink: 0;
            font-size: 13px;
            font-weight: 600;
            color: var(--accent-light);
            font-variant-numeric: tabular-nums;
            min-width: 42px;
        }

        .sub-text {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.6;
        }

        .subtitle-item.active .sub-text { color: var(--text-primary); }

        .subtitle-item mark {
            background: var(--warning);
            color: #000;
            border-radius: 2px;
            padding: 0 2px;
        }

        .subtitle-empty {
            padding: 40px 20px;
            text-align: center;
            color: var(--text-muted);
        }

        /* ========== Modal ========== */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal-overlay.show { display: flex; }

        .modal-content {
            width: 85vw;
            height: 80vh;
            background: var(--bg-secondary);
            border-radius: 16px;
            border: 1px solid var(--border);
            overflow: hidden;
            position: relative;
        }

        .modal-close {
            position: absolute;
            top: 12px;
            right: 16px;
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 28px;
            cursor: pointer;
            z-index: 10;
            transition: color 0.2s;
        }

        .modal-close:hover { color: var(--text-primary); }

        .modal-body {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .modal-body svg {
            max-width: 100%;
            max-height: 100%;
        }

        /* ========== Keyboard Shortcuts ========== */
        .shortcuts-trigger {
            position: fixed;
            bottom: 16px;
            right: 16px;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            font-size: 16px;
            cursor: pointer;
            z-index: 50;
            transition: all 0.2s;
        }

        .shortcuts-trigger:hover { background: var(--bg-card); border-color: var(--accent); }

        .shortcuts-panel {
            display: none;
            position: fixed;
            bottom: 60px;
            right: 16px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 16px;
            z-index: 50;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            min-width: 180px;
        }

        .shortcuts-panel.show { display: block; }

        .shortcuts-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 13px;
            font-weight: 600;
        }

        .shortcuts-header button {
            background: none; border: none; color: var(--text-muted);
            font-size: 18px; cursor: pointer;
        }

        .shortcuts-list div {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 4px 0;
            font-size: 12px;
            color: var(--text-secondary);
        }

        kbd {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 11px;
            font-family: inherit;
            min-width: 24px;
            text-align: center;
        }

        /* ========== Scrollbar ========== */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover { background: var(--border-light); }
'''

    # ================================================================
    # Private: JavaScript
    # ================================================================

    def _generate_javascript(self, transcript_json: str, concept_graph_json: str) -> str:
        return f'''
        // ========== Data ==========
        const transcriptData = {transcript_json};
        const conceptGraphData = {concept_graph_json};

        // ========== DOM Elements ==========
        const video = document.getElementById('mainVideo');
        const overlayContainer = document.getElementById('overlayContainer');
        const subtitleList = document.getElementById('subtitleList');
        const searchInput = document.getElementById('searchInput');
        const galleryGrid = document.getElementById('galleryGrid');
        const galleryEmpty = document.getElementById('galleryEmpty');
        const galleryCount = document.getElementById('galleryCount');
        const mechanismList = document.getElementById('mechanismList');
        const misconceptionList = document.getElementById('misconceptionList');

        // ========== State ==========
        let overlaysEnabled = true;
        let isUserScrollingSubs = false;
        let scrollTimeout = null;

        // ========== Video Time Update ==========
        video.addEventListener('timeupdate', function() {{
            const currentTime = video.currentTime;

            // Update overlay visibility
            if (overlaysEnabled) {{
                document.querySelectorAll('.enhancement-container').forEach(el => {{
                    const start = parseFloat(el.dataset.start);
                    const end = parseFloat(el.dataset.end);
                    if (currentTime >= start && currentTime <= end) {{
                        el.classList.add('active');
                    }} else {{
                        el.classList.remove('active');
                    }}
                }});
            }}

            syncConceptGraph(currentTime);

            // Update subtitle highlighting
            document.querySelectorAll('.subtitle-item').forEach(item => {{
                const start = parseFloat(item.dataset.start);
                const end = parseFloat(item.dataset.end);
                if (currentTime >= start && currentTime < end) {{
                    if (!item.classList.contains('active')) {{
                        item.classList.add('active');
                        if (!isUserScrollingSubs) {{
                            item.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }}
                }} else {{
                    item.classList.remove('active');
                }}
            }});

            // Update timeline progress
            if (video.duration) {{
                const pct = (currentTime / video.duration) * 100;
                document.getElementById('timelineProgress').style.width = pct + '%';
                document.getElementById('videoTimeDisplay').textContent =
                    formatTime(currentTime) + ' / ' + formatTime(video.duration);
            }}
        }});

        // Detect user scrolling in subtitle panel
        subtitleList.addEventListener('scroll', function() {{
            isUserScrollingSubs = true;
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {{ isUserScrollingSubs = false; }}, 3000);
        }});

        // ========== Overlay Container 自适应 ==========
        // 当视频使用 object-fit: contain 时，实际视频区域可能
        // 小于容器（有黑边/letterbox），需要让 overlay 精确覆盖视频区域
        function adjustOverlayToVideo() {{
            const wrapper = video.parentElement;
            if (!wrapper || !video.videoWidth || !video.videoHeight) return;

            const wW = wrapper.clientWidth;
            const wH = wrapper.clientHeight;
            const vRatio = video.videoWidth / video.videoHeight;
            const cRatio = wW / wH;

            let renderW, renderH, offsetX, offsetY;
            if (cRatio > vRatio) {{
                // 容器更宽 → 左右黑边
                renderH = wH;
                renderW = wH * vRatio;
                offsetX = (wW - renderW) / 2;
                offsetY = 0;
            }} else {{
                // 容器更高 → 上下黑边
                renderW = wW;
                renderH = wW / vRatio;
                offsetX = 0;
                offsetY = (wH - renderH) / 2;
            }}

            overlayContainer.style.left = offsetX + 'px';
            overlayContainer.style.top = offsetY + 'px';
            overlayContainer.style.width = renderW + 'px';
            overlayContainer.style.height = renderH + 'px';
        }}

        video.addEventListener('loadedmetadata', adjustOverlayToVideo);
        window.addEventListener('resize', adjustOverlayToVideo);
        // 定期校准（防止首次加载时视频尺寸还未就绪）
        setTimeout(adjustOverlayToVideo, 500);
        setTimeout(adjustOverlayToVideo, 2000);

        // ========== Timeline Markers ==========
        video.addEventListener('loadedmetadata', function() {{
            refreshTimelineMarkers();
        }});

        function refreshTimelineMarkers() {{
            const duration = video.duration;
            if (!duration) return;

            const bar = document.getElementById('timelineBar');
            // Remove old dots
            bar.querySelectorAll('.timeline-dot').forEach(d => d.remove());

            document.querySelectorAll('.enhancement-container').forEach(el => {{
                const start = parseFloat(el.dataset.start);
                const type = el.dataset.type || '';
                const pct = (start / duration) * 100;

                const dot = document.createElement('div');
                let dotClass = 'text-dot';
                if (type.includes('svg')) dotClass = 'svg-dot';
                else if (type.includes('mechanism')) dotClass = 'mechanism-dot';
                else if (type.includes('misconception')) dotClass = 'misconception-dot';
                dot.className = 'timeline-dot ' + dotClass;
                dot.style.left = pct + '%';
                dot.title = formatTime(start);
                dot.onclick = function(e) {{ e.stopPropagation(); jumpTo(start); }};
                bar.appendChild(dot);
            }});

            // Update gallery count
            updateGalleryCount();
        }}

        // Timeline bar click to seek
        document.getElementById('timelineBar').addEventListener('click', function(e) {{
            if (!video.duration) return;
            const rect = this.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            video.currentTime = pct * video.duration;
        }});

        // ========== Jump to time ==========
        function jumpTo(time) {{
            video.currentTime = time;
            video.play().catch(() => {{}});
        }}

        // ========== Toggle Overlays ==========
        function toggleOverlays() {{
            overlaysEnabled = !overlaysEnabled;
            const btn = document.getElementById('toggleOverlays');

            if (!overlaysEnabled) {{
                document.querySelectorAll('.enhancement-container').forEach(el => {{
                    el.classList.remove('active');
                }});
                btn.classList.remove('active');
            }} else {{
                btn.classList.add('active');
            }}
        }}

        // Init toggle button state
        document.getElementById('toggleOverlays').classList.add('active');

        // ========== Search Subtitles ==========
        function searchSubtitles() {{
            const query = searchInput.value.toLowerCase().trim();
            const clearBtn = document.getElementById('clearBtn');

            if (!query) {{
                clearSearch();
                return;
            }}

            clearBtn.style.display = '';
            const items = document.querySelectorAll('.subtitle-item');
            let matchCount = 0;

            items.forEach(item => {{
                const textEl = item.querySelector('.sub-text');
                const originalText = textEl.textContent;

                if (originalText.toLowerCase().includes(query)) {{
                    item.style.display = '';
                    matchCount++;
                    // Highlight matching text
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

        // Enter key triggers search
        searchInput.addEventListener('keydown', function(e) {{
            if (e.key === 'Enter') searchSubtitles();
        }});

        // ========== SVG Preview Modal ==========
        function previewSvg(idx) {{
            const container = document.getElementById('container-' + idx);
            if (!container) return;

            const svgWrapper = container.querySelector('.svg-wrapper');
            if (!svgWrapper) return;

            const modal = document.getElementById('svgModal');
            const modalBody = document.getElementById('svgModalBody');
            modalBody.innerHTML = svgWrapper.innerHTML;
            modal.classList.add('show');
        }}

        function closeSvgModal(event) {{
            if (event && event.target !== event.currentTarget) return;
            document.getElementById('svgModal').classList.remove('show');
        }}

        // ========== Keyboard Shortcuts ==========
        function toggleShortcuts() {{
            document.getElementById('shortcutsPanel').classList.toggle('show');
        }}

        document.addEventListener('keydown', function(e) {{
            // Don't trigger shortcuts when typing in search
            if (e.target.tagName === 'INPUT') return;

            if (e.code === 'Space') {{
                e.preventDefault();
                video.paused ? video.play() : video.pause();
            }} else if (e.code === 'KeyC') {{
                toggleOverlays();
            }} else if (e.code === 'KeyF') {{
                e.preventDefault();
                searchInput.focus();
            }} else if (e.code === 'Escape') {{
                closeSvgModal();
                document.getElementById('shortcutsPanel').classList.remove('show');
            }} else if (e.key === '?') {{
                toggleShortcuts();
            }}
        }});

        // ========== Gallery Management ==========
        function updateGalleryCount() {{
            const items = galleryGrid.querySelectorAll('.gallery-item');
            const count = items.length;
            galleryCount.textContent = count + ' 个增强点';
            galleryEmpty.style.display = count > 0 ? 'none' : '';

            const mechanismItems = mechanismList ? mechanismList.querySelectorAll('.focus-item').length : 0;
            const misconceptionItems = misconceptionList ? misconceptionList.querySelectorAll('.focus-item').length : 0;
            const mechanismCount = document.getElementById('mechanismCount');
            const misconceptionCount = document.getElementById('misconceptionCount');
            const mechanismEmpty = document.getElementById('mechanismEmpty');
            const misconceptionEmpty = document.getElementById('misconceptionEmpty');

            if (mechanismCount) mechanismCount.textContent = mechanismItems + ' 条';
            if (misconceptionCount) misconceptionCount.textContent = misconceptionItems + ' 条';
            if (mechanismEmpty) mechanismEmpty.style.display = mechanismItems > 0 ? 'none' : '';
            if (misconceptionEmpty) misconceptionEmpty.style.display = misconceptionItems > 0 ? 'none' : '';
        }}

        function syncConceptGraph(currentTime) {{
            if (!conceptGraphData || !conceptGraphData.timeline_updates) return;
            let activeIds = [];
            let revealedIds = new Set();
            conceptGraphData.timeline_updates.forEach(update => {{
                if (currentTime >= update.timestamp) {{
                    (update.node_ids || []).forEach(id => revealedIds.add(id));
                    activeIds = update.node_ids || [];
                }}
            }});
            document.querySelectorAll('.concept-node').forEach(node => {{
                node.classList.toggle('revealed', revealedIds.has(node.dataset.nodeId));
                node.classList.toggle('active', activeIds.includes(node.dataset.nodeId));
            }});
            document.querySelectorAll('.concept-edge').forEach(edge => {{
                const source = edge.dataset.source;
                const target = edge.dataset.target;
                const revealed = revealedIds.has(source) && revealedIds.has(target);
                const active = activeIds.includes(source) && activeIds.includes(target);
                edge.classList.toggle('revealed', revealed);
                edge.classList.toggle('active', active);
            }});
        }}

        // ========== Utility ==========
        function formatTime(seconds) {{
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
        }}

        // ========== Init ==========
        updateGalleryCount();
        console.log('Video Enhancement Studio loaded');
        console.log('Transcript entries:', transcriptData.length);
        console.log('Concept graph nodes:', (conceptGraphData.nodes || []).length);
'''


def test_generator():
    """测试生成器"""
    generator = HTMLGenerator()

    test_points = [
        {
            'timestamp': 0.0,
            'duration': 5.0,
            'content_type': 'svg_animation',
            'text': 'Test SVG',
            'layout': {'x': 50, 'y': 50, 'width': 350, 'height': 250, 'position': 'center'},
            'content': {'type': 'svg', 'path': 'assets/svg/test.svg', 'svg_content': '<svg viewBox="0 0 1920 1080"><rect width="1920" height="1080" fill="#1a1a1a"/><circle cx="960" cy="540" r="100" fill="#00f3ff"/></svg>'}
        },
        {
            'timestamp': 6.0,
            'duration': 4.0,
            'content_type': 'text_card',
            'text': 'Test Text',
            'layout': {'x': 500, 'y': 100, 'width': 300, 'height': 200},
            'content': {'type': 'text', 'label': '[ ✨ Insight ]', 'hero_text': 'Test Hero', 'explanation': 'Test explanation content', 'use_glassmorphism': True}
        }
    ]

    html = generator.generate('test.mp4', test_points)

    with open('test_output.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("✓ Test HTML generated: test_output.html")


if __name__ == "__main__":
    test_generator()
