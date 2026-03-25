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
import re
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

            html_content = html_content.replace(
                '<!-- OVERLAY_MARKER -->',
                overlay_html + '\n            <!-- OVERLAY_MARKER -->'
            )
            html_content = html_content.replace(
                '<!-- GALLERY_MARKER -->',
                gallery_html + '\n                <!-- GALLERY_MARKER -->'
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
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
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
                            <stop stop-color="#2f5f98"/>
                            <stop offset="1" stop-color="#3f7fb8"/>
                        </linearGradient>
                    </defs>
                </svg>
                <span class="logo-text">Video Enhancement Studio</span>
            </div>
        </div>
        <div class="header-right">
            <button id="toggleOverlays" class="header-tool-btn active" onclick="toggleOverlays()" title="切换浮层显示">
                <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor">
                    <rect x="1" y="3" width="14" height="10" rx="1" stroke="currentColor" stroke-width="1.2" fill="none"/>
                    <rect x="3" y="5" width="5" height="4" rx="0.5" fill="currentColor" opacity="0.4"/>
                </svg>
                浮层
            </button>
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
    <div class="main-content" id="mainContent">
        <div class="left-panel">
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

            </div>
            <div class="subtitle-section">
                <div class="subtitle-header">
                    <h3>字幕</h3>
                    <span class="subtitle-count">{len(transcript_data)} 条字幕</span>
                </div>
                <div class="subtitle-list" id="subtitleList">
{subtitle_entries_html}
                </div>
            </div>
        </div>

        <div class="middle-panel">
            <div class="gallery-section">
                <div class="gallery-header">
                    <h3>增强内容画廊</h3>
                    <div class="gallery-toolbar">
                        <div class="gallery-view-chip" id="galleryViewChip">分类排序</div>
                        <div class="gallery-filter-wrap">
                            <button class="gallery-filter-btn" id="galleryFilterBtn" onclick="toggleGalleryMenu(event)" title="切换画廊视图">
                                <span>筛选</span>
                                <span>⌄</span>
                            </button>
                            <div class="gallery-filter-menu" id="galleryFilterMenu">
                                <button onclick="setTimelineSort('time')">按时间排序</button>
                                <button onclick="setGalleryMode('category')">按分类排序</button>
                            </div>
                        </div>
                    </div>
                </div>
                    <div class="gallery-viewport" id="galleryViewport">
                        <div class="gallery-home">
                            <div class="gallery-category-card text-card">
                                <div class="gallery-category-icon">文</div>
                                <div class="gallery-category-copy">
                                    <div class="gallery-category-title">文字</div>
                                    <div class="gallery-category-desc">用于浏览文字说明与文本增强</div>
                                </div>
                                <button class="gallery-enter-btn" onclick="openGalleryDetail('text')">→</button>
                            </div>
                            <div class="gallery-category-card image-card">
                                <div class="gallery-category-icon">图</div>
                                <div class="gallery-category-copy">
                                    <div class="gallery-category-title">图片</div>
                                    <div class="gallery-category-desc">用于浏览 SVG / 图像增强内容</div>
                                </div>
                                <button class="gallery-enter-btn" onclick="openGalleryDetail('image')">→</button>
                            </div>
                        </div>
                    </div>
                <div class="gallery-source" id="gallerySource">
                <!-- GALLERY_MARKER -->
                </div>
                <div class="gallery-empty" id="galleryEmpty">
                    <p>等待内容生成中...</p>
                    <p class="hint">生成的 SVG 与文字内容会显示在这里</p>
                </div>
            </div>
        </div>

        <div class="right-panel" id="rightPanel">
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
            style = self._get_svg_container_style(layout, content)
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
            available_bottom_pct = max(10.0, 92.0 - top_pct)
            h_pct_max = min(max(height / self.LAYOUT_CANVAS_H * 100 * 1.55, 22.0), available_bottom_pct)
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
        """生成单个画廊源数据HTML，由前端JS统一渲染多种视图"""
        content = point.get('content', {})
        content_type = content.get('type', 'text')
        point_content_type = point.get('content_type', '')
        timestamp = point.get('timestamp', 0)
        topic = (point.get('text', '') or '')[:120]
        svg_path = content.get('path', '')
        svg_mode_hint = point.get('svg_mode_hint', point.get('metadata', {}).get('svg_mode_hint', 'static_svg'))

        if point_content_type == 'text_card':
            category = 'text'
            display_type = '文字'
            title = content.get('title', topic)[:60] or topic[:60]
            summary = content.get('subtitle', point.get('text', ''))[:160]
            icon = '文'
        elif content_type == 'svg':
            category = 'image'
            display_type = '图片'
            title = content.get('title', topic)[:60] or topic[:60]
            summary = content.get('subtitle', point.get('text', ''))[:160]
            icon = '🖼'
        else:
            category = 'text'
            display_type = '文字'
            title = content.get('title', topic)[:60] or topic[:60]
            summary = content.get('explanation', point.get('text', ''))[:160]
            icon = '文'

        attrs = {
            'data-idx': str(idx),
            'data-start': str(timestamp),
            'data-category': category,
            'data-display-type': display_type,
            'data-title': title,
            'data-summary': summary,
            'data-icon': icon,
            'data-svg-path': svg_path,
            'data-svg-mode': svg_mode_hint,
            'data-topic': point.get('text', '')[:200],
        }
        attr_html = " ".join(
            f'{key}="{html_module.escape(value, quote=True)}"' for key, value in attrs.items()
        )
        return f'                <div class="gallery-source-item" {attr_html}></div>'

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
            svg_intent = content.get('svg_intent', '')
            shell_class = 'svg-shell image-svg-shell'
            if 'assets/t2svg/' in svg_path or svg_intent in ('knowledge_note', 'mechanism_process'):
                shell_class = 'svg-shell text-svg-shell'
            shell_style = self._build_overlay_shell_style(content)

            if svg_path:
                return (
                    f'<div class="{shell_class}" style="{shell_style}">'
                    f'<img src="{svg_path}" class="svg-content svg-content-image" alt="SVG enhancement" draggable="false">'
                    f'</div>'
                )
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
            layout_width = point.get('layout', {}).get('width', 0)
            if layout_width and (layout_width < 620 or any(len(str(stage)) > 22 for stage in stages)):
                variant = 'stacked'
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

    def _build_overlay_shell_style(self, content: Dict) -> str:
        style = content.get('overlay_style') or {}
        bg = html_module.escape(style.get('background', '#122238'))
        border = html_module.escape(style.get('border', '#6d98d1'))
        opacity = style.get('bg_opacity', 1.0)
        svg_intent = content.get('svg_intent', '')
        try:
            opacity = max(0.88, min(1.0, float(opacity)))
        except Exception:
            opacity = 1.0
        if svg_intent in ('knowledge_note', 'mechanism_process'):
            opacity = 1.0
        shell_bg = self._hex_to_rgba(bg, opacity)
        return (
            f'background: {shell_bg}; '
            f'border: 4px solid {border}; '
            f'border-radius: 18px; '
            f'overflow: hidden; '
            f'box-shadow: 0 16px 30px rgba(8, 15, 25, 0.22);'
        )

    def _hex_to_rgba(self, color: str, alpha: float) -> str:
        raw = str(color or '').strip().lstrip('#')
        if len(raw) != 6:
            return f'rgba(18, 34, 56, {alpha})'
        try:
            r = int(raw[0:2], 16)
            g = int(raw[2:4], 16)
            b = int(raw[4:6], 16)
            return f'rgba({r}, {g}, {b}, {alpha})'
        except Exception:
            return f'rgba(18, 34, 56, {alpha})'

    def _generate_concept_graph_html(self, concept_graph: Dict) -> str:
        def _clean_md(text: str, fallback: str) -> str:
            raw = str(text or fallback).strip()
            raw = re.sub(r'^\s*#+\s*', '', raw)
            raw = raw.replace('**', '')
            return html_module.escape(raw.strip() or fallback)

        title = _clean_md(concept_graph.get('graph_title', 'Main Topic'), 'Main Topic')
        summary = _clean_md(concept_graph.get('summary', '暂无概念图摘要'), '暂无概念图摘要')
        nodes_html = []
        for node in concept_graph.get('nodes', []):
            label = _clean_md(node.get('label', 'Node'), 'Node')
            node_id = html_module.escape(node.get('id', ''))
            nodes_html.append(
                f'<div class="concept-node" data-node-id="{node_id}">'
                f'<span class="concept-node-label">{label}</span>'
                f'<span class="concept-node-weight">{node.get("weight", 1)}</span>'
                f'</div>'
            )

        if not nodes_html:
            nodes_html.append('<div class="concept-empty">暂无概念节点</div>')

        return f'''
            <div class="concept-graph-section" id="conceptGraphSection">
                <div class="concept-graph-header">
                    <h3>全局概念图</h3>
                    <span class="concept-graph-count">{len(concept_graph.get('nodes', []))} 个节点</span>
                </div>
                <div class="concept-main-topic">
                    <div class="concept-main-label">Main Topic</div>
                    <div class="concept-graph-title">{title}</div>
                    <div class="concept-graph-summary">{summary}</div>
                </div>
                <div class="concept-node-list" id="conceptGraphNodes">
                    {"".join(nodes_html)}
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

    def _get_svg_container_style(self, layout: Dict, content: Dict | None = None) -> str:
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
            svg_path = (content or {}).get('path', '')
            svg_intent = (content or {}).get('svg_intent', '')
            is_t2svg = 'assets/t2svg/' in svg_path or svg_intent in ('knowledge_note', 'mechanism_process')
            if is_t2svg:
                original_w_pct = w_pct
                original_h_pct = h_pct
                w_pct *= 1.30
                h_pct *= 1.30
                left_pct -= (w_pct - original_w_pct) / 2
                top_pct -= (h_pct - original_h_pct) / 2
            min_w_pct = 18.0 if is_t2svg else 14.0
            min_h_pct = 15.0 if is_t2svg else 10.5
            w_pct = max(w_pct, min_w_pct)
            h_pct = max(h_pct, min_h_pct)
            margin_x = 4.8
            margin_y = 5.2
            left_pct = max(margin_x, left_pct)
            top_pct = max(margin_y, top_pct)
            if left_pct + w_pct > 100 - margin_x:
                left_pct = max(margin_x, 100 - margin_x - w_pct)
            if top_pct + h_pct > 100 - margin_y:
                top_pct = max(margin_y, 100 - margin_y - h_pct)
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
        elif position == 'middle-left':
            return 'left: 4.5%; top: 18%; width: 46%; height: 54%;'
        elif position == 'middle-right':
            return 'right: 4.5%; top: 18%; width: 46%; height: 54%;'
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
            --bg-primary: #ffffff;
            --bg-secondary: #f3f8fe;
            --bg-tertiary: #e8f1fb;
            --bg-card: #ffffff;
            --border: #d7e6f5;
            --border-light: #aac6e4;
            --accent: #4a79ba;
            --accent-light: #6d98d1;
            --accent-glow: rgba(74, 121, 186, 0.18);
            --success: #5d91cb;
            --warning: #7ea8da;
            --text-primary: #173756;
            --text-secondary: #4e6884;
            --text-muted: #8aa4be;
            --highlight-bg: rgba(74, 121, 186, 0.10);
            --header-height: 56px;
        }

        body {
            font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background:
                radial-gradient(circle at top left, rgba(90,146,205,0.12), transparent 26%),
                linear-gradient(180deg, #fbfdff 0%, #f5f9fd 100%);
            color: var(--text-primary);
            overflow: hidden;
            height: 100vh;
        }

        /* ========== Header ========== */
        .app-header {
            height: var(--header-height);
            background: rgba(255,255,255,0.92);
            backdrop-filter: blur(10px);
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
            color: #1b3b5d;
            letter-spacing: -0.2px;
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .header-tool-btn {
            height: 34px;
            padding: 0 12px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: #ffffff;
            color: var(--accent);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            box-shadow: 0 6px 18px rgba(74,121,186,0.08);
        }

        .header-tool-btn.active {
            background: #f4f9fe;
        }

        .search-box {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .search-box input {
            width: 280px;
            height: 34px;
            background: rgba(255,255,255,0.92);
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
            background: #ffffff;
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }

        #clearBtn:hover { background: var(--bg-card); }

        /* ========== Main Layout ========== */
        .main-content {
            display: grid;
            grid-template-columns: minmax(0, 9fr) minmax(340px, 4fr) minmax(220px, 2fr);
            height: calc(100vh - var(--header-height));
            position: relative;
            gap: 12px;
            padding: 12px;
            background: var(--bg-secondary);
        }

        .left-panel {
            display: grid;
            grid-template-rows: minmax(0, 2.2fr) minmax(0, 1fr);
            min-width: 0;
            min-height: 0;
            background: var(--bg-primary);
            overflow: hidden;
            gap: 12px;
        }

        .middle-panel,
        .right-panel {
            min-width: 0;
            min-height: 0;
        }

        .middle-panel {
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .right-panel {
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: transparent;
        }

        .subtitle-section {
            display: flex;
            flex-direction: column;
            min-height: 0;
            height: 100%;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 10px 28px rgba(74,121,186,0.08);
        }

        /* ========== Video Section ========== */
        .video-section {
            display: flex;
            flex-direction: column;
            background: #000;
            min-height: 0;
            height: 100%;
            overflow: hidden;
            border-radius: 20px;
            border: 1px solid var(--border);
            box-shadow: 0 10px 28px rgba(74,121,186,0.08);
        }

        .bottom-row {
            display: flex;
            flex-direction: column;
            padding: 12px;
            background: var(--bg-secondary);
            min-height: 0;
            height: 100%;
            overflow: hidden;
        }

        .video-wrapper {
            flex: 1;
            position: relative;
            overflow: hidden;
            min-height: 0;
        }

        #mainVideo {
            width: 100%;
            height: 100%;
            object-fit: cover;
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
            mix-blend-mode: normal;
            filter: drop-shadow(0 14px 28px rgba(15, 23, 42, 0.28));
            isolation: isolate;
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
            display: block;
            background: inherit;
            border: none;
            outline: none;
        }

        .svg-content-image {
            filter: drop-shadow(0 10px 22px rgba(15, 23, 42, 0.18));
            transform: translateZ(0);
            backface-visibility: hidden;
        }

        .svg-shell {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 18px;
            overflow: hidden;
        }

        .text-svg-shell {
            width: 100%;
            height: 100%;
            padding: 0;
            backdrop-filter: none;
            -webkit-backdrop-filter: none;
            box-shadow: 0 18px 32px rgba(8, 15, 25, 0.24);
        }

        .text-svg-shell .svg-content {
            object-fit: fill;
            background: inherit;
        }

        .text-svg-shell .svg-content-image {
            filter: none;
        }

        .image-svg-shell {
            padding: 0;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }

        /* Scholarly Overlay Theme */
        .premium-glassmorphism {
            background: rgba(255, 255, 255, 0.88);
            backdrop-filter: blur(14px) saturate(120%);
            -webkit-backdrop-filter: blur(14px) saturate(120%);
            border: 1px solid rgba(151, 184, 219, 0.36);
            border-left: 4px solid var(--card-accent, #4f7cac);
            box-shadow: 0 16px 38px rgba(47, 111, 178, 0.12), inset 0 1px 0 rgba(255,255,255,0.72);
            border-radius: 14px;
            padding: 24px 32px;
            color: var(--text-primary);
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
            color: var(--card-accent, #7fa9d6);
            text-transform: uppercase;
            background: rgba(255, 255, 255, 0.08);
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
            color: var(--text-primary);
            overflow-wrap: anywhere;
        }
        
        .card-explanation { 
            font-size: calc(15px * var(--overlay-scale, 1)); 
            line-height: 1.6; 
            color: #45617f;
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
            font-size: calc(18px * var(--overlay-scale, 1));
            font-weight: 600;
            line-height: 1.35;
        }

        .mechanism-path-track {
            display: grid;
            grid-auto-flow: column;
            grid-auto-columns: minmax(0, 1fr);
            align-items: stretch;
            gap: 10px;
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
            display: grid;
            grid-template-columns: minmax(0, 1fr) 28px;
            align-items: center;
            min-width: 0;
        }

        .mechanism-stage {
            display: flex;
            gap: 10px;
            color: var(--text-primary);
            min-width: 0;
            animation: mechanismReveal 0.7s ease forwards;
        }

        .node-stage {
            align-items: flex-start;
            background: #edf4fb;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 12px;
            min-height: 150px;
        }

        .mechanism-node-core {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: rgba(47,111,178,0.12);
            border: 2px solid rgba(47,111,178,0.45);
            box-shadow: 0 0 0 6px rgba(47,111,178,0.08);
            flex-shrink: 0;
            position: relative;
            margin-top: 2px;
        }

        .mechanism-node-copy {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-left: 0;
            min-width: 0;
            padding: 0;
        }

        .mechanism-stage.active {
            color: var(--text-primary);
        }

        .mechanism-stage.active .mechanism-node-core {
            background: #6da8e6;
            border-color: #2f6fb2;
            box-shadow: 0 0 0 8px rgba(47,111,178,0.10), 0 0 22px rgba(47,111,178,0.22);
            animation: mechanismPulse 1.5s ease-in-out infinite;
        }

        .mechanism-stage.completed {
            color: var(--text-primary);
        }

        .mechanism-stage.completed .mechanism-node-core {
            background: rgba(47,111,178,0.72);
            border-color: rgba(47,111,178,0.92);
            box-shadow: 0 0 0 7px rgba(47,111,178,0.08), 0 0 16px rgba(47,111,178,0.22);
        }

        .mechanism-stage-text {
            overflow-wrap: break-word;
            word-break: break-word;
            line-height: 1.45;
            font-size: calc(14px * var(--overlay-scale, 1));
            color: var(--text-primary);
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
            background: linear-gradient(90deg, rgba(47,111,178,0.10), rgba(47,111,178,0.28));
            transform-origin: left center;
            animation: mechanismFlow 1.1s ease forwards;
        }

        .mechanism-connector-dot {
            position: absolute;
            right: -1px;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: rgba(47,111,178,0.35);
            box-shadow: 0 0 10px rgba(47,111,178,0.18);
        }

        .mechanism-connector.active .mechanism-connector-line {
            background: linear-gradient(90deg, rgba(47,111,178,0.65), rgba(47,111,178,1));
            box-shadow: 0 0 14px rgba(47,111,178,0.20);
        }

        .mechanism-connector.active .mechanism-connector-dot {
            background: #6da8e6;
            box-shadow: 0 0 24px rgba(47,111,178,0.36);
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
            height: 28px;
            background: var(--bg-secondary);
            display: flex;
            align-items: center;
            justify-content: flex-end;
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
            background: var(--bg-card);
            overflow: visible;
            border: 1px solid var(--border);
            border-radius: 18px;
            min-height: 0;
            height: 100%;
            box-shadow: 0 10px 28px rgba(47,111,178,0.08);
        }

        .gallery-header {
            padding: 12px 14px;
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

        .gallery-toolbar {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 10px;
            flex-shrink: 0;
        }

        .gallery-view-chip {
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 999px;
            background: #edf4fb;
            border: 1px solid var(--border);
            color: var(--accent);
            font-size: 12px;
            font-weight: 600;
        }

        .gallery-filter-wrap {
            position: relative;
        }

        .gallery-filter-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: #ffffff;
            color: var(--text-primary);
            cursor: pointer;
            font-size: 12px;
            font-family: inherit;
            box-shadow: 0 6px 18px rgba(47,111,178,0.08);
        }

        .gallery-filter-menu {
            position: fixed;
            min-width: 150px;
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 14px;
            box-shadow: 0 16px 28px rgba(47,111,178,0.14);
            padding: 8px;
            display: none;
            z-index: 60;
        }

        .gallery-filter-menu.show {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .gallery-filter-menu button {
            width: 100%;
            text-align: left;
            border: none;
            background: transparent;
            border-radius: 10px;
            padding: 9px 10px;
            color: var(--text-primary);
            font-size: 12px;
            cursor: pointer;
            font-family: inherit;
        }

        .gallery-filter-menu button:hover {
            background: #edf4fb;
            color: var(--accent);
        }

        .gallery-viewport {
            flex: 1;
            height: 100%;
            overflow-y: auto;
            padding: 10px;
            min-height: 0;
            position: relative;
        }

        .gallery-viewport.detail-view {
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding-top: 4px;
        }

        .gallery-viewport.detail-view > * {
            width: 100%;
            height: 100%;
            min-height: 0;
            flex: 1 1 auto;
        }

        .gallery-source {
            display: none;
        }

        .gallery-home {
            display: flex;
            flex-direction: column;
            gap: 14px;
            align-items: stretch;
            height: 100%;
        }

        .gallery-category-card {
            border-radius: 24px;
            border: 1px solid var(--border);
            background: linear-gradient(180deg, #4a79ba 0%, #5d91cb 100%);
            color: #ffffff;
            min-height: 0;
            flex: 1 1 0;
            display: grid;
            grid-template-columns: 52px minmax(0, 1fr) 44px;
            align-items: center;
            gap: 14px;
            padding: 18px 20px;
            box-shadow: 0 16px 36px rgba(47,111,178,0.16);
        }

        .gallery-category-card.text-card {
            background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
            color: var(--accent);
        }

        .gallery-category-card.image-card {
            background: linear-gradient(180deg, #ffffff 0%, #eef5fd 100%);
            color: var(--accent);
        }

        .gallery-category-icon {
            width: 52px;
            height: 52px;
            border-radius: 50%;
            background: rgba(255,255,255,0.92);
            color: var(--accent);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 700;
            box-shadow: inset 0 0 0 1px rgba(47,111,178,0.08);
        }

        .gallery-category-card.text-card .gallery-category-icon,
        .gallery-category-card.image-card .gallery-category-icon {
            background: linear-gradient(180deg, #88a8df 0%, #6d98d1 100%);
            color: #ffffff;
        }

        .gallery-category-copy {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: center;
            gap: 6px;
            text-align: left;
        }

        .gallery-category-title {
            font-size: 20px;
            font-weight: 700;
        }

        .gallery-category-desc {
            font-size: 13px;
            line-height: 1.5;
            color: rgba(255,255,255,0.80);
        }

        .gallery-category-card.text-card .gallery-category-desc,
        .gallery-category-card.image-card .gallery-category-desc {
            color: var(--text-muted);
        }

        .gallery-enter-btn,
        .gallery-back-btn,
        .gallery-nav-btn {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            border: none;
            background: rgba(255,255,255,0.94);
            color: var(--accent);
            font-size: 22px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 10px 24px rgba(47,111,178,0.14);
        }

        .gallery-detail-layout {
            min-height: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            gap: 10px;
            overflow: hidden;
        }

        .gallery-detail-layout > * {
            min-height: 0;
        }

        .gallery-side {
            display: flex;
            flex-direction: row;
            gap: 8px;
            position: sticky;
            top: 0;
            z-index: 4;
            height: max-content;
            min-height: 0;
            align-items: center;
        }

        .gallery-action-stack {
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 5;
        }

        .gallery-mini-chip {
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 999px;
            background: #edf4fb;
            border: 1px solid var(--border);
            color: var(--accent);
            font-size: 12px;
            font-weight: 600;
        }

        .gallery-mini-filter {
            min-width: 74px;
            justify-content: center;
        }

        .gallery-side-card {
            border-radius: 18px;
            background: linear-gradient(180deg, #eaf3fd 0%, #d9e9fb 100%);
            padding: 10px 12px;
            display: flex;
            flex-direction: row;
            align-items: center;
            justify-content: flex-start;
            gap: 10px;
            min-height: 64px;
            box-shadow: 0 12px 28px rgba(31, 64, 114, 0.10);
        }

        .gallery-side-card.text-side {
            background: linear-gradient(180deg, #edf5fd 0%, #dceafb 100%);
        }

        .gallery-side-card .gallery-category-icon {
            width: 36px;
            height: 36px;
            flex: 0 0 auto;
        }

        .gallery-side-card .gallery-category-copy {
            flex: 1 1 auto;
            justify-content: flex-start;
            gap: 2px;
            min-width: 0;
        }

        .gallery-side-card .gallery-category-title {
            color: var(--text-primary);
            font-size: 13px;
        }

        .gallery-side-card .gallery-category-desc {
            color: var(--text-primary);
            opacity: 0.72;
            font-size: 10px;
            line-height: 1.4;
        }

        .gallery-detail-list {
            display: block;
            overflow-y: auto;
            min-height: 0;
            height: 100%;
            max-height: 100%;
            padding-top: 0;
            padding-right: 6px;
            overscroll-behavior: contain;
        }

        .gallery-detail-item {
            border-radius: 16px;
            background: linear-gradient(180deg, #f8fbff 0%, #edf5fd 100%);
            border: 1px solid #cfe1f4;
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            align-items: stretch;
            gap: 7px;
            cursor: pointer;
            transition: transform 0.18s ease, box-shadow 0.18s ease;
            margin-bottom: 10px;
        }

        .gallery-detail-item.text-item {
            background: #edf5fd;
            border-color: #d7e6f5;
        }

        .gallery-detail-item:hover {
            transform: translateX(4px);
            box-shadow: 0 10px 24px rgba(47,111,178,0.10);
        }

        .gallery-detail-item.active {
            border-color: var(--accent);
            background: #dceafb;
            box-shadow: 0 0 0 1px rgba(47,111,178,0.12) inset;
        }

        .gallery-detail-time {
            font-size: 12px;
            font-weight: 700;
            color: var(--accent);
        }

        .gallery-detail-title {
            font-size: 14px;
            line-height: 1.45;
            font-weight: 700;
            color: var(--text-primary);
        }

        .gallery-detail-subtext {
            font-size: 12px;
            line-height: 1.5;
            color: var(--text-muted);
        }

        .gallery-image-detail {
            min-height: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            gap: 10px;
            align-items: stretch;
        }

        .gallery-image-main {
            min-height: 0;
            height: 100%;
            display: flex;
            flex-direction: column;
            gap: 12px;
            overflow-y: auto;
            padding-right: 4px;
        }

        .gallery-image-card {
            background: linear-gradient(180deg, rgba(233, 243, 252, 0.72) 0%, rgba(241, 248, 254, 0.42) 100%);
            border: 1px solid rgba(182, 208, 233, 0.56);
            border-radius: 22px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            gap: 0;
            cursor: pointer;
            min-height: 280px;
            box-shadow: 0 8px 20px rgba(47,111,178,0.06);
            backdrop-filter: blur(6px);
        }

        .gallery-image-stage {
            position: relative;
            background: transparent;
            border-bottom: none;
            min-height: 220px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            padding: 12px 12px 0;
        }

        .gallery-back-btn {
            position: sticky;
            top: 0;
            z-index: 5;
        }

        .gallery-image-stage img {
            width: 100%;
            height: 100%;
            max-width: none;
            max-height: none;
            object-fit: contain;
            border-radius: 0;
            box-shadow: none;
            background: transparent;
        }

        .gallery-image-caption {
            background: transparent;
            padding: 10px 14px 14px;
            color: var(--text-primary);
            font-size: 13px;
            line-height: 1.6;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }

        .gallery-nav-btn {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
        }

        .gallery-nav-btn.prev-btn { left: 16px; }
        .gallery-nav-btn.next-btn { right: 16px; }

        .gallery-mode-timeline {
            display: flex;
            flex-direction: column;
            gap: 12px;
            min-height: 0;
        }

        .timeline-card {
            background: linear-gradient(180deg, #ffffff 0%, #f4f9fe 100%);
            border: 1px solid var(--border);
            border-radius: 22px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            cursor: pointer;
            transition: all 0.2s;
            min-height: 124px;
            padding: 12px;
            gap: 10px;
        }

        .timeline-card.image-card {
            background: linear-gradient(180deg, rgba(233, 243, 252, 0.72) 0%, rgba(241, 248, 254, 0.42) 100%);
            border-color: rgba(182, 208, 233, 0.56);
            box-shadow: 0 8px 20px rgba(47,111,178,0.05);
        }

        .timeline-card:hover {
            border-color: var(--border-light);
            box-shadow: 0 10px 24px rgba(47, 111, 178, 0.16);
            transform: translateY(-3px);
        }

        .timeline-top {
            position: relative;
            min-height: 0;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: flex-start;
            gap: 6px;
            padding: 0;
        }

        .timeline-time {
            position: absolute;
            top: 0;
            right: 0;
            padding: 5px 10px;
            border-radius: 999px;
            background: rgba(255,255,255,0.94);
            color: var(--text-primary);
            font-size: 12px;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(47,111,178,0.10);
        }

        .timeline-icon {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: #ffffff;
            color: var(--accent);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            font-weight: 700;
            border: 1px solid var(--border);
        }

        .timeline-media {
            width: 100%;
            min-height: 92px;
            max-height: 120px;
            border-radius: 14px;
            overflow: hidden;
            background: transparent;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: none;
        }

        .timeline-media img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }

        .timeline-title {
            font-size: 15px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .timeline-production {
            display: block;
            font-size: 14px;
            font-weight: 700;
            color: #2c62a7;
            margin-top: 2px;
        }

        .timeline-summary-pill {
            display: inline-flex;
            align-items: center;
            min-height: 30px;
            padding: 6px 10px;
            border-radius: 12px;
            background: #ffffff;
            border: 1px solid #d9e7f4;
            color: var(--text-primary);
            font-size: 12px;
            box-shadow: inset 0 0 0 1px rgba(108, 152, 209, 0.05);
        }

        .timeline-bottom {
            display: flex;
            align-items: flex-start;
            justify-content: flex-start;
            padding: 0;
            font-size: 11px;
            color: var(--text-primary);
            line-height: 1.45;
            text-align: left;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
        }

        .gallery-empty {
            display: none;
            padding: 40px 20px;
            text-align: center;
            color: var(--text-muted);
        }

        .gallery-empty .hint {
            font-size: 12px;
            margin-top: 8px;
            opacity: 0.6;
        }

        .concept-graph-section {
            background: linear-gradient(180deg, #ffffff 0%, #f4f9fe 100%);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 14px 14px 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            overflow: hidden;
            min-height: 0;
            height: 100%;
            box-shadow: 0 10px 28px rgba(74,121,186,0.08);
        }

        .concept-graph-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .concept-graph-header h3 {
            font-size: 14px;
            font-weight: 600;
        }

        .concept-graph-count {
            font-size: 12px;
            color: var(--text-muted);
        }

        .concept-main-topic {
            background: linear-gradient(180deg, #eef5fd 0%, #dfeefe 100%);
            border: 1px solid rgba(151, 184, 219, 0.4);
            border-radius: 14px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .concept-main-label {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            color: var(--accent);
        }

        .concept-graph-title {
            font-size: 15px;
            font-weight: 700;
            line-height: 1.35;
            color: var(--text-primary);
        }

        .concept-graph-summary {
            font-size: 12px;
            line-height: 1.55;
            color: var(--text-secondary);
        }

        .concept-node-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            overflow-y: auto;
            min-height: 0;
        }

        .concept-node {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 12px;
            background: #f6fbff;
            border: 1px solid #d6e4f2;
            color: var(--text-secondary);
            transition: all 0.2s ease;
            opacity: 0.46;
            transform: translateX(0);
        }

        .concept-node.revealed {
            opacity: 0.82;
        }

        .concept-node.active {
            color: var(--accent);
            border-color: var(--accent);
            background: rgba(47,111,178,0.12);
            box-shadow: 0 0 0 1px rgba(47,111,178,0.10) inset, 0 8px 22px rgba(47,111,178,0.14);
        }

        .concept-node-label {
            font-size: 12px;
            font-weight: 600;
            line-height: 1.4;
        }
        .concept-node-weight {
            font-size: 10px;
            color: var(--accent);
            font-weight: 700;
        }

        .concept-empty {
            padding: 16px 12px;
            border-radius: 12px;
            background: #f6fbff;
            border: 1px dashed var(--border-light);
            color: var(--text-muted);
            font-size: 12px;
            text-align: center;
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
            background: var(--bg-card);
            flex-shrink: 0;
        }

        .subtitle-header h3 { font-size: 14px; font-weight: 600; }
        .subtitle-count { font-size: 12px; color: var(--text-muted); }

        .subtitle-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px 0;
            background: var(--bg-card);
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
        const galleryViewport = document.getElementById('galleryViewport');
        const gallerySource = document.getElementById('gallerySource');
        const galleryEmpty = document.getElementById('galleryEmpty');
        const galleryCount = document.getElementById('galleryCount');
        const galleryViewChip = document.getElementById('galleryViewChip');
        const galleryFilterMenu = document.getElementById('galleryFilterMenu');
        const galleryToolbar = document.querySelector('.gallery-toolbar');

        // ========== State ==========
        let overlaysEnabled = true;
        let isUserScrollingSubs = false;
        let scrollTimeout = null;
        let galleryMode = 'category';
        let galleryDetailType = null;
        let timelineSort = 'time';
        let imageCarouselIndex = 0;
        let galleryEntries = [];
        let galleryReturnState = null;
        let selectedDetailIdx = null;

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

            // Update time display if present
            if (video.duration) {{
                const timeDisplay = document.getElementById('videoTimeDisplay');
                if (timeDisplay) {{
                    timeDisplay.textContent = formatTime(currentTime) + ' / ' + formatTime(video.duration);
                }}
            }}
        }});

        // Detect user scrolling in subtitle panel
        if (subtitleList) {{
            subtitleList.addEventListener('scroll', function() {{
                isUserScrollingSubs = true;
                clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {{ isUserScrollingSubs = false; }}, 3000);
            }});
        }}

        // ========== Overlay Container 自适应 ==========
        // 当视频使用 object-fit: cover 时，让 overlay 覆盖整个视频框
        // 这样视频和浮层都会占满容器，避免左右留白
        function adjustOverlayToVideo() {{
            const wrapper = video.parentElement;
            if (!wrapper) return;

            const wW = wrapper.clientWidth;
            const wH = wrapper.clientHeight;

            overlayContainer.style.left = '0px';
            overlayContainer.style.top = '0px';
            overlayContainer.style.width = wW + 'px';
            overlayContainer.style.height = wH + 'px';
        }}

        video.addEventListener('loadedmetadata', adjustOverlayToVideo);
        window.addEventListener('resize', adjustOverlayToVideo);
        // 定期校准（防止首次加载时视频尺寸还未就绪）
        setTimeout(adjustOverlayToVideo, 500);
        setTimeout(adjustOverlayToVideo, 2000);

        // ========== Gallery Init ==========
        video.addEventListener('loadedmetadata', function() {{
            updateGalleryCount();
        }});

        function ensureGalleryReady() {{
            updateGalleryCount();
        }}

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

        function toggleGalleryMenu(event) {{
            if (event) {{
                const rect = event.currentTarget.getBoundingClientRect();
                galleryFilterMenu.style.top = (rect.bottom + 8) + 'px';
                galleryFilterMenu.style.left = Math.max(12, rect.left) + 'px';
            }}
            galleryFilterMenu.classList.toggle('show');
        }}

        function closeGalleryMenu() {{
            galleryFilterMenu.classList.remove('show');
        }}

        function collectGalleryEntries() {{
            galleryEntries = Array.from(gallerySource.querySelectorAll('.gallery-source-item')).map(node => ({{
                idx: Number(node.dataset.idx || 0),
                start: Number(node.dataset.start || 0),
                category: node.dataset.category || 'text',
                displayType: node.dataset.displayType || '文字',
                title: node.dataset.title || '',
                summary: node.dataset.summary || '',
                icon: node.dataset.icon || '文',
                svgPath: node.dataset.svgPath || '',
                svgMode: node.dataset.svgMode || 'static_svg',
                topic: node.dataset.topic || ''
            }}));
        }}

        function getCategoryMeta(type) {{
            if (type === 'mechanism') {{
                return {{ title: '机制链', desc: '用于展示过程、链路与机制关系', icon: '⚙', cardClass: 'mechanism-card', sideClass: 'mechanism-side' }};
            }}
            if (type === 'image') {{
                return {{ title: '图片', desc: '用于浏览 SVG / 图像增强内容', icon: '图', cardClass: 'image-card', sideClass: 'image-side' }};
            }}
            return {{ title: '文字', desc: '用于浏览文字说明与文本增强', icon: '文', cardClass: 'text-card', sideClass: 'text-side' }};
        }}

        function getEntriesByType(type) {{
            return galleryEntries
                .filter(item => item.category === type)
                .sort((a, b) => a.start - b.start);
        }}

        function renderGallery() {{
            if (!galleryEntries.length) {{
                galleryViewport.innerHTML = '';
                galleryEmpty.style.display = '';
                galleryViewport.classList.remove('detail-view');
                return;
            }}
            galleryEmpty.style.display = 'none';
            galleryToolbar.style.display = galleryDetailType ? 'none' : 'flex';
            galleryViewport.classList.toggle('detail-view', !!galleryDetailType);
            if (galleryMode === 'timeline') {{
                galleryViewChip.textContent = '按时间排序';
                renderTimelineGallery();
                return;
            }}
            galleryViewChip.textContent = '按分类排序';
            if (!galleryDetailType) {{
                renderCategoryHome();
                return;
            }}
            if (galleryDetailType === 'image') {{
                renderImageDetail();
                return;
            }}
            renderTextualDetail(galleryDetailType);
        }}

        function renderCategoryHome() {{
            const types = ['mechanism', 'text', 'image'];
            let cards = '';
            types.forEach(type => {{
                const meta = getCategoryMeta(type);
                cards += '<div class="gallery-category-card ' + meta.cardClass + '">';
                cards += '<div class="gallery-category-icon">' + escapeHtml(meta.icon) + '</div>';
                cards += '<div class="gallery-category-copy">';
                cards += '<div class="gallery-category-title">' + escapeHtml(meta.title) + '</div>';
                cards += '<div class="gallery-category-desc">' + escapeHtml(meta.desc) + '</div>';
                cards += '</div>';
                cards += '<button class="gallery-enter-btn" onclick="openGalleryDetail(\\'' + type + '\\')">→</button>';
                cards += '</div>';
            }});
            galleryViewport.innerHTML = '<div class="gallery-home">' + cards + '</div>';
        }}

        function openGalleryDetail(type) {{
            galleryMode = 'category';
            galleryDetailType = type;
            imageCarouselIndex = 0;
            selectedDetailIdx = null;
            galleryReturnState = {{ mode: 'category', timelineSort: timelineSort }};
            closeGalleryMenu();
            renderGallery();
        }}

        function backToGalleryHome() {{
            if (galleryReturnState && galleryReturnState.mode === 'timeline') {{
                galleryMode = 'timeline';
                timelineSort = galleryReturnState.timelineSort || timelineSort;
            }} else {{
                galleryMode = 'category';
            }}
            galleryDetailType = null;
            selectedDetailIdx = null;
            closeGalleryMenu();
            renderGallery();
        }}

        function focusDetailItem(type, idx) {{
            const entry = galleryEntries.find(item => item.idx === idx);
            if (!entry) return;
            galleryDetailType = type;
            selectedDetailIdx = idx;
            if (type === 'image') {{
                const entries = getEntriesByType('image');
                imageCarouselIndex = Math.max(0, entries.findIndex(item => item.idx === idx));
            }}
            jumpTo(entry.start);
            renderGallery();
        }}

        function renderTextualDetail(type) {{
            const entries = getEntriesByType(type);
            let itemsHtml = '';
            entries.forEach(item => {{
                let cls = type === 'text' ? 'gallery-detail-item text-item' : 'gallery-detail-item';
                if (item.idx === selectedDetailIdx) cls += ' active';
                itemsHtml += '<div class="' + cls + '" onclick="focusDetailItem(\\'' + type + '\\',' + item.idx + ')">';
                itemsHtml += '<div class="gallery-detail-time">' + formatTime(item.start) + '</div>';
                itemsHtml += '<div class="gallery-detail-title">' + escapeHtml(item.title || item.topic || getCategoryMeta(type).title) + '</div>';
                itemsHtml += '<div class="gallery-detail-subtext">' + escapeHtml(item.summary || item.topic || '点击后跳转到对应视频位置') + '</div>';
                itemsHtml += '</div>';
            }});
            let html = '';
            html += '<div class="gallery-detail-layout">';
            html += '<div class="gallery-side">';
            html += '<button class="gallery-back-btn" onclick="backToGalleryHome()">←</button>';
            html += '</div>';
            html += '<div class="gallery-detail-list">' + itemsHtml + '</div>';
            html += '</div>';
            galleryViewport.innerHTML = html;
            const activeItem = galleryViewport.querySelector('.gallery-detail-item.active');
            if (activeItem) {{
                setTimeout(() => activeItem.scrollIntoView({{ block: 'center', behavior: 'smooth' }}), 0);
            }}
        }}

        function renderImageDetail() {{
            const entries = getEntriesByType('image');
            if (!entries.length) {{
                backToGalleryHome();
                return;
            }}
            let html = '';
            html += '<div class="gallery-image-detail">';
            html += '<div class="gallery-side">';
            html += '<button class="gallery-back-btn" onclick="backToGalleryHome()">←</button>';
            html += '</div>';
            html += '<div class="gallery-image-main">';
            entries.forEach(item => {{
                const imageHtml = item.svgPath
                    ? '<img src="' + escapeAttr(item.svgPath) + '">'
                    : '<div class="concept-empty">暂无图片</div>';
                html += '<div class="gallery-image-card" onclick="jumpTo(' + item.start + ')">';
                html += '<div class="gallery-image-stage">' + imageHtml + '</div>';
                html += '<div class="gallery-image-caption"><strong>' + escapeHtml(item.title || '图片') + '</strong><br>' + escapeHtml(item.summary || item.topic || '点击图片可跳转到对应时间点。') + '</div>';
                html += '</div>';
            }});
            html += '</div></div>';
            galleryViewport.innerHTML = html;
        }}

        function renderTimelineGallery() {{
            let items = [...galleryEntries];
            items.sort((a, b) => a.start - b.start);
            let cards = '';
            items.forEach(item => {{
                cards += '<div class="timeline-card" onclick="openTimelineItem(\\'' + item.category + '\\',' + item.idx + ')">';
                cards += '<div class="timeline-top">';
                cards += '<div class="timeline-time">' + formatTime(item.start) + '</div>';
                if (item.category === 'image' && item.svgPath) {{
                    cards += '<div class="timeline-media"><img src="' + escapeAttr(item.svgPath) + '" alt=""></div>';
                    cards += '<div class="timeline-bottom">' + escapeHtml(item.summary || item.title || item.topic) + '</div>';
                }} else {{
                    cards += '<div class="timeline-icon">' + escapeHtml(item.icon) + '</div>';
                    cards += '<div class="timeline-production">' + escapeHtml(item.title || item.displayType || item.topic || 'production') + '</div>';
                    cards += '<div class="timeline-summary-pill">' + escapeHtml(item.topic || item.displayType || '内容概览') + '</div>';
                }}
                cards += '</div>';
                // 文字与机制链卡只保留两层信息：标题 + 一条摘要
                cards += '</div>';
            }});
            galleryViewport.innerHTML = '<div class="gallery-mode-timeline">' + cards + '</div>';
        }}

        function openTimelineItem(type, idx) {{
            galleryReturnState = {{ mode: 'timeline', timelineSort: timelineSort }};
            galleryMode = 'category';
            galleryDetailType = type;
            selectedDetailIdx = idx;
            const entry = galleryEntries.find(item => item.idx === idx);
            if (entry) jumpTo(entry.start);
            if (type === 'image') {{
                const entries = getEntriesByType('image');
                imageCarouselIndex = Math.max(0, entries.findIndex(item => item.idx === idx));
            }}
            closeGalleryMenu();
            renderGallery();
        }}

        function setGalleryMode(mode) {{
            galleryMode = mode;
            if (mode === 'timeline') {{
                galleryDetailType = null;
                selectedDetailIdx = null;
            }}
            closeGalleryMenu();
            renderGallery();
        }}

        function setTimelineSort(mode) {{
            timelineSort = mode;
            galleryMode = 'timeline';
            galleryDetailType = null;
            closeGalleryMenu();
            renderGallery();
        }}

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
            collectGalleryEntries();
            const count = galleryEntries.length;
            galleryCount.textContent = count + ' 个增强点';
            galleryMode = 'category';
            galleryDetailType = null;
            selectedDetailIdx = null;
            renderGallery();
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
        }}

        // ========== Utility ==========
        function formatTime(seconds) {{
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
        }}

        // ========== Init ==========
        ensureGalleryReady();
        requestAnimationFrame(ensureGalleryReady);
        setTimeout(ensureGalleryReady, 60);
        setTimeout(ensureGalleryReady, 240);
        window.addEventListener('load', ensureGalleryReady);
        document.addEventListener('DOMContentLoaded', ensureGalleryReady);

        const galleryObserver = new MutationObserver(function() {{
            ensureGalleryReady();
        }});
        if (gallerySource) {{
            galleryObserver.observe(gallerySource, {{ childList: true, subtree: true }});
        }}

        document.addEventListener('click', function(e) {{
            if (!e.target.closest('.gallery-filter-wrap')) {{
                closeGalleryMenu();
            }}
        }});
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
