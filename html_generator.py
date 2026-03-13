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
        html_path: str
    ) -> str:
        """
        生成初始HTML骨架 (含视频、字幕面板、空SVG画廊)
        在Phase 6之前调用，用户可立即在浏览器中打开
        """
        video_src = self._resolve_video_source(video_source)
        transcript_data = self._parse_transcript(transcript_path)

        html_content = self._build_skeleton_html(video_src, transcript_data)

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

        content_type = point.get('content_type', 'unknown')
        print(f"    ✓ Appended [{content_type}] #{idx} to HTML")

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

        html_content = self._build_skeleton_html(video_src, transcript_data)

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

    def _build_skeleton_html(self, video_src: str, transcript_data: List[Dict]) -> str:
        """构建完整HTML骨架"""
        transcript_json = json.dumps(transcript_data, ensure_ascii=False)
        subtitle_entries_html = self._generate_subtitle_entries(transcript_data)

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
        </div>

        <!-- Right Panel: Subtitles (Top) & Gallery (Bottom) -->
        <div class="right-panel">
            <div class="subtitle-header">
                <h3>📝 字幕时间线</h3>
                <span class="subtitle-count">{len(transcript_data)} 条字幕</span>
            </div>
            <div class="subtitle-list" id="subtitleList">
{subtitle_entries_html}
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
{self._generate_javascript(transcript_json)}
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
            
            # 使用 width: max-content 让卡片大小自适应文字长短，但使用 max-width 防止超出边界
            w_pct = max(width / self.LAYOUT_CANVAS_W * 100, 25.0)  # 至少给 25% 宽度让文字呼吸
            h_pct_max = max(height / self.LAYOUT_CANVAS_H * 100 * 2.5, 45.0) 
            style = f'left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: max-content; max-width: {w_pct:.2f}%; height: auto; max-height: {h_pct_max:.2f}%; min-height: 5%;'

        content_html = self._generate_content_html(content, point)
        container_class = "enhancement-container"
        if content_type == 'svg':
            container_class += " svg-overlay"

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

        return '<div class="placeholder">Content</div>'

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
            display: flex;
            flex-direction: column;
            border-right: 1px solid var(--border);
            min-width: 0;
            background: #000;
        }

        .right-panel {
            width: 33.33%;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }

        /* ========== Video Section ========== */
        .video-section {
            flex: 0 0 58%;
            display: flex;
            flex-direction: column;
            background: #000;
            border-bottom: 1px solid var(--border);
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
        }

        .enhancement-container.active { opacity: 1; }

        /* SVG Overlay */
        .svg-overlay {
            display: flex;
            align-items: center;
            justify-content: center;
            /* In-Video Cinematic Effect: blend with background */
            mix-blend-mode: screen; 
            filter: drop-shadow(0 0 20px rgba(0,0,0,0.5));
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
        }

        .text-content {
            width: 100%;
            height: auto;
            display: flex;
            overflow: hidden;
        }

        .card-label { 
            font-size: 13px;
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
            font-size: 34px; 
            font-weight: 300; 
            line-height: 1.3; 
            letter-spacing: -0.5px;
            margin: 0; 
            text-shadow: 0 2px 10px rgba(0,0,0,0.5);
            color: #ffffff;
        }
        
        .card-explanation { 
            font-size: 15px; 
            line-height: 1.6; 
            color: rgba(255, 255, 255, 0.75); 
            margin-top: 4px;
            font-weight: 400;
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
            height: 40%;
            display: flex;
            flex-direction: column;
            background: var(--bg-secondary);
            overflow: hidden;
            border-top: 1px solid var(--border);
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

    def _generate_javascript(self, transcript_json: str) -> str:
        return f'''
        // ========== Data ==========
        const transcriptData = {transcript_json};

        // ========== DOM Elements ==========
        const video = document.getElementById('mainVideo');
        const overlayContainer = document.getElementById('overlayContainer');
        const subtitleList = document.getElementById('subtitleList');
        const searchInput = document.getElementById('searchInput');
        const galleryGrid = document.getElementById('galleryGrid');
        const galleryEmpty = document.getElementById('galleryEmpty');
        const galleryCount = document.getElementById('galleryCount');

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
                dot.className = 'timeline-dot ' + (type.includes('svg') ? 'svg-dot' : 'text-dot');
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