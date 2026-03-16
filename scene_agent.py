"""
Scene Agent
===========

深度视觉分析：色彩分级、视觉复杂度、设计指南
"""

import os
import numpy as np
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from multimodal_utils import save_scene_analysis, load_scene_analysis, create_fallback_scene_analysis


class SceneAgent:
    """场景分析Agent - 提取深层视觉特征"""
    
    def __init__(
        self,
        video_path: str,
        output_dir: str,
        llm_type: str = "claude-sonnet-4-5-20250929",
        max_workers: int = 1
    ):
        """初始化"""
        self.video_path = video_path
        self.output_dir = output_dir
        self.llm_type = llm_type
        self.max_workers = max(1, max_workers)
        self.scene_cache_path = os.path.join(output_dir, "scene_analysis.txt")
    
    def analyze_scenes(
        self,
        enhancement_points: List[Dict],
        force: bool = False
    ) -> List[Dict]:
        """深度场景分析"""
        scene_info = {}
        cache_valid = False
        cache_complete = False
        
        if not force and os.path.exists(self.scene_cache_path):
            print(f"  > Checking cached scene analysis...")
            try:
                cached_data = load_scene_analysis(self.scene_cache_path)
                if cached_data:
                    first_key = next(iter(cached_data))
                    if 'design_guide' in cached_data[first_key] and \
                       'art_style_name' in cached_data[first_key]['design_guide']:
                        scene_info = cached_data
                        cache_valid = True
                        cache_complete = len(scene_info) >= len(enhancement_points)
                        if cache_complete:
                            print(f"  > Cache is up-to-date. Loading.")
                        else:
                            print(f"  > Partial scene cache found: {len(scene_info)}/{len(enhancement_points)} complete. Resuming.")
                    else:
                        print(f"  > Cache is stale (missing Art Style). Re-analyzing.")
                else:
                    print(f"  > Cache empty. Re-analyzing.")
            except:
                print(f"  > Cache corrupted. Re-analyzing.")

        if not cache_valid or not cache_complete:
            print(f"  > Deep visual feature extraction (Art Style Edition, workers={self.max_workers})...")
            completed = 0
            total = len(enhancement_points)
            pending_indices = [idx for idx in range(total) if str(idx) not in scene_info]
            pending_total = len(pending_indices)

            if self.max_workers <= 1:
                for idx in pending_indices:
                    point = enhancement_points[idx]
                    result_idx, analysis = self._analyze_point(idx, point)
                    scene_info[str(result_idx)] = analysis
                    completed += 1
                    if completed % 5 == 0 or completed == pending_total:
                        self._save_checkpoint(scene_info)
                    print(f"    > Scene progress: {completed}/{pending_total}")
            else:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        executor.submit(self._analyze_point, idx, enhancement_points[idx]): idx
                        for idx in pending_indices
                    }
                    for future in as_completed(futures):
                        idx, analysis = future.result()
                        scene_info[str(idx)] = analysis
                        completed += 1
                        if completed % 5 == 0 or completed == pending_total:
                            self._save_checkpoint(scene_info)
                        print(f"    > Scene progress: {completed}/{pending_total}")
            
            self._save_checkpoint(scene_info)
        
        # 添加场景信息到增强点
        for idx, point in enumerate(enhancement_points):
            point['scene_info'] = scene_info.get(str(idx), create_fallback_scene_analysis())
        
        print(f"  ✓ Deep scene analysis complete")
        return enhancement_points

    def _save_checkpoint(self, scene_info: Dict):
        save_scene_analysis(scene_info, self.scene_cache_path)

    def _analyze_point(self, idx: int, point: Dict):
        ts_start = point['timestamp']
        ts_end = point['timestamp'] + point['duration']
        region_context = point.get('layout', {}).get('region_context', {})
        analysis = self._analyze_time_range(ts_start, ts_end, region_context)
        print(f"    [{idx+1}] {ts_start:.1f}s: "
              f"Style={analysis['design_guide'].get('art_style_name', 'Unknown')}")
        return idx, analysis
    
    def _analyze_time_range(self, start_time: float, end_time: float, region_context: Dict = None) -> Dict:
        """深度分析时间范围（含局部区域上下文）"""
        if region_context is None:
            region_context = {}
        try:
            import cv2
            from sklearn.cluster import KMeans
            
            # 采样多帧 — 使用 FFmpeg 抽帧（避免 AV1 解码失败）
            frames = []
            duration = end_time - start_time
            num_samples = min(7, max(3, int(duration * 3)))
            sample_times = np.linspace(start_time, end_time, num=num_samples)
            
            # 使用多线程并发提取当前时间段内的帧
            frame_workers = min(num_samples, 2 if self.max_workers > 1 else 3)
            with ThreadPoolExecutor(max_workers=frame_workers) as executor:
                # 提交所有抽帧任务 (保留时间戳以便后续需要排序)
                future_to_time = {executor.submit(self._extract_frame_ffmpeg, t): t for t in sample_times}
                
                # 收集结果
                for future in as_completed(future_to_time):
                    frame = future.result()
                    if frame is not None:
                        frames.append(frame)
            
            if not frames:
                print(f"      [SceneAgent] ✗ No frames extracted for {start_time:.1f}-{end_time:.1f}s → fallback")
                return create_fallback_scene_analysis()
            
            print(f"      [SceneAgent] ✓ Extracted {len(frames)} frames for {start_time:.1f}-{end_time:.1f}s")
            mid_frame = frames[len(frames) // 2]
            
            # 1. 场景连续性检测
            is_single_scene = self._detect_scene_continuity(frames)
            
            # 2. 色彩分级提取（Color Hierarchy）
            color_hierarchy = self._extract_color_hierarchy(mid_frame)
            
            # 3. 视觉复杂度分析
            visual_complexity = self._analyze_visual_complexity(mid_frame)
            
            # 4. 色彩指标（饱和度、亮度、色温）
            color_metrics = self._extract_color_metrics(mid_frame)
            
            print(f"      [SceneAgent] Colors: bg={color_hierarchy.get('background_color','?')} "
                  f"accent={color_hierarchy.get('accent_color','?')} "
                  f"complexity={visual_complexity} sat={color_metrics.get('saturation_level','?')}")
            
            # 5. 生成设计指南（给SVG和Text用）— 含局部区域上下文
            design_guide = self._generate_design_guide(
                color_hierarchy,
                color_metrics,
                visual_complexity,
                is_single_scene,
                region_context
            )
            
            return {
                'is_single_scene': is_single_scene,
                'color_hierarchy': color_hierarchy,
                'color_metrics': color_metrics,
                'visual_complexity': visual_complexity,
                'design_guide': design_guide,
                'frame_count': len(frames),
                # 兼容旧接口
                'color_palette': color_hierarchy['all_colors'][:5],
                'style_keywords': [visual_complexity, color_metrics['saturation_level']],
                'design_prompt': design_guide  # 别名
            }
            
        except Exception as e:
            print(f"      [SceneAgent] Scene analysis error: {e}")
            return create_fallback_scene_analysis()
    
    def _extract_frame_ffmpeg(self, timestamp: float):
        """通过 FFmpeg 截取单帧图像（避免 OpenCV AV1 解码问题）"""
        import tempfile
        import subprocess
        import uuid
        import cv2
        
        temp_dir = tempfile.gettempdir()
        temp_img = os.path.join(temp_dir, f"scene_frame_{timestamp:.2f}_{uuid.uuid4().hex}.jpg")
        
        try:
            cmd = [
                'ffmpeg', '-y', '-ss', str(timestamp),
                '-i', self.video_path,
                '-vframes', '1',
                '-q:v', '2',
                temp_img
            ]
            subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6
            )
            
            if os.path.exists(temp_img):
                frame = cv2.imread(temp_img)
                os.remove(temp_img)
                return frame
            return None
        except Exception as e:
            if os.path.exists(temp_img):
                os.remove(temp_img)
            return None
    
    def _detect_scene_continuity(self, frames: List) -> bool:
        """检测场景连续性（单场景 vs 多场景）"""
        if len(frames) < 2:
            return True
        
        try:
            import cv2
            
            similarities = []
            for i in range(len(frames) - 1):
                hist1 = cv2.calcHist([frames[i]], [0,1,2], None, [8,8,8], [0,256,0,256,0,256])
                hist2 = cv2.calcHist([frames[i+1]], [0,1,2], None, [8,8,8], [0,256,0,256,0,256])
                
                hist1 = cv2.normalize(hist1, hist1).flatten()
                hist2 = cv2.normalize(hist2, hist2).flatten()
                
                sim = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
                similarities.append(sim)
            
            avg_sim = np.mean(similarities)
            return bool(avg_sim > 0.75)  # Convert to native bool for JSON serialization
            
        except:
            return True
    
    def _extract_color_hierarchy(self, frame) -> Dict:
        """
        色彩分级提取（Color Hierarchy）
        
        返回：
        - background_color: 背景主色（占比最大）
        - accent_color: 强调色（最鲜艳）
        - text_color: 建议文字色（对比度计算）
        - all_colors: 所有主色
        - color_weights: 各颜色占比
        """
        try:
            import cv2
            from sklearn.cluster import KMeans
            
            # 降采样加速
            small = cv2.resize(frame, (150, 150))
            pixels = small.reshape(-1, 3)
            
            # 聚类提取8种主色
            kmeans = KMeans(n_clusters=8, random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            colors_bgr = kmeans.cluster_centers_.astype(int)
            labels = kmeans.labels_
            counts = np.bincount(labels)
            
            # 按占比排序
            sorted_idx = np.argsort(-counts)
            sorted_colors = colors_bgr[sorted_idx]
            sorted_counts = counts[sorted_idx]
            
            # 转hex
            hex_colors = [f"#{c[2]:02x}{c[1]:02x}{c[0]:02x}" for c in sorted_colors]
            
            # 背景色 = 占比最大
            background_color = hex_colors[0]
            
            # 强调色 = 最鲜艳（高饱和度）
            accent_idx = self._find_most_vibrant(sorted_colors)
            accent_color = hex_colors[accent_idx] if accent_idx < len(hex_colors) else hex_colors[1]
            
            # 文字色 = 与背景对比度最高
            bg_luminance = self._calc_luminance(sorted_colors[0])
            text_color = "#ffffff" if bg_luminance < 128 else "#000000"
            
            return {
                'background_color': background_color,
                'accent_color': accent_color,
                'text_color': text_color,
                'all_colors': hex_colors,
                'color_weights': (sorted_counts / sorted_counts.sum()).tolist()
            }
            
        except:
            return {
                'background_color': '#1a1a1a',
                'accent_color': '#00f3ff',
                'text_color': '#ffffff',
                'all_colors': ['#1a1a1a', '#00f3ff', '#ffffff'],
                'color_weights': [0.6, 0.3, 0.1]
            }
    
    def _find_most_vibrant(self, colors_bgr: np.ndarray) -> int:
        """找最鲜艳的颜色（跳过背景）"""
        max_sat = 0
        max_idx = 1
        
        for i in range(1, min(len(colors_bgr), 6)):
            b, g, r = colors_bgr[i]
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            sat = (max_c - min_c) / (max_c + 1)
            
            if sat > max_sat:
                max_sat = sat
                max_idx = i
        
        return max_idx
    
    def _calc_luminance(self, color_bgr: np.ndarray) -> float:
        """计算亮度"""
        b, g, r = color_bgr
        return 0.299 * r + 0.587 * g + 0.114 * b
    
    def _extract_color_metrics(self, frame) -> Dict:
        """
        色彩指标
        
        返回：
        - saturation: 饱和度 [0-1]
        - saturation_level: vibrant/moderate/muted
        - brightness: 亮度 [0-255]
        - brightness_level: bright/medium/dark
        - temperature: warm/cool/neutral
        """
        try:
            import cv2
            
            # 饱和度
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            sat = np.mean(hsv[:, :, 1]) / 255.0
            
            if sat > 0.6:
                sat_level = "vibrant"
            elif sat > 0.3:
                sat_level = "moderate"
            else:
                sat_level = "muted"
            
            # 亮度
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            bright = np.mean(gray)
            
            if bright > 160:
                bright_level = "bright"
            elif bright > 80:
                bright_level = "medium"
            else:
                bright_level = "dark"
            
            # 色温
            b_avg = np.mean(frame[:, :, 0])
            r_avg = np.mean(frame[:, :, 2])
            
            if r_avg > b_avg * 1.15:
                temp = "warm"
            elif b_avg > r_avg * 1.15:
                temp = "cool"
            else:
                temp = "neutral"
            
            return {
                'saturation': float(sat),
                'saturation_level': sat_level,
                'brightness': float(bright),
                'brightness_level': bright_level,
                'temperature': temp
            }
            
        except:
            return {
                'saturation': 0.5,
                'saturation_level': 'moderate',
                'brightness': 128,
                'brightness_level': 'medium',
                'temperature': 'neutral'
            }
    
    def _analyze_visual_complexity(self, frame) -> str:
        """
        视觉复杂度
        
        返回：minimal/moderate/complex
        """
        try:
            import cv2
            
            # 边缘密度 = 复杂度
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            if edge_density < 0.05:
                return "minimal"
            elif edge_density < 0.15:
                return "moderate"
            else:
                return "complex"
                
        except:
            return "moderate"
    
    def _generate_design_guide(
        self,
        color_hierarchy: Dict,
        color_metrics: Dict,
        visual_complexity: str,
        is_single_scene: bool,
        region_context: Dict = None
    ) -> Dict:
        """
        生成设计指南（使用LLM转化）
        
        将视觉参数转为自然语言设计指令
        """
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'svg_agent'))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import SystemMessage, HumanMessage
            
            llm = CustomChatModel(llm_type=self.llm_type, temperature=0.7)
            
            bg = color_hierarchy['background_color']
            accent = color_hierarchy['accent_color']
            text_color = color_hierarchy['text_color']
            all_colors = color_hierarchy['all_colors'][:5]
            
            sat_level = color_metrics['saturation_level']
            bright_level = color_metrics['brightness_level']
            temp = color_metrics['temperature']
            
            system_prompt = """You are a High-End Visual Design Director.
            
Your task: Analyze the visual technical parameters and prescribe a distinct, cohesive ART STYLE for motion graphics that overlays this footage.

**AVOID GENERIC TERMS.** Do not just say "modern" or "clean".

Output JSON:
{
  "art_style_name": "Name of the style (e.g., 'Cyberpunk Glitch', 'Swiss Minimalist', 'Organic Flow')",
  "visual_metaphor": "A core visual concept (e.g., 'Floating data particles', 'Architectural blueprints', 'Liquid gradients')",
  "svg_prompt": "Specific instruction for the SVG artist (shapes, stroke styles, effects)",
  "text_style": "Specific CSS/design instruction for text overlays",
  "recommended_bg": "#hex — MUST harmonize with the overlay region's local background",
  "recommended_accent": "#hex (The most striking color to use)",
  "recommended_secondary": "#hex (Complementary)",
  "svg_bg_opacity": 0.0-1.0
}

**STYLE LOGIC:**
1. **High Tech/Dark**: Use 'Holographic UI' or 'Cyberpunk'. Thin lines, glows, monospaced fonts.
2. **Nature/Bright**: Use 'Organic Glass' or 'Papercut'. Soft shadows, rounded shapes, serif or rounded fonts.
3. **Corporate/Clean**: Use 'Swiss International'. Grid-based, heavy bold text, solid colors (no gradients).
4. **Chaotic/Action**: Use 'Glitch Art'. Asymmetric, jagged shapes, high contrast.

**CRITICAL — OVERLAY REGION BLENDING:**
The SVG overlay will be placed on a specific region of the video frame. You MUST ensure the SVG background blends seamlessly:
- If the region is DARK → use a dark or transparent SVG background, with light/neon accents
- If the region is BRIGHT → use a light or transparent SVG background, with dark/bold accents
- If the region is SOLID color → SVG can use transparent background (the video color shows through)
- If the region is COMPLEX (busy content) → SVG needs a semi-opaque backdrop for readability
- The `recommended_bg` MUST be close to or harmonize with the region's actual background color
- NEVER use a white SVG background on a dark region or vice versa
"""
            
            # 构建局部区域信息
            region_info = ""
            if region_context:
                region_bg = region_context.get('region_bg_color', 'unknown')
                region_bright = region_context.get('region_brightness', 'unknown')
                region_type = region_context.get('region_type', 'unknown')
                region_colors = region_context.get('region_colors', [])
                rec_opacity = region_context.get('recommended_svg_opacity', 0.0)
                region_info = f"""

**🎯 OVERLAY REGION (where the SVG will actually be placed):**
- Region background color: {region_bg}
- Region brightness: {region_bright}
- Region type: {region_type} (solid=clean area, gradient=transition, complex=busy content)
- Region colors: {region_colors}
- Recommended SVG background opacity: {rec_opacity}
- ⚠️ The SVG `recommended_bg` MUST be close to {region_bg} to avoid visual clash!"""
            
            prompt = f"""Generate design guidance based on scene analysis:

**Color Hierarchy (full frame):**
- Background: {bg}
- Accent: {accent}
- Text: {text_color}
- All colors: {all_colors}

**Color Metrics (full frame):**
- Saturation: {sat_level}
- Brightness: {bright_level}
- Temperature: {temp}

**Visual Complexity:** {visual_complexity}
**Scene Type:** {'Single scene' if is_single_scene else 'Multiple scenes'}
{region_info}

Generate specific, actionable design instructions for SVG and text.
The `recommended_bg` and `svg_bg_opacity` MUST account for the overlay region info above.

Return JSON only."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = llm.invoke(messages)
            result_text = response.content
            
            # 解析JSON
            import json
            result_text = result_text.strip()
            if result_text.startswith('```'):
                lines = result_text.split('\n')
                result_text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            design_guide = json.loads(result_text)
            
            return design_guide
            
        except Exception as e:
            print(f"      LLM design guide generation failed: {e}, using fallback")
            # Fallback到原来的简单逻辑
            return self._generate_design_guide_fallback(
                color_hierarchy,
                color_metrics,
                visual_complexity,
                is_single_scene
            )
    
    def _generate_design_guide_fallback(
        self,
        color_hierarchy: Dict,
        color_metrics: Dict,
        visual_complexity: str,
        is_single_scene: bool
    ) -> Dict:
        """降级设计指南生成（简单规则）"""
        bg = color_hierarchy['background_color']
        accent = color_hierarchy['accent_color']
        text_color = color_hierarchy['text_color']
        
        sat_level = color_metrics['saturation_level']
        bright_level = color_metrics['brightness_level']
        
        # SVG设计指令
        if bright_level == 'dark':
            svg_bg_guide = f"Use dark base ({bg}) with neon/glow accents ({accent})"
        elif bright_level == 'bright':
            svg_bg_guide = f"Use light/white base ({bg}) with bold dark accents ({accent})"
        else:
            svg_bg_guide = f"Use mid-tone base ({bg}) with contrasting accents ({accent})"
        
        if sat_level == 'vibrant':
            svg_style_guide = " Keep high saturation, energetic animations"
        elif sat_level == 'muted':
            svg_style_guide = " Use subtle, desaturated tones for elegance"
        else:
            svg_style_guide = " Balanced saturation for clarity"
        
        svg_prompt = svg_bg_guide + "." + svg_style_guide
        
        # Text卡片设计指令
        if is_single_scene:
            if visual_complexity == 'minimal':
                text_style = f"Semi-transparent card with simple border"
            elif visual_complexity == 'complex':
                text_style = f"Strong frosted glass (blur 15px) for high contrast"
            else:
                text_style = f"Subtle glass with accent border"
        else:
            text_style = f"Adaptive frosted glass with backdrop-filter"
        
        return {
            'svg_prompt': svg_prompt,
            'text_style': text_style,
            'recommended_bg': bg,
            'recommended_accent': accent,
            'recommended_text': text_color
        }
