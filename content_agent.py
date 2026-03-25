"""
Content Agent
=============

内容生成协调器 - SVG动画 + 文字卡片
统一画布: 1920x1080
支持 max_workers 并发生成
"""

import os
import json
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from text_agent import TextAgent
from text_to_svg_agent import TextToSVGAgent
from overlay_style_agent import OverlayStyleAgent

# 统一画布常量
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class ContentAgent:
    """内容生成Agent - 协调SVG和文字生成（支持并发）"""
    
    def __init__(self, llm_type: str, vision_llm_type: str, output_dir: str,
                 svg_mode: str = "simple", max_workers: int = 1):
        """初始化"""
        self.llm_type = llm_type
        self.vision_llm_type = vision_llm_type
        self.output_dir = output_dir
        self.svg_mode = svg_mode
        self.max_workers = max(1, max_workers)
        
        # 初始化TextAgent
        self.text_agent = TextAgent(llm_type)
        self.text_to_svg_agent = TextToSVGAgent(llm_type)
        self.overlay_style_agent = OverlayStyleAgent(llm_type)
        
        # 创建assets目录
        self.assets_dir = os.path.join(output_dir, "assets")
        self.svg_dir = os.path.join(self.assets_dir, "svg")
        self.t2svg_dir = os.path.join(self.assets_dir, "t2svg")
        self.text_cache_dir = os.path.join(self.assets_dir, "text")
        os.makedirs(self.svg_dir, exist_ok=True)
        os.makedirs(self.t2svg_dir, exist_ok=True)
        os.makedirs(self.text_cache_dir, exist_ok=True)
    
    def generate_content(
        self,
        enhancement_points: List[Dict],
        html_generator=None,
        html_path: str = None
    ) -> List[Dict]:
        """
        生成内容（支持多线程并发）
        
        Args:
            enhancement_points: 增强点列表
            html_generator: HTMLGenerator实例（可选，用于增量更新）
            html_path: HTML文件路径（可选，配合html_generator使用）
        """
        total = len(enhancement_points)
        print(f"  > Generating content for {total} points (max_workers={self.max_workers})...")
        
        if self.max_workers <= 1:
            # 串行模式（兼容原有行为）
            self._generate_sequential(enhancement_points, html_generator, html_path)
        else:
            # 并发模式
            self._generate_concurrent(enhancement_points, html_generator, html_path)
        
        print(f"  ✓ Content generation complete")
        return enhancement_points

    def _content_priority(self, point: Dict) -> int:
        content_type = point.get('content_type')
        priorities = {
            'text_card': 0,
            'svg_animation': 1,
        }
        return priorities.get(content_type, 99)

    def _ordered_points(self, enhancement_points: List[Dict]):
        indexed_points = list(enumerate(enhancement_points))
        indexed_points.sort(key=lambda item: (self._content_priority(item[1]), item[0]))
        return indexed_points
    
    def _generate_sequential(self, enhancement_points, html_generator, html_path):
        """串行生成（max_workers=1 时的原有逻辑）"""
        for idx, point in self._ordered_points(enhancement_points):
            self._process_single_point(point, idx)
            
            # 增量追加到HTML
            if html_generator and html_path and 'content' in point:
                try:
                    html_generator.append_content(html_path, point, idx)
                except Exception as e:
                    print(f"    ⚠ HTML追加失败: {e}")
    
    def _generate_concurrent(self, enhancement_points, html_generator, html_path):
        """并发生成（max_workers>1 时使用 ThreadPoolExecutor）"""
        import threading
        html_lock = threading.Lock()
        
        completed_count = 0
        total = len(enhancement_points)

        ordered_points = self._ordered_points(enhancement_points)
        priority_levels = [0, 1, 2, 3]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for priority in priority_levels:
                batch = [
                    (idx, point) for idx, point in ordered_points
                    if self._content_priority(point) == priority
                    and point['content_type'] in ('svg_animation', 'text_card')
                ]
                if not batch:
                    continue

                futures = {
                    executor.submit(self._process_single_point, point, idx): (point, idx)
                    for idx, point in batch
                }

                # 每个优先级批次按完成顺序 append，确保 chain 总是最先进入 HTML
                for fut in as_completed(futures):
                    point, idx = futures[fut]
                    try:
                        fut.result()
                        completed_count += 1
                        print(f"    ✓ [{completed_count}/{total}] Point #{idx} done")

                        if html_generator and html_path and 'content' in point:
                            with html_lock:
                                try:
                                    html_generator.append_content(html_path, point, idx)
                                except Exception as e:
                                    print(f"    ⚠ HTML追加失败: {e}")

                    except Exception as e:
                        print(f"    ✗ Point #{idx} failed: {e}")
    
    def _process_single_point(self, point: Dict, idx: int):
        """处理单个增强点（线程安全）"""
        if point['content_type'] == 'svg_animation':
            content = self._generate_svg_content(point, idx)
            point['content'] = content
            
            if 'layout' in point and 'position' not in point['layout']:
                point['layout']['position'] = 'center'
            
            print(f"    [{idx+1}] SVG: {content.get('path', 'inline')}")
            
        elif point['content_type'] == 'text_card':
            content = self._generate_text_content(point, idx)
            point['content'] = content
            print(f"    [{idx+1}] Text→SVG: {content.get('title', point.get('text', 'No Text')[:40])}")
    
    def _build_styled_scene_info(self, point: Dict, content_kind: str) -> Dict:
        """为每个 overlay 单独规划背景/边框/文字颜色。"""
        import copy

        base_scene = copy.deepcopy(point.get('scene_info', {}) or {})
        layout_info = point.get('layout', {}) or {}
        style_plan = self.overlay_style_agent.plan_style(
            transcript=point.get('text', ''),
            scene_info=base_scene,
            layout_info=layout_info,
            content_kind=content_kind,
        )
        base_scene['overlay_style'] = style_plan
        design = dict(base_scene.get('design_guide', {}) or {})
        design['recommended_bg'] = style_plan.get('background', design.get('recommended_bg', '#122238'))
        design['recommended_border'] = style_plan.get('border', design.get('recommended_border', design.get('recommended_accent', '#7aa7d8')))
        design['recommended_accent'] = style_plan.get('primary_accent', design.get('recommended_accent', '#7aa7d8'))
        design['recommended_secondary'] = style_plan.get('secondary_accent', design.get('recommended_secondary', design.get('recommended_accent', '#7aa7d8')) )
        design['recommended_text'] = style_plan.get('text', design.get('recommended_text', '#f8fbff'))
        design['svg_bg_opacity'] = style_plan.get('bg_opacity', design.get('svg_bg_opacity', 0.84))
        base_scene['design_guide'] = design
        return base_scene

    def _generate_svg_content(self, point: Dict, idx: int) -> Dict:
        """生成SVG内容"""
        topic = point['text']
        timestamp = point['timestamp']
        scene_info = self._build_styled_scene_info(point, 'svg')
        layout_info = point.get('layout', {})
        motion_context = {
            'svg_mode_hint': point.get('svg_mode_hint', point.get('metadata', {}).get('svg_mode_hint', 'none')),
            'motion_worthiness': point.get('motion_worthiness', point.get('metadata', {}).get('motion_worthiness', 0.0)),
            'motion_grammar_hint': point.get('motion_grammar_hint', point.get('metadata', {}).get('motion_grammar_hint', 'none')),
            'animation_reason': point.get('animation_reason', point.get('metadata', {}).get('animation_reason', '')),
        }
        
        try:
            import sys
            # Mode routing
            if getattr(self, 'svg_mode', 'simple') == 'complex':
                svg_module_path = os.path.join(os.path.dirname(__file__), 'svg_agent')
            elif getattr(self, 'svg_mode', 'simple') == 'normal':
                svg_module_path = os.path.join(os.path.dirname(__file__), 'svg_common')
            else:
                svg_module_path = os.path.join(os.path.dirname(__file__), 'svg_simple')
            sys.path.insert(0, svg_module_path)
            from main import generate_svg_from_text
            
            # 布局上下文 — 使用布局代理计算出的真实区域大小，避免在HTML渲染时被二次缩小导致文字不可见
            # 兼容：如果未提供具体宽高，则回退为默认大画布
            layout_w = layout_info.get('width', CANVAS_WIDTH)
            layout_h = layout_info.get('height', CANVAS_HEIGHT)
            
            layout_context = {
                'width': layout_w,
                'height': layout_h,
                'position': layout_info.get('position', 'center'),
                # 局部区域上下文（来自 layout_agent 的位置感知分析）
                'region_context': layout_info.get('region_context', {}),
            }
            
            actual_sample_id = f"animation_{idx}_{int(timestamp)}"
            filename = f"animation_{idx}_{int(timestamp)}.svg"
            filepath = os.path.join(self.svg_dir, filename)
            
            # --- 缓存跳过逻辑 START ---
            if os.path.exists(filepath):
                print(f"      [Cache] Found existing SVG {filename}, skipping generation.")
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        svg_content = f.read()
                    return {
                        'type': 'svg',
                        'path': f'temp_analysis/assets/svg/{filename}',
                        'svg_content': svg_content,
                        'overlay_style': scene_info.get('overlay_style', {}),
                    }
                except Exception as e:
                    print(f"      [Cache] Read failed: {e}, falling back to generation.")
            # --- 缓存跳过逻辑 END ---
            
            result = generate_svg_from_text(
                text_input=topic,
                output_dir=self.svg_dir,
                save_file=True,
                llm_type=self.llm_type,
                vision_llm_type=self.vision_llm_type,
                layout_context=layout_context,
                scene_context=scene_info,
                motion_context=motion_context,
                enable_complex_mode=(getattr(self, 'svg_mode', 'simple') == 'complex'),
                sample_id=actual_sample_id,
                visual_description=point.get('visual_description', ''),
            )
            
            svg_content = result.get('svg_content', '')
            
            if svg_content:
                svg_content = self._safe_color_adapt(svg_content, scene_info)
                
                filename = f"animation_{idx}_{int(timestamp)}.svg"
                filepath = os.path.join(self.svg_dir, filename)
                
                if 'xmlns=' not in svg_content:
                    svg_content = svg_content.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(svg_content)
                
                return {
                    'type': 'svg',
                    'path': f'temp_analysis/assets/svg/{filename}',
                    'svg_content': svg_content,
                    'overlay_style': scene_info.get('overlay_style', {}),
                }
            
        except Exception as e:
            print(f"      SVG generation failed: {e}")
        
        return self._generate_fallback_svg(topic, scene_info, idx, timestamp, layout_info)
    
    def _safe_color_adapt(self, svg_content: str, scene_info: Dict) -> str:
        """
        [DEPRECATED] 颜色适配已移至 SVGCreatorAgent 内部通过 Context 实现
        此处仅保留为了兼容性，不再进行强制字符串替换，以免破坏精心设计的调色板
        """
        return svg_content
    
    def _generate_fallback_svg(
        self,
        topic: str,
        scene_info: Dict,
        idx: int,
        timestamp: float,
        layout_info: Dict = None
    ) -> Dict:
        """生成fallback SVG"""
        if layout_info is None:
            layout_info = {}

        width = layout_info.get('width', CANVAS_WIDTH)
        height = layout_info.get('height', CANVAS_HEIGHT)

        design = scene_info.get('design_guide', {})
        bg = design.get('recommended_bg', '#0a0a1a')
        accent = design.get('recommended_accent', '#00f3ff')
        border = design.get('recommended_border', accent)
        bg_opacity = design.get('svg_bg_opacity', 0.86)
        
        safe_topic = topic[:30] if topic else "Info"
        cx = width // 2
        cy = height // 2
        
        svg = f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <style>
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .pulse {{ animation: pulse 2s ease-in-out infinite; }}
    .fade {{ animation: fadeIn 1s ease-out forwards; }}
  </style>
  
  <rect width="{width}" height="{height}" rx="28" fill="{bg}" fill-opacity="{bg_opacity}" stroke="{border}" stroke-width="3"/>
  
  <text x="{cx}" y="{cy - 50}" font-family="sans-serif" font-size="32" 
        fill="{accent}" text-anchor="middle" class="fade">
    {safe_topic}
  </text>
  
  <circle cx="{cx}" cy="{cy}" r="100" fill="none" stroke="{accent}" 
          stroke-width="3" class="pulse"/>
  <circle cx="{cx}" cy="{cy}" r="70" fill="none" stroke="{accent}" 
          stroke-width="2" opacity="0.5" class="pulse"/>
</svg>'''
        
        filename = f"fallback_{idx}_{int(timestamp)}.svg"
        filepath = os.path.join(self.svg_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(svg)
        
        return {
            'type': 'svg',
            'path': f'temp_analysis/assets/svg/{filename}',
            'svg_content': svg,
            'overlay_style': scene_info.get('overlay_style', {}),
        }
    
    def _generate_text_content(self, point: Dict, idx: int) -> Dict:
        """生成文字内容（专用 text->SVG 链）"""
        return self._generate_t2svg_content(point, idx, mode="text")

    def _generate_t2svg_content(self, point: Dict, idx: int, mode: str) -> Dict:
        """
        文字 / 机制链统一走独立的 text-to-SVG 生成链。
        成功时缓存到 assets/t2svg，后续直接读取并 append 到 HTML。
        """
        timestamp = point['timestamp']
        prefix = 'mechanism' if mode == 'mechanism' else 'text'
        version_tag = "v4"
        filename = f"{prefix}_{version_tag}_{idx}_{int(timestamp)}.svg"
        filepath = os.path.join(self.t2svg_dir, filename)

        if os.path.exists(filepath):
            print(f"      [Cache] Found existing t2svg {filename}, skipping generation.")
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                legacy_markers = ("INSIGHT", "OBSERVATION", "NOTE")
                if any(marker in svg_content for marker in legacy_markers):
                    print(f"      [Cache] Legacy t2svg detected in {filename}, regenerating.")
                    raise ValueError("legacy_t2svg_cache")
                return {
                    'type': 'svg',
                    'path': f'temp_analysis/assets/t2svg/{filename}',
                    'svg_content': svg_content,
                    'title': point.get('text', '')[:72],
                    'subtitle': point.get('text', '')[:120],
                    'svg_intent': 'mechanism_process' if mode == 'mechanism' else 'knowledge_note',
                    'overlay_style': self._build_styled_scene_info(point, 't2svg_mechanism' if mode == 'mechanism' else 't2svg_text').get('overlay_style', {}),
                }
            except Exception as e:
                print(f"      [Cache] Failed to load t2svg {filename}: {e}, regenerating.")

        styled_scene_info = self._build_styled_scene_info(point, 't2svg_text')

        result = self.text_to_svg_agent.generate_text_svg(
            transcript=point['text'],
            scene_info=styled_scene_info,
            layout_info=point.get('layout', {}),
            mode="text",
            payload={},
        )

        svg_content = result.get('svg_content', '').strip()
        if svg_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(svg_content)
            return {
                'type': 'svg',
                'path': f'temp_analysis/assets/t2svg/{filename}',
                'svg_content': svg_content,
                'title': result.get('title', point.get('text', '')[:72]),
                'subtitle': result.get('subtitle', point.get('text', '')[:120]),
                'svg_intent': 'knowledge_note',
                'overlay_style': styled_scene_info.get('overlay_style', {}),
            }
        fallback_result = self.text_to_svg_agent.generate_text_svg(
            transcript=point['text'],
            scene_info=styled_scene_info,
            layout_info=point.get('layout', {}),
            mode="text",
            payload={},
        )
        fallback_svg = fallback_result.get('svg_content', '').strip()
        if fallback_svg:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fallback_svg)
            return {
                'type': 'svg',
                'path': f'temp_analysis/assets/t2svg/{filename}',
                'svg_content': fallback_svg,
                'title': fallback_result.get('title', point.get('text', '')[:72]),
                'subtitle': fallback_result.get('subtitle', point.get('text', '')[:120]),
                'svg_intent': 'knowledge_note',
                'overlay_style': styled_scene_info.get('overlay_style', {}),
            }
        return self._generate_fallback_svg(point['text'], styled_scene_info, idx, point['timestamp'], point.get('layout', {}))

    def _generate_svg_note_content(self, point: Dict, idx: int, intent: str) -> Dict:
        """
        将原本的 text / mechanism 内容统一交给 SVG 生成链。
        失败时仍会回退到文字卡，保证系统可用。
        """
        transcript = point['text']
        scene_info = point.get('scene_info', {})
        layout_info = point.get('layout', {})
        timestamp = point['timestamp']

        if intent == "mechanism_process":
            payload = point.get('metadata', {}).get('mechanism_payload') or point.get('mechanism_payload') or {}
            compact = self.text_agent.generate_mechanism_chain_card(
                transcript,
                scene_info,
                payload,
                layout_info
            )
            title = compact.get('chain_title', compact.get('title', transcript[:60]))
            stages = compact.get('stages', [])
            summary = " → ".join(str(stage) for stage in stages[:3]) if stages else transcript[:120]
            visual_description = (
                "Create an explanatory SVG knowledge diagram for a mechanism/process segment. "
                "Use text inside the SVG as a core part of the design. "
                "Show 2-4 clear stages or transformations, with meaningful hierarchy. "
                "Prefer dynamic explanatory motion if possible: staged reveal, path progression, flowing connectors, "
                "highlight transitions, or subtle sequential activation. "
                "Do NOT make it a generic box-and-arrow filler. "
                f"Title: {title}. "
                f"Key stages: {summary}. "
                "Even if the final composition is mostly static, add subtle animation polish."
            )
            motion_overrides = {
                'svg_mode_hint': 'animated_svg',
                'motion_worthiness': max(point.get('motion_worthiness', 0.0), 0.82),
                'motion_grammar_hint': point.get('motion_grammar_hint', 'flow') or 'flow',
                'animation_reason': 'Mechanism/process content should be expressed as an explanatory animated SVG.',
            }
        else:
            compact = self.text_agent.generate_knowledge_card(
                transcript,
                scene_info,
                point.get('duration', 3.0),
                layout_info
            )
            title = compact.get('hero_text', transcript[:60])
            explanation = compact.get('explanation', transcript[:120])
            visual_description = (
                "Create a compact explanatory SVG note card that uses typography, shapes, and layout to present the idea. "
                "Text should live inside the SVG, not as HTML outside it. "
                "Use a strong title, one concise supporting line, and simple visual anchors. "
                "Avoid generic random word nodes and avoid empty template diagrams. "
                "If the idea supports motion, use light-to-medium animation such as staged reveal, emphasis pulse, "
                "underline sweep, progressive highlighting, or connecting line draw-in. "
                f"Primary takeaway: {title}. "
                f"Supporting explanation: {explanation}."
            )
            motion_overrides = {
                'svg_mode_hint': 'animated_svg',
                'motion_worthiness': max(point.get('motion_worthiness', 0.0), 0.62),
                'motion_grammar_hint': point.get('motion_grammar_hint', 'build') or 'build',
                'animation_reason': 'Text insight should be rendered as a typographic SVG note with subtle animation.',
            }

        svg_point = dict(point)
        svg_point['visual_description'] = ((point.get('visual_description') or '').strip() + ' ' + visual_description).strip()
        svg_point['svg_mode_hint'] = motion_overrides['svg_mode_hint']
        svg_point['motion_worthiness'] = motion_overrides['motion_worthiness']
        svg_point['motion_grammar_hint'] = motion_overrides['motion_grammar_hint']
        svg_point['animation_reason'] = motion_overrides['animation_reason']
        svg_point['metadata'] = dict(point.get('metadata', {}))
        svg_point['metadata'].update(motion_overrides)

        svg_content = self._generate_svg_content(svg_point, idx)
        if svg_content and svg_content.get('type') == 'svg':
            svg_content['title'] = title
            svg_content['subtitle'] = compact.get('explanation', compact.get('summary', transcript[:120]))
            svg_content['svg_intent'] = intent
            return svg_content

        # 极端情况下回退到原先的 HTML 文本内容
        if intent == "mechanism_process":
            return compact
        return compact

    def _load_cached_text_content(self, filename: str, content_kind: str) -> Dict:
        filepath = os.path.join(self.text_cache_dir, filename)
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = json.load(f)
            print(f"      [Cache] Found existing {content_kind} {filename}, skipping generation.")
            return content
        except Exception as e:
            print(f"      [Cache] Failed to load {filename}: {e}")
            return {}

    def _save_text_content(self, filename: str, content: Dict):
        filepath = os.path.join(self.text_cache_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"      [Cache] Failed to save {filename}: {e}")
