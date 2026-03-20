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
        
        # 创建assets目录
        self.assets_dir = os.path.join(output_dir, "assets")
        self.svg_dir = os.path.join(self.assets_dir, "svg")
        self.text_cache_dir = os.path.join(self.assets_dir, "text")
        os.makedirs(self.svg_dir, exist_ok=True)
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
            'mechanism_chain': 0,
            'misconception_card': 1,
            'text_card': 2,
            'svg_animation': 3,
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
                    and point['content_type'] in ('svg_animation', 'text_card', 'misconception_card', 'mechanism_chain')
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
            print(f"    [{idx+1}] Text: {content.get('hero_text', 'No Text')}")
        elif point['content_type'] == 'misconception_card':
            content = self._generate_misconception_content(point, idx)
            point['content'] = content
            print(f"    [{idx+1}] Misconception: {content.get('hero_text', 'No Text')}")
        elif point['content_type'] == 'mechanism_chain':
            content = self._generate_mechanism_chain_content(point, idx)
            point['content'] = content
            print(f"    [{idx+1}] Mechanism: {content.get('chain_title', 'No Title')}")
    
    def _generate_svg_content(self, point: Dict, idx: int) -> Dict:
        """生成SVG内容"""
        topic = point['text']
        timestamp = point['timestamp']
        scene_info = point.get('scene_info', {})
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
                        'svg_content': svg_content
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
                    'svg_content': svg_content
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
  
  <rect width="{width}" height="{height}" fill="{bg}"/>
  
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
            'svg_content': svg
        }
    
    def _generate_text_content(self, point: Dict, idx: int) -> Dict:
        """生成文字内容"""
        cache_name = f"text_{idx}_{int(point['timestamp'])}.txt"
        cached = self._load_cached_text_content(cache_name, "text_card")
        if cached:
            return cached

        transcript = point['text']
        duration = point.get('duration', 3.0)
        scene_info = point.get('scene_info', {})
        layout_info = point.get('layout', {})
        
        text_card = self.text_agent.generate_knowledge_card(
            transcript, scene_info, duration, layout_info
        )
        self._save_text_content(cache_name, text_card)
        return text_card

    def _generate_misconception_content(self, point: Dict, idx: int) -> Dict:
        cache_name = f"misconception_{idx}_{int(point['timestamp'])}.txt"
        cached = self._load_cached_text_content(cache_name, "misconception_card")
        if cached:
            return cached

        payload = point.get('metadata', {}).get('misconception_payload') or point.get('misconception_payload') or {}
        content = self.text_agent.generate_misconception_card(
            point['text'],
            point.get('scene_info', {}),
            payload,
            point.get('layout', {})
        )
        self._save_text_content(cache_name, content)
        return content

    def _generate_mechanism_chain_content(self, point: Dict, idx: int) -> Dict:
        cache_name = f"mechanism_{idx}_{int(point['timestamp'])}.txt"
        cached = self._load_cached_text_content(cache_name, "mechanism_chain")
        if cached:
            return cached

        payload = point.get('metadata', {}).get('mechanism_payload') or point.get('mechanism_payload') or {}
        content = self.text_agent.generate_mechanism_chain_card(
            point['text'],
            point.get('scene_info', {}),
            payload,
            point.get('layout', {})
        )
        self._save_text_content(cache_name, content)
        return content

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
