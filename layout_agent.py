"""
Layout Agent
============

智能布局计算：全图搜索 + 多帧时域检测
"""

import os
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple


class LayoutProcessor:
    """布局处理器 - 全图智能搜索"""
    
    def __init__(self, video_path: str):
        """初始化"""
        self.video_path = video_path
    
    def calculate_layouts(
        self,
        decisions: List[Dict],
        output_dir: str,
        force: bool = False
    ) -> List[Dict]:
        """计算布局位置"""
        layout_cache_path = os.path.join(output_dir, "layout_positions.txt")
        
        if not force and os.path.exists(layout_cache_path):
            print(f"  > Loading cached layouts from {layout_cache_path}")
            return self._load_cached_layouts(decisions, layout_cache_path)
        
        print(f"  > Calculating layouts with full-screen search + temporal detection...")
        
        enhancement_points = []
        layouts = []
        
        for idx, dec in enumerate(decisions):
            if dec['enhancement_type'] == 'none':
                continue
            
            start_time = dec['start']
            duration = dec['end'] - dec['start']
            
            # 全图搜索 + 多帧时域检测 + 降级评估
            layout = self.calculate_single_layout(start_time, duration, dec['enhancement_type'])
            
            # 如果算法果断判定没有空间，强制舍弃该叠加图点
            if layout is None:
                print(f"    [{idx+1}] {start_time:.1f}s: (已舍弃 - 无安全放置空间)")
                continue
            
            # 如果降级发生了改变，由于是动态的，所以根据返回的宽高修正 content_type
            final_type = dec['enhancement_type']
            if layout['width'] == 350 and layout['height'] == 200 and final_type == 'svg':
                final_type = 'text_card' # SVG被降级为文字
                
            point = {
                'timestamp': dec['start'],
                'duration': duration,
                'content_type': 'svg_animation' if final_type == 'svg' else 'text_card',
                'text': dec['text'],
                'enhancement_type': final_type,
                'layout': layout,
                'metadata': {'start': dec['start'], 'end': dec['end']}
            }
            
            enhancement_points.append(point)
            layouts.append({'timestamp': start_time, 'layout': layout})
            
            print(f"    [{idx+1}] {start_time:.1f}s: ({layout['x']}, {layout['y']}) "
                  f"score={layout['safety_score']:.2f}")
        
        self._save_layouts(layouts, layout_cache_path)
        print(f"  ✓ Calculated {len(enhancement_points)} layouts")
        
        return enhancement_points
    
    def calculate_single_layout(
        self,
        start_time: float,
        duration: float,
        content_type: str
    ) -> Dict:
        """
        计算单个时间段的最佳布局
        
        策略：全图搜索 + 多帧时域检测
        """
        try:
            # 采样时间段内的多帧（头、中、尾）
            sample_times = self._get_sample_times(start_time, duration)
            
            # 提取多帧
            frames = []
            for t in sample_times:
                frame = self._extract_frame_at_timestamp(t)
                if frame is not None:
                    frames.append(frame)
            
            if not frames:
                return self._create_fallback_layout(content_type)
            
            # 全图搜索最佳位置
            best_layout = self._full_screen_search(frames, content_type)
            
            return best_layout
            
        except Exception as e:
            print(f"      Layout calculation failed: {e}")
            return self._create_fallback_layout(content_type)
    
    def _get_sample_times(self, start_time: float, duration: float) -> List[float]:
        """获取采样时间点（头、中、尾）"""
        if duration < 1.0:
            return [start_time]
        elif duration < 3.0:
            return [start_time, start_time + duration / 2, start_time + duration]
        else:
            # 5个采样点
            return [
                start_time,
                start_time + duration * 0.25,
                start_time + duration * 0.5,
                start_time + duration * 0.75,
                start_time + duration
            ]
    
    def _full_screen_search(
        self,
        frames: List,
        content_type: str,
        overlay_w: int = None,
        overlay_h: int = None
    ) -> Dict:
        """
        全图搜索最佳位置：使用积分图与能量力场
        寻找最“冷”的负空间（Negative Space）
        """
        if overlay_w is None or overlay_h is None:
            if content_type == 'svg':
                overlay_w, overlay_h = 640, 360
            else:
                overlay_w, overlay_h = 350, 200
                
        h, w = frames[0].shape[:2]
        
        # 1. 生成每一帧的综合能量场（0.0 最安全 ~ 1.0 最危险）
        energy_fields = []
        for frame in frames:
            ef = self._generate_energy_field(frame)
            energy_fields.append(ef)
            
        # 2. 将多帧的能量场叠加并取最大值（确保整个持续时间内该位置均安全）
        combined_energy = np.max(np.array(energy_fields), axis=0)
        
        # 3. 使用积分图加速二维矩形区域求和
        best_x, best_y, min_energy = self._find_minimum_energy_window(
            combined_energy, overlay_w, overlay_h, step=20
        )
        
        # 4. 判断是否可放置（单点均值能量阈值例如 >0.15 则认为过于拥挤）
        avg_energy = min_energy / (overlay_w * overlay_h)
        if avg_energy > 0.15:
            # 空间严重不足，尝试降级
            if content_type == 'svg':
                print(f"      [!] 空间不足放置 {overlay_w}x{overlay_h} SVG. 尝试降级为较小的文字卡片.")
                return self._full_screen_search(frames, 'text_card', 350, 200)
            else:
                print(f"      [!] 当前画面过于拥挤密集或都是人脸特写，完全找不到合适放置区. 策略：放弃此浮层.")
                return None
                
        # 确定位置类型
        position_name = self._determine_position_name(best_x, best_y, w, h)
        
        # 提取该位置的局部视觉上下文（颜色、亮度等）
        region_context = self._extract_region_context(
            frames, best_x, best_y, overlay_w, overlay_h
        )
        
        # 将 avg_energy 映射回 0-1 的安全分数 (0.0 energy = 1.0 满分)
        safety_score = max(0.0, 1.0 - (avg_energy / 0.15))
        
        return {
            'x': int(best_x),
            'y': int(best_y),
            'width': overlay_w,
            'height': overlay_h,
            'position': position_name,
            'safety_score': float(safety_score),
            'region_context': region_context
        }

    def _generate_energy_field(self, frame) -> np.ndarray:
        """生成单帧的基础能量场地图 (Height x Width)"""
        h, w = frame.shape[:2]
        energy = np.zeros((h, w), dtype=np.float32)
        
        # 1. Subtitle Area Block (绝对红线区: 底部 15%)
        subtitle_h = int(h * 0.85)
        energy[subtitle_h:, :] = 1.0
        
        # 2. Face Detection Penalty (严格人脸避让)
        faces = self._detect_faces(frame)
        for face in faces:
            fx, fy, fw, fh = face['x'], face['y'], face['w'], face['h']
            # 将人脸保护区外扩 40%
            expand_w = int(fw * 0.4)
            expand_h = int(fh * 0.4)
            start_x, end_x = max(0, fx - expand_w), min(w, fx + fw + expand_w)
            start_y, end_y = max(0, fy - expand_h), min(h, fy + fh + expand_h)
            energy[start_y:end_y, start_x:end_x] = np.maximum(
                energy[start_y:end_y, start_x:end_x], 0.95
            )

        # 3. Center Penalty (避开中心绝对视线焦点区域)
        center_x, center_y = w // 2, h // 2
        max_dist = np.sqrt(center_x**2 + center_y**2)
        
        # 生成基于距离的中心引力网格
        y_grid, x_grid = np.ogrid[:h, :w]
        dist_from_center = np.sqrt((x_grid - center_x)**2 + (y_grid - center_y)**2)
        center_penalty = np.clip(1.0 - (dist_from_center / (max_dist * 0.5)), 0, 0.4)
        energy = np.maximum(energy, center_penalty)

        # 4. Saliency Map Penalty (显著性物体/色块避让)
        saliency_map = self._detect_saliency(frame)
        if saliency_map is not None:
            energy = np.maximum(energy, saliency_map * 0.6)
            
        return energy

    def _find_minimum_energy_window(
        self, combined_energy: np.ndarray, 
        overlay_w: int, overlay_h: int, step: int = 20
    ) -> Tuple[int, int, float]:
        """使用积分图在能量场中寻找总能量最低的矩形窗口"""
        # 创建积分图以便O(1)复杂度计算任意矩形的和
        integral = cv2.integral(combined_energy)
        h, w = combined_energy.shape
        
        best_energy = float('inf')
        best_x = 0
        best_y = 0
        
        # 以步长扫描寻找最佳点
        for y in range(0, h - overlay_h + 1, step):
            for x in range(0, w - overlay_w + 1, step):
                # 利用积分图计算 (x, y) 到 (x+w, y+h) 矩形块的能量和
                # sum = I(x2,y2) - I(x1,y2) - I(x2,y1) + I(x1,y1)
                x2, y2 = x + overlay_w, y + overlay_h
                window_energy = (
                    integral[y2, x2] 
                    - integral[y, x2] 
                    - integral[y2, x] 
                    + integral[y, x]
                )
                
                if window_energy < best_energy:
                    best_energy = window_energy
                    best_x = x
                    best_y = y
                    
        return best_x, best_y, best_energy
    
    def _determine_position_name(self, x: int, y: int, w: int, h: int) -> str:
        """根据坐标确定位置名称"""
        mid_x = w / 2
        mid_y = h / 2
        if x < mid_x and y < mid_y: return 'top-left'
        elif x >= mid_x and y < mid_y: return 'top-right'
        elif x < mid_x and y >= mid_y: return 'bottom-left'
        else: return 'bottom-right'
    
    def _extract_frame_at_timestamp(self, timestamp: float):
        """提取指定时间戳的帧（通过 FFmpeg 截取图像避免 OpenCV 解码崩溃）"""
        import tempfile
        import subprocess
        
        temp_dir = tempfile.gettempdir()
        temp_img = os.path.join(temp_dir, f"frame_{timestamp}.jpg")
        
        try:
            # 使用 FFmpeg 快速提取 timestamp 时的一帧为 JPG
            cmd = [
                'ffmpeg', '-y', '-ss', str(timestamp), 
                '-i', self.video_path,
                '-vframes', '1',
                '-q:v', '2',  # 保证一定的 JPEG 质量
                temp_img
            ]
            subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            
            if os.path.exists(temp_img):
                frame = cv2.imread(temp_img)
                os.remove(temp_img)
                return frame
            return None
        except Exception as e:
            print(f"      FFmpeg 抽帧失败: {e}")
            if os.path.exists(temp_img):
                os.remove(temp_img)
            return None
    
    def _detect_saliency(self, frame):
        """显著性检测"""
        try:
            saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
            success, saliency_map = saliency.computeSaliency(frame)
            return saliency_map if success else np.zeros(frame.shape[:2], dtype=np.float32)
        except:
            return np.zeros(frame.shape[:2], dtype=np.float32)
    
    def _detect_faces(self, frame):
        """人脸检测"""
        try:
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            return [{'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)} 
                   for (x, y, w, h) in faces]
        except:
            return []
    

    def _extract_region_context(
        self,
        frames: list,
        x: int, y: int, w: int, h: int
    ) -> Dict:
        """
        提取 overlay 区域的局部视觉上下文
        
        在 layout 确定位置后调用，为 SVG 生成提供位置感知信息：
        - 区域主色调（SVG 背景应与之协调）
        - 区域亮度（决定 SVG 应用亮色还是暗色主题）
        - 区域类型（纯色/渐变/复杂 → 决定 SVG 是否需要背景遮罩）
        """
        try:
            from sklearn.cluster import KMeans
            
            # 从多帧中裁剪并合并 overlay 区域像素
            all_pixels = []
            brightnesses = []
            edge_densities = []
            
            for frame in frames:
                fh, fw = frame.shape[:2]
                # 边界安全裁剪
                rx = max(0, min(x, fw - 1))
                ry = max(0, min(y, fh - 1))
                rw = min(w, fw - rx)
                rh = min(h, fh - ry)
                
                if rw <= 0 or rh <= 0:
                    continue
                
                region = frame[ry:ry+rh, rx:rx+rw]
                
                # 降采样到 80x60 加速
                small = cv2.resize(region, (80, 60))
                all_pixels.append(small.reshape(-1, 3))
                
                # 计算亮度
                gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                brightnesses.append(float(np.mean(gray)))
                
                # 计算边缘密度（判断区域复杂度）
                edges = cv2.Canny(gray, 50, 150)
                edge_densities.append(float(np.sum(edges > 0) / edges.size))
            
            if not all_pixels:
                return self._create_fallback_region_context()
            
            pixels = np.vstack(all_pixels)
            avg_brightness = np.mean(brightnesses)
            avg_edge_density = np.mean(edge_densities)
            
            # KMeans 提取区域 3 主色
            n_colors = min(3, len(pixels) // 10 + 1)
            kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=5)
            kmeans.fit(pixels)
            
            colors_bgr = kmeans.cluster_centers_.astype(int)
            labels = kmeans.labels_
            counts = np.bincount(labels)
            sorted_idx = np.argsort(-counts)
            
            # 区域主色（占比最大）
            dominant_bgr = colors_bgr[sorted_idx[0]]
            dominant_hex = f"#{dominant_bgr[2]:02x}{dominant_bgr[1]:02x}{dominant_bgr[0]:02x}"
            
            # 所有区域色
            region_colors = [
                f"#{c[2]:02x}{c[1]:02x}{c[0]:02x}" for c in colors_bgr[sorted_idx]
            ]
            
            # 亮度等级
            if avg_brightness > 160:
                brightness_level = 'bright'
            elif avg_brightness > 80:
                brightness_level = 'medium'
            else:
                brightness_level = 'dark'
            
            # 区域类型判断
            color_variance = np.std(counts / counts.sum())
            if avg_edge_density < 0.03 and color_variance < 0.15:
                region_type = 'solid'       # 纯色区域，SVG 可以用透明背景
            elif avg_edge_density < 0.10:
                region_type = 'gradient'    # 渐变区域，SVG 需要半透明背景
            else:
                region_type = 'complex'     # 复杂区域，SVG 需要不透明背景遮罩
            
            # 推荐 SVG 背景不透明度
            if region_type == 'solid':
                recommended_opacity = 0.0   # 纯色区域可以完全透明
            elif region_type == 'gradient':
                recommended_opacity = 0.6   # 渐变区域半透明
            else:
                recommended_opacity = 0.85  # 复杂区域需要较高不透明度
            
            # 对比文字色
            contrast_text = '#ffffff' if avg_brightness < 128 else '#000000'
            
            return {
                'region_bg_color': dominant_hex,
                'region_brightness': brightness_level,
                'region_brightness_value': round(avg_brightness, 1),
                'region_colors': region_colors,
                'region_type': region_type,
                'region_edge_density': round(avg_edge_density, 4),
                'recommended_svg_opacity': recommended_opacity,
                'contrast_text_color': contrast_text,
            }
            
        except Exception as e:
            print(f"      Region context extraction failed: {e}")
            return self._create_fallback_region_context()
    
    def _create_fallback_region_context(self) -> Dict:
        """创建 fallback 的局部上下文"""
        return {
            'region_bg_color': '#1a1a1a',
            'region_brightness': 'dark',
            'region_brightness_value': 40.0,
            'region_colors': ['#1a1a1a', '#333333', '#555555'],
            'region_type': 'solid',
            'region_edge_density': 0.02,
            'recommended_svg_opacity': 0.0,
            'contrast_text_color': '#ffffff',
        }
    
    def _create_fallback_layout(self, content_type: str) -> Dict:
        """创建fallback布局"""
        # 根据content_type决定容器尺寸
        if content_type == 'svg':
            width, height = 640, 360  # SVG使用合理比例的容器
            x, y = 100, 50  # 稍微右移避免完全在角落
        else:
            width, height = 350, 200  # 文本使用小容器
            x, y = 50, 50
        
        return {
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'position': 'top-left',
            'safety_score': 0.5,
            'region_context': self._create_fallback_region_context()
        }
    
    def _save_layouts(self, layouts: List[Dict], filepath: str):
        """保存布局"""
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(layouts, f, ensure_ascii=False, indent=2)
    
    def _load_cached_layouts(self, decisions: List[Dict], filepath: str) -> List[Dict]:
        """加载缓存的布局"""
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cached_layouts = json.load(f)
            
            layout_map = {item['timestamp']: item['layout'] for item in cached_layouts}
            
            points = []
            for dec in decisions:
                if dec['enhancement_type'] == 'none':
                    continue
                
                layout = layout_map.get(dec['start'])
                if not layout:
                    layout = self._create_fallback_layout(dec['enhancement_type'])
                
                point = {
                    'timestamp': dec['start'],
                    'duration': dec['end'] - dec['start'],
                    'content_type': 'svg_animation' if dec['enhancement_type'] == 'svg' else 'text_card',
                    'text': dec['text'],
                    'enhancement_type': dec['enhancement_type'],
                    'layout': layout,
                    'metadata': {'start': dec['start'], 'end': dec['end']}
                }
                points.append(point)
            
            return points
        except Exception as e:
            print(f"      Failed to load cached json layouts: {e}")
            return [{
                'timestamp': dec['start'],
                'duration': dec['end'] - dec['start'],
                'content_type': 'svg_animation' if dec['enhancement_type'] == 'svg' else 'text_card',
                'text': dec['text'],
                'layout': self._create_fallback_layout(dec['enhancement_type']),
                'metadata': {'start': dec['start'], 'end': dec['end']}
            } for dec in decisions if dec['enhancement_type'] != 'none']
