"""
Layout Agent
============

智能布局计算：全图搜索 + 多帧时域检测
"""

import os
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from placement_judge_agent import PlacementJudgeAgent


class LayoutProcessor:
    """布局处理器 - 全图智能搜索"""
    
    def __init__(
        self,
        video_path: str,
        max_workers: int = 1,
        vision_llm_type: str = None,
        enable_print_layout: bool = False,
    ):
        """初始化"""
        self.video_path = video_path
        self.max_workers = max(1, max_workers)
        self.vision_llm_type = vision_llm_type
        self.enable_print_layout = enable_print_layout
        self._yunet_model_path = os.path.join(
            os.path.dirname(__file__),
            "models",
            "face_detection_yunet_2023mar.onnx",
        )
        self._face_detector = self._init_face_detector()
        self.safe_margin_x = 36
        self.safe_margin_y = 28
        self.placement_judge = PlacementJudgeAgent(vision_llm_type, debug_print=enable_print_layout) if vision_llm_type else None

    def _debug(self, message: str):
        if self.enable_print_layout:
            print(message)

    def _init_face_detector(self):
        try:
            if os.path.exists(self._yunet_model_path) and hasattr(cv2, "FaceDetectorYN_create"):
                detector = cv2.FaceDetectorYN_create(
                    self._yunet_model_path,
                    "",
                    (320, 320),
                    0.78,
                    0.3,
                    5000,
                )
                self._debug(f"      [Layout] YuNet enabled: {self._yunet_model_path}")
                return detector
        except Exception as e:
            print(f"      YuNet init failed: {e}")
        return None
    
    def calculate_layouts(
        self,
        decisions: List[Dict],
        output_dir: str,
        force: bool = False
    ) -> List[Dict]:
        """计算布局位置"""
        layout_cache_path = os.path.join(output_dir, "layout_positions.txt")
        
        if not force and os.path.exists(layout_cache_path):
            cached_points = self._load_cached_layouts(decisions, layout_cache_path)
            if cached_points is not None:
                print(f"  > Loading cached layouts from {layout_cache_path}")
                return cached_points
            print(f"  > Layout cache stale after placement-window refinement. Recomputing.")
        
        print(f"  > Calculating layouts with full-screen search + temporal detection (workers={self.max_workers})...")
        
        enhancement_points = []
        layouts = []
        completed = 0
        total = len([dec for dec in decisions if dec['enhancement_type'] != 'none'])
        
        candidates = [(idx, dec) for idx, dec in enumerate(decisions) if dec['enhancement_type'] != 'none']
        if self.max_workers <= 1:
            results = []
            for idx, dec in candidates:
                result = self._calculate_layout_for_decision(idx, dec)
                results.append(result)
                completed += 1
                print(f"    > Layout progress: {completed}/{total}")
        else:
            results = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._calculate_layout_for_decision, idx, dec): idx
                    for idx, dec in candidates
                }
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    completed += 1
                    idx = result[0]
                    start_time = result[2]
                    print(f"    > Layout progress: {completed}/{total} (segment #{idx+1} @ {start_time:.1f}s)")

        for result in sorted(results, key=lambda item: item[0]):
            idx, point, start_time, layout = result
            if point is None:
                print(f"    [{idx+1}] {start_time:.1f}s: (已舍弃 - 无安全放置空间)")
                continue
            enhancement_points.append(point)
            layouts.append({
                'timestamp': start_time,
                'end': point['timestamp'] + point['duration'],
                'text': point['text'],
                'layout': layout,
            })
            print(f"    [{idx+1}] {start_time:.1f}s: ({layout['x']}, {layout['y']}) "
                  f"score={layout['safety_score']:.2f}")
        
        self._save_layouts(layouts, layout_cache_path)
        print(f"  ✓ Calculated {len(enhancement_points)} layouts")
        
        return enhancement_points

    def _calculate_layout_for_decision(self, idx: int, dec: Dict):
        start_time = dec['start']
        duration = dec['end'] - dec['start']
        layout = self.calculate_single_layout(
            start_time,
            duration,
            dec['enhancement_type'],
            dec.get('svg_mode_hint', 'none')
        )
        if layout is None:
            return idx, None, start_time, None

        final_type = dec['enhancement_type']
        if layout['width'] == 350 and layout['height'] == 200 and final_type in ('svg', 'mechanism_chain', 'misconception'):
            final_type = 'text_card'

        point = {
            'timestamp': dec['start'],
            'duration': duration,
            'content_type': self._map_enhancement_to_content_type(final_type),
            'text': dec['text'],
            'enhancement_type': final_type,
            'visual_description': dec.get('visual_description', ''),
            'svg_mode_hint': dec.get('svg_mode_hint', 'none'),
            'motion_worthiness': dec.get('motion_worthiness', 0.0),
            'motion_grammar_hint': dec.get('motion_grammar_hint', 'none'),
            'animation_reason': dec.get('animation_reason', ''),
            'layout': layout,
            'metadata': {
                'start': dec['start'],
                'end': dec['end'],
                'original_start': dec.get('original_start', dec['start']),
                'original_end': dec.get('original_end', dec['end']),
                'placement_window': dec.get('placement_window', {}),
                'svg_mode_hint': dec.get('svg_mode_hint', 'none'),
                'motion_worthiness': dec.get('motion_worthiness', 0.0),
                'motion_grammar_hint': dec.get('motion_grammar_hint', 'none'),
                'animation_reason': dec.get('animation_reason', ''),
            }
        }
        return idx, point, start_time, layout
    
    def calculate_single_layout(
        self,
        start_time: float,
        duration: float,
        content_type: str,
        svg_mode_hint: str = 'none'
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
            if self.max_workers > 1:
                for t in sample_times:
                    frame = self._extract_frame_at_timestamp(t)
                    if frame is not None:
                        frames.append(frame)
            else:
                frame_workers = min(len(sample_times), 2)
                with ThreadPoolExecutor(max_workers=frame_workers) as executor:
                    futures = [executor.submit(self._extract_frame_at_timestamp, t) for t in sample_times]
                    for future in as_completed(futures):
                        frame = future.result()
                        if frame is not None:
                            frames.append(frame)
            
            if not frames:
                return self._create_fallback_layout(content_type)
            
            # 全图搜索最佳位置
            best_layout = self._full_screen_search(frames, content_type, svg_mode_hint=svg_mode_hint)
            
            return best_layout
            
        except Exception as e:
            print(f"      Layout calculation failed: {e}")
            return self._create_fallback_layout(content_type)
    
    def _get_sample_times(self, start_time: float, duration: float) -> List[float]:
        """获取采样时间点（头、中、尾）"""
        if self.max_workers > 1:
            if duration < 1.0:
                return [start_time]
            return [
                start_time,
                start_time + duration * 0.5,
                start_time + duration
            ]
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
        svg_mode_hint: str = 'none',
        overlay_w: int = None,
        overlay_h: int = None
    ) -> Dict:
        """
        全图搜索最佳位置：使用积分图与能量力场
        寻找最“冷”的负空间（Negative Space）
        """
        if overlay_w is None or overlay_h is None:
            if content_type == 'svg':
                if svg_mode_hint == 'animated_svg':
                    overlay_w, overlay_h = 760, 428
                else:
                    overlay_w, overlay_h = 700, 394
            elif content_type == 'mechanism_chain':
                overlay_w, overlay_h = 680, 260
            elif content_type == 'misconception':
                overlay_w, overlay_h = 460, 252
            else:
                if svg_mode_hint == 'animated_svg':
                    overlay_w, overlay_h = 560, 314
                else:
                    overlay_w, overlay_h = 460, 258
                
        h, w = frames[0].shape[:2]

        orig_overlay_w, orig_overlay_h = overlay_w, overlay_h
        overlay_w, overlay_h = self._adapt_overlay_size(frames, overlay_w, overlay_h, content_type)
        self._debug(
            f"      [Layout/debug] frame={w}x{h} type={content_type} svg_mode={svg_mode_hint} "
            f"size {orig_overlay_w}x{orig_overlay_h} -> {overlay_w}x{overlay_h}"
        )
        
        # 1. 生成每一帧的综合能量场（0.0 最安全 ~ 1.0 最危险）
        energy_fields = []
        for frame in frames:
            ef = self._generate_energy_field(frame)
            energy_fields.append(ef)
            
        # 2. 将多帧的能量场叠加并取最大值（确保整个持续时间内该位置均安全）
        combined_energy = np.max(np.array(energy_fields), axis=0)
        
        size_variants = self._build_size_variants(frames, overlay_w, overlay_h, content_type)
        all_candidates = []
        for cand_w, cand_h in size_variants:
            all_candidates.extend(
                self._find_candidate_windows(
                    combined_energy,
                    cand_w,
                    cand_h,
                    step=20,
                    top_k=3,
                )
            )

        if not all_candidates:
            return self._create_fallback_layout(content_type)

        min_avg_energy = min(c['avg_energy'] for c in all_candidates)
        safe_pool = [
            c for c in all_candidates
            if c['avg_energy'] <= min(0.24, min_avg_energy + 0.05)
        ]
        ranked_pool = safe_pool or all_candidates
        ranked_pool.sort(
            key=lambda c: (
                -c['area_ratio'],
                c['score'],
                c['avg_energy'],
            )
        )

        candidates = []
        labels = ['A', 'B', 'C', 'D']
        for cand in ranked_pool:
            if all(
                abs((cand['x'] + cand['width'] / 2.0) - (s['x'] + s['width'] / 2.0)) > min(cand['width'], s['width']) * 0.40 or
                abs((cand['y'] + cand['height'] / 2.0) - (s['y'] + s['height'] / 2.0)) > min(cand['height'], s['height']) * 0.36
                for s in candidates
            ):
                cand = dict(cand)
                cand['label'] = labels[len(candidates)] if len(candidates) < len(labels) else str(len(candidates) + 1)
                candidates.append(cand)
            if len(candidates) >= 4:
                break

        best_candidate = candidates[0]
        best_x = best_candidate['x']
        best_y = best_candidate['y']
        overlay_w = best_candidate['width']
        overlay_h = best_candidate['height']
        min_energy = best_candidate['avg_energy'] * (overlay_w * overlay_h)

        if self.enable_print_layout and candidates:
            pretty = ", ".join(
                f"{cand['label']}@({cand['x']},{cand['y']},{cand['width']}x{cand['height']}) avg={cand['avg_energy']:.4f} area={cand['area_ratio']:.3f}"
                for cand in candidates
            )
            print(f"      [Layout/candidates] {pretty}")
        if candidates and self.placement_judge and self.placement_judge.available():
            chosen = self.placement_judge.choose(frames, candidates, content_type)
            if chosen:
                if chosen.get('judge_reason'):
                    print(f"      [PlacementJudge] {chosen.get('label', '?')} adjusted -> ({chosen['x']}, {chosen['y']}) | {chosen['judge_reason']}")
                best_x, best_y = chosen['x'], chosen['y']
                overlay_w, overlay_h = chosen['width'], chosen['height']
                min_energy = chosen.get('avg_energy', chosen.get('energy', 0.0)) * (overlay_w * overlay_h)
        
        # 4. 判断是否可放置（单点均值能量阈值例如 >0.15 则认为过于拥挤）
        avg_energy = min_energy / (overlay_w * overlay_h)
        if avg_energy > 0.21:
            # 空间严重不足，尝试降级
            if content_type == 'svg':
                print(f"      [!] 空间不足放置 {overlay_w}x{overlay_h} SVG. 尝试降级为较小的文字卡片.")
                return self._full_screen_search(frames, 'text_card', 350, 200)
            elif content_type == 'mechanism_chain':
                print(f"      [!] 机制链空间不足，降级为文字卡片.")
                return self._full_screen_search(frames, 'text_card', 350, 200)
            elif content_type == 'misconception':
                print(f"      [!] 误解纠正卡空间不足，尝试普通文字卡片.")
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
        if self.enable_print_layout:
            self._debug(
                "      [Layout/region] "
                f"bg={region_context.get('region_bg_color')} "
                f"brightness={region_context.get('region_brightness')} "
                f"type={region_context.get('region_type')} "
                f"opacity={region_context.get('recommended_svg_opacity')}"
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

    def _adapt_overlay_size(self, frames: List, overlay_w: int, overlay_h: int, content_type: str) -> Tuple[int, int]:
        """根据画面拥挤程度自适应收缩 overlay，减少遮挡主体和舞台元素。"""
        try:
            frame = frames[len(frames) // 2]
            h, w = frame.shape[:2]
            occupancy = self._estimate_visual_occupancy(frame)
            self._debug(f"      [Layout/occupancy] type={content_type} occupancy={occupancy:.3f}")
            scale = 1.0
            if occupancy > 0.48:
                scale = 0.90
            elif occupancy > 0.36:
                scale = 1.0
            elif occupancy < 0.20:
                scale = 1.18

            if content_type == 'svg':
                min_w, min_h = 580, 326
            elif content_type == 'mechanism_chain':
                min_w, min_h = 560, 224
            elif content_type == 'misconception':
                min_w, min_h = 400, 216
            else:
                if content_type in ('text', 'text_card'):
                    min_w, min_h = 460, 258
                else:
                    min_w, min_h = 280, 160

            scaled_w = max(min_w, int(overlay_w * scale))
            scaled_h = max(min_h, int(overlay_h * scale))
            scaled_w = min(scaled_w, int(w * 0.78))
            scaled_h = min(scaled_h, int(h * 0.64))
            return scaled_w, scaled_h
        except Exception:
            return overlay_w, overlay_h

    def _build_size_variants(self, frames: List, overlay_w: int, overlay_h: int, content_type: str) -> List[Tuple[int, int]]:
        """围绕当前尺寸构造多组候选大小，优先尝试更大的安全区域。"""
        try:
            frame = frames[len(frames) // 2]
            h, w = frame.shape[:2]
            occupancy = self._estimate_visual_occupancy(frame)
            if content_type == 'svg':
                scales = [1.48, 1.32, 1.18, 1.06, 1.0, 0.90]
            elif content_type in ('text', 'text_card'):
                scales = [1.32, 1.18, 1.06, 1.0, 0.90]
            else:
                scales = [1.26, 1.12, 1.0, 0.90]

            if occupancy > 0.46:
                scales = [1.16, 1.04, 0.94, 0.86]
            elif occupancy < 0.20:
                scales = [1.60, 1.42, 1.24, 1.10, 1.0, 0.90]

            min_w = 500 if content_type == 'svg' else 380
            min_h = 280 if content_type == 'svg' else 210
            max_w = int(w * (0.84 if content_type == 'svg' else 0.72))
            max_h = int(h * (0.68 if content_type == 'svg' else 0.56))

            variants = []
            seen = set()
            for scale in scales:
                cand_w = max(min_w, min(max_w, int(round(overlay_w * scale))))
                cand_h = max(min_h, min(max_h, int(round(overlay_h * scale))))
                key = (cand_w, cand_h)
                if key not in seen:
                    seen.add(key)
                    variants.append(key)
            return variants or [(overlay_w, overlay_h)]
        except Exception:
            return [(overlay_w, overlay_h)]

    def _map_enhancement_to_content_type(self, enhancement_type: str) -> str:
        if enhancement_type == 'svg':
            return 'svg_animation'
        return 'text_card'

    def _generate_energy_field(self, frame) -> np.ndarray:
        """生成单帧的基础能量场地图 (Height x Width)"""
        h, w = frame.shape[:2]
        energy = np.zeros((h, w), dtype=np.float32)
        
        # 1. Subtitle Area Block (仅保留中等约束，不再视为绝对禁区)
        subtitle_h = int(h * 0.85)
        energy[subtitle_h:, :] = 0.45
        
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
                energy[start_y:end_y, start_x:end_x], 0.98
            )

        # 3. Center Penalty (明显减弱，只做很轻的参考)
        center_x, center_y = w // 2, h // 2
        max_dist = np.sqrt(center_x**2 + center_y**2)
        
        # 生成基于距离的中心引力网格
        y_grid, x_grid = np.ogrid[:h, :w]
        dist_from_center = np.sqrt((x_grid - center_x)**2 + (y_grid - center_y)**2)
        center_penalty = np.clip(1.0 - (dist_from_center / (max_dist * 0.42)), 0, 0.10)
        energy = np.maximum(energy, center_penalty)

        # 4. Structural Lines Penalty (弱参考，不再强避让)
        line_map = self._detect_structural_lines(frame)
        if line_map is not None:
            energy = np.maximum(energy, line_map * 0.14)

        # 5. Saliency Map Penalty (弱参考，不再把显著区域当强禁区)
        saliency_map = self._detect_saliency(frame)
        if saliency_map is not None:
            energy = np.maximum(energy, saliency_map * 0.16)
            
        return energy

    def _estimate_visual_occupancy(self, frame) -> float:
        """估计画面中主体/显著元素的占用程度，用于决定 overlay 是否需要缩小。"""
        try:
            h, w = frame.shape[:2]
            faces = self._detect_faces(frame)
            face_area = 0.0
            for face in faces:
                face_area += (face['w'] * face['h']) / max(1.0, (w * h))

            saliency = self._detect_saliency(frame)
            saliency_occ = float(np.mean(saliency > 0.28)) if saliency is not None else 0.0

            line_map = self._detect_structural_lines(frame)
            line_occ = float(np.mean(line_map > 0.18)) if line_map is not None else 0.0

            occupancy = 0.16 * saliency_occ + 0.08 * line_occ + 3.6 * face_area
            return float(min(1.0, max(0.0, occupancy)))
        except Exception:
            return 0.0

    def _find_minimum_energy_window(
        self, combined_energy: np.ndarray, 
        overlay_w: int, overlay_h: int, step: int = 20
    ) -> Tuple[int, int, float]:
        """使用积分图在能量场中寻找总能量最低的矩形窗口，并显式避开边缘与角落。"""
        integral = cv2.integral(combined_energy)
        h, w = combined_energy.shape

        margin_x = min(self.safe_margin_x, max(10, (w - overlay_w) // 8 if w > overlay_w else 10))
        margin_y = min(self.safe_margin_y, max(10, (h - overlay_h) // 8 if h > overlay_h else 10))

        x_start = max(0, margin_x)
        y_start = max(0, margin_y)
        x_end = max(x_start, w - overlay_w - margin_x)
        y_end = max(y_start, h - overlay_h - margin_y)

        best_energy = float('inf')
        best_x = max(0, min(x_start, w - overlay_w))
        best_y = max(0, min(y_start, h - overlay_h))
        area = max(1.0, float(overlay_w * overlay_h))

        for y in range(y_start, y_end + 1, step):
            for x in range(x_start, x_end + 1, step):
                x2, y2 = x + overlay_w, y + overlay_h
                window_energy = (
                    integral[y2, x2]
                    - integral[y, x2]
                    - integral[y2, x]
                    + integral[y, x]
                ) / area

                cx = x + overlay_w / 2.0
                cy = y + overlay_h / 2.0
                edge_dx = min(x, w - (x + overlay_w))
                edge_dy = min(y, h - (y + overlay_h))
                edge_penalty = 0.0
                if edge_dx < margin_x:
                    edge_penalty += 0.08 * (1.0 - edge_dx / max(1.0, margin_x))
                if edge_dy < margin_y:
                    edge_penalty += 0.10 * (1.0 - edge_dy / max(1.0, margin_y))

                vertical_target = 0.48 * h
                vertical_penalty = 0.07 * abs(cy - vertical_target) / max(1.0, h)
                right_lower_preference = (
                    -0.020 * max(0.0, (cx / max(1.0, w)) - 0.56)
                    -0.010 * max(0.0, (cy / max(1.0, h)) - 0.46)
                )

                near_corner = (x < margin_x * 1.25 and y < margin_y * 1.25) or (x > w - overlay_w - margin_x * 1.25 and y < margin_y * 1.25) or (x < margin_x * 1.25 and y > h - overlay_h - margin_y * 1.25) or (x > w - overlay_w - margin_x * 1.25 and y > h - overlay_h - margin_y * 1.25)
                corner_penalty = 0.04 if near_corner else 0.0

                total_energy = float(window_energy + edge_penalty + vertical_penalty + corner_penalty + right_lower_preference)
                if total_energy < best_energy:
                    best_energy = total_energy
                    best_x = x
                    best_y = y

        return best_x, best_y, best_energy
    
    def _find_candidate_windows(
        self,
        combined_energy: np.ndarray,
        overlay_w: int,
        overlay_h: int,
        step: int = 20,
        top_k: int = 3,
    ) -> List[Dict[str, float]]:
        integral = cv2.integral(combined_energy)
        h, w = combined_energy.shape
        margin_x = min(self.safe_margin_x, max(10, (w - overlay_w) // 8 if w > overlay_w else 10))
        margin_y = min(self.safe_margin_y, max(10, (h - overlay_h) // 8 if h > overlay_h else 10))
        x_start = max(0, margin_x)
        y_start = max(0, margin_y)
        x_end = max(x_start, w - overlay_w - margin_x)
        y_end = max(y_start, h - overlay_h - margin_y)
        area = max(1.0, float(overlay_w * overlay_h))
        scored = []
        for y in range(y_start, y_end + 1, step):
            for x in range(x_start, x_end + 1, step):
                x2, y2 = x + overlay_w, y + overlay_h
                window_energy = (
                    integral[y2, x2] - integral[y, x2] - integral[y2, x] + integral[y, x]
                ) / area
                edge_dx = min(x, w - (x + overlay_w))
                edge_dy = min(y, h - (y + overlay_h))
                edge_penalty = 0.0
                if edge_dx < margin_x:
                    edge_penalty += 0.08 * (1.0 - edge_dx / max(1.0, margin_x))
                if edge_dy < margin_y:
                    edge_penalty += 0.10 * (1.0 - edge_dy / max(1.0, margin_y))
                total_energy = float(window_energy + edge_penalty)
                scored.append({
                    'x': x,
                    'y': y,
                    'width': overlay_w,
                    'height': overlay_h,
                    'energy': total_energy,
                    'avg_energy': float(window_energy),
                    'area_ratio': float((overlay_w * overlay_h) / max(1.0, w * h)),
                    'score': total_energy,
                })
        for cand in scored:
            cy = cand['y'] + overlay_h / 2.0
            cx = cand['x'] + overlay_w / 2.0
            vertical_target = 0.48 * h
            cand['score'] += 0.05 * abs(cy - vertical_target) / max(1.0, h)
            cand['score'] += (
                -0.020 * max(0.0, (cx / max(1.0, w)) - 0.56)
                -0.010 * max(0.0, (cy / max(1.0, h)) - 0.46)
            )
            near_corner = (
                (cand['x'] < margin_x * 1.25 and cand['y'] < margin_y * 1.25) or
                (cand['x'] > w - overlay_w - margin_x * 1.25 and cand['y'] < margin_y * 1.25) or
                (cand['x'] < margin_x * 1.25 and cand['y'] > h - overlay_h - margin_y * 1.25) or
                (cand['x'] > w - overlay_w - margin_x * 1.25 and cand['y'] > h - overlay_h - margin_y * 1.25)
            )
            if near_corner:
                cand['score'] += 0.03

        scored.sort(key=lambda item: (item['avg_energy'], item['score']))
        selected = []
        for cand in scored:
            if all(
                abs((cand['x'] + overlay_w / 2.0) - (s['x'] + overlay_w / 2.0)) > overlay_w * 0.55 or
                abs((cand['y'] + overlay_h / 2.0) - (s['y'] + overlay_h / 2.0)) > overlay_h * 0.45
                for s in selected
            ):
                selected.append(cand)
            if len(selected) >= top_k:
                break
        return selected

    def _determine_position_name(self, x: int, y: int, w: int, h: int) -> str:
        """根据坐标确定位置名称"""
        mid_x = w / 2
        top_band = h * 0.28
        bottom_band = h * 0.72
        if y < top_band:
            return 'top-left' if x < mid_x else 'top-right'
        if y > bottom_band:
            return 'bottom-left' if x < mid_x else 'bottom-right'
        return 'middle-left' if x < mid_x else 'middle-right'
    
    def _extract_frame_at_timestamp(self, timestamp: float):
        """提取指定时间戳的帧（通过 FFmpeg 截取图像避免 OpenCV 解码崩溃）"""
        import tempfile
        import subprocess
        import uuid
        
        temp_dir = tempfile.gettempdir()
        temp_img = os.path.join(temp_dir, f"frame_{timestamp}_{uuid.uuid4().hex}.jpg")
        
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
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6
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

    def _detect_structural_lines(self, frame):
        """检测结构线，避免 overlay 压在线条、支架、桌面边缘和几何边界上。"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blur, 60, 160)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=70,
                minLineLength=max(40, frame.shape[1] // 14),
                maxLineGap=18,
            )

            if lines is None:
                return np.zeros(frame.shape[:2], dtype=np.float32)

            line_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            for line in lines[:160]:
                x1, y1, x2, y2 = line[0]
                length = np.hypot(x2 - x1, y2 - y1)
                if length < 32:
                    continue
                cv2.line(line_mask, (x1, y1), (x2, y2), 255, thickness=4)

            kernel = np.ones((15, 15), np.uint8)
            expanded = cv2.dilate(line_mask, kernel, iterations=1)
            return expanded.astype(np.float32) / 255.0
        except Exception:
            return np.zeros(frame.shape[:2], dtype=np.float32)
    
    def _detect_faces(self, frame):
        """人脸检测"""
        try:
            if self._face_detector is None:
                return []
            h, w = frame.shape[:2]
            self._face_detector.setInputSize((w, h))
            _, detections = self._face_detector.detect(frame)
            if detections is None:
                return []
            faces = []
            for det in detections:
                x, y, fw, fh = det[:4]
                confidence = float(det[-1]) if len(det) > 14 else 1.0
                if confidence < 0.72:
                    continue
                faces.append({
                    'x': int(max(0, x)),
                    'y': int(max(0, y)),
                    'w': int(max(1, fw)),
                    'h': int(max(1, fh)),
                })
            return faces
        except Exception:
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
            
            region_frames = frames[:2] if len(frames) > 2 else frames
            for frame in region_frames:
                fh, fw = frame.shape[:2]
                # 边界安全裁剪
                rx = max(0, min(x, fw - 1))
                ry = max(0, min(y, fh - 1))
                rw = min(w, fw - rx)
                rh = min(h, fh - ry)
                
                if rw <= 0 or rh <= 0:
                    continue
                
                region = frame[ry:ry+rh, rx:rx+rw]
                
                # 降采样到 64x48 加速
                small = cv2.resize(region, (64, 48))
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
            kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=2)
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
                recommended_opacity = 0.58  # 保持一定融入感，同时保证可读性
            elif region_type == 'gradient':
                recommended_opacity = 0.72  # 渐变区域需要更稳的底
            else:
                recommended_opacity = 0.88  # 复杂区域需要较高不透明度
            
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
            width, height = 720, 420
            x, y = 104, 168
        else:
            width, height = 350, 200
            x, y = 118, 224
        
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
    
    def _load_cached_layouts(self, decisions: List[Dict], filepath: str) -> List[Dict] | None:
        """加载缓存的布局"""
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cached_layouts = json.load(f)

            if not self._is_layout_cache_compatible(decisions, cached_layouts):
                return None

            layout_map = {item['timestamp']: item['layout'] for item in cached_layouts}
            if self.enable_print_layout:
                print(f"      [Layout/cache] loaded {len(cached_layouts)} cached layouts")
                sample = list(cached_layouts[:3])
                for item in sample:
                    layout = item.get('layout', {})
                    print(
                        "      [Layout/cache/sample] "
                        f"t={item.get('timestamp')} "
                        f"pos={layout.get('position')} "
                        f"xy=({layout.get('x')},{layout.get('y')}) "
                        f"size={layout.get('width')}x{layout.get('height')} "
                        f"score={layout.get('safety_score')}"
                    )
                print("      [Layout/cache] heuristic/vllm rerank logs are skipped because cached layouts were reused")

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
                    'content_type': self._map_enhancement_to_content_type(dec['enhancement_type']),
                    'text': dec['text'],
                    'enhancement_type': dec['enhancement_type'],
                    'visual_description': dec.get('visual_description', ''),
                    'svg_mode_hint': dec.get('svg_mode_hint', 'none'),
                    'motion_worthiness': dec.get('motion_worthiness', 0.0),
                    'motion_grammar_hint': dec.get('motion_grammar_hint', 'none'),
                    'animation_reason': dec.get('animation_reason', ''),
                    'layout': layout,
                    'metadata': {
                        'start': dec['start'],
                        'end': dec['end'],
                        'original_start': dec.get('original_start', dec['start']),
                        'original_end': dec.get('original_end', dec['end']),
                        'placement_window': dec.get('placement_window', {}),
                        'confusion_risk': dec.get('confusion_risk'),
                        'misconception_payload': dec.get('misconception_payload'),
                        'mechanism_payload': dec.get('mechanism_payload'),
                        'svg_mode_hint': dec.get('svg_mode_hint', 'none'),
                        'motion_worthiness': dec.get('motion_worthiness', 0.0),
                        'motion_grammar_hint': dec.get('motion_grammar_hint', 'none'),
                        'animation_reason': dec.get('animation_reason', ''),
                    }
                }
                points.append(point)
            
            return points
        except Exception as e:
            print(f"      Failed to load cached json layouts: {e}")
            return [{
                'timestamp': dec['start'],
                'duration': dec['end'] - dec['start'],
                'content_type': self._map_enhancement_to_content_type(dec['enhancement_type']),
                'text': dec['text'],
                'enhancement_type': dec['enhancement_type'],
                'visual_description': dec.get('visual_description', ''),
                'svg_mode_hint': dec.get('svg_mode_hint', 'none'),
                'motion_worthiness': dec.get('motion_worthiness', 0.0),
                'motion_grammar_hint': dec.get('motion_grammar_hint', 'none'),
                'animation_reason': dec.get('animation_reason', ''),
                'layout': self._create_fallback_layout(dec['enhancement_type']),
                'metadata': {
                    'start': dec['start'],
                    'end': dec['end'],
                    'original_start': dec.get('original_start', dec['start']),
                    'original_end': dec.get('original_end', dec['end']),
                    'placement_window': dec.get('placement_window', {}),
                    'confusion_risk': dec.get('confusion_risk'),
                    'misconception_payload': dec.get('misconception_payload'),
                    'mechanism_payload': dec.get('mechanism_payload'),
                    'svg_mode_hint': dec.get('svg_mode_hint', 'none'),
                    'motion_worthiness': dec.get('motion_worthiness', 0.0),
                    'motion_grammar_hint': dec.get('motion_grammar_hint', 'none'),
                    'animation_reason': dec.get('animation_reason', ''),
                }
            } for dec in decisions if dec['enhancement_type'] != 'none']

    def _is_layout_cache_compatible(self, decisions: List[Dict], cached_layouts: List[Dict]) -> bool:
        expected = [dec for dec in decisions if dec['enhancement_type'] != 'none']
        if len(expected) != len(cached_layouts):
            return False
        for dec, cached in zip(expected, cached_layouts):
            if abs(float(cached.get('timestamp', -1.0)) - float(dec['start'])) > 1e-3:
                return False
            if abs(float(cached.get('end', -1.0)) - float(dec['end'])) > 1e-3:
                return False
            if cached.get('text', '') != dec.get('text', ''):
                return False
        return True
