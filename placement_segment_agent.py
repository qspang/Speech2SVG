"""
Placement Segment Agent
=======================

在布局前先对较长字幕片段做场景子片段筛选，优先选择停留更久的稳定场景时间窗。
"""

import json
import os
import tempfile
import subprocess
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional

import cv2
import numpy as np


class PlacementSegmentAgent:
    """为后续 layout / scene 阶段选择更稳定的放置时间片段。"""

    def __init__(self, video_path: str, output_dir: str):
        self.video_path = video_path
        self.output_dir = output_dir
        self.cache_path = os.path.join(output_dir, "placement_time_segments.txt")

    def refine_decisions(
        self,
        decisions: List[Dict[str, Any]],
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        if not decisions:
            return []

        cached = None if force else self._load_cache()
        if cached and self._is_cache_compatible(cached, decisions):
            print(f"  > Loading cached placement windows from {self.cache_path}")
            return self._apply_cache(decisions, cached)

        print("  > Refining placement time windows before layout...")
        records = []
        refined = []
        total = len([d for d in decisions if d.get("enhancement_type") != "none"])
        completed = 0

        for idx, dec in enumerate(decisions):
            original_start = float(dec.get("original_start", dec.get("start", 0.0)))
            original_end = float(dec.get("original_end", dec.get("end", original_start)))
            entry = self._select_stable_subsegment(idx, dec, original_start, original_end)
            records.append(entry)

            updated = deepcopy(dec)
            updated["original_start"] = original_start
            updated["original_end"] = original_end
            updated["start"] = entry["refined_start"]
            updated["end"] = entry["refined_end"]
            updated["placement_window"] = {
                "original_start": original_start,
                "original_end": original_end,
                "refined_start": entry["refined_start"],
                "refined_end": entry["refined_end"],
                "detected_scene_count": entry["detected_scene_count"],
                "boundary_time": entry.get("boundary_time"),
                "selection_reason": entry.get("selection_reason", ""),
                "kept_original": entry.get("kept_original", False),
                "change_score": entry.get("change_score", 0.0),
            }
            refined.append(updated)

            if dec.get("enhancement_type") != "none":
                completed += 1
                print(
                    f"    > Placement window progress: {completed}/{total} "
                    f"({original_start:.1f}-{original_end:.1f}s -> "
                    f"{entry['refined_start']:.1f}-{entry['refined_end']:.1f}s)"
                )

        self._save_cache(records)
        print(f"  ✓ Placement window refinement complete")
        return refined

    def _select_stable_subsegment(
        self,
        idx: int,
        dec: Dict[str, Any],
        start_time: float,
        end_time: float,
    ) -> Dict[str, Any]:
        duration = max(0.0, end_time - start_time)
        base = {
            "index": idx,
            "text": dec.get("text", ""),
            "enhancement_type": dec.get("enhancement_type", "none"),
            "original_start": start_time,
            "original_end": end_time,
            "refined_start": start_time,
            "refined_end": end_time,
            "detected_scene_count": 1,
            "boundary_time": None,
            "selection_reason": "kept_original_short_or_stable",
            "kept_original": True,
            "change_score": 0.0,
        }

        if dec.get("enhancement_type") == "none" or duration < 6.0:
            return base

        sample_times = self._build_sample_times(start_time, end_time)
        frames = []
        valid_times = []
        for ts in sample_times:
            frame = self._extract_frame(ts)
            if frame is not None:
                frames.append(frame)
                valid_times.append(ts)

        if len(frames) < 4:
            base["selection_reason"] = "insufficient_frames_keep_original"
            return base

        change_scores = self._compute_adjacent_change_scores(frames)
        if not change_scores:
            base["selection_reason"] = "no_boundary_keep_original"
            return base

        best_idx = int(np.argmax(change_scores))
        best_score = float(change_scores[best_idx])
        boundary_time = float((valid_times[best_idx] + valid_times[best_idx + 1]) * 0.5)

        left_duration = max(0.0, boundary_time - start_time)
        right_duration = max(0.0, end_time - boundary_time)
        min_side = min(left_duration, right_duration)
        if best_score < 0.34 or min_side < max(2.2, duration * 0.18):
            base["selection_reason"] = "boundary_weak_keep_original"
            base["change_score"] = round(best_score, 4)
            return base

        left_frames = frames[: best_idx + 1]
        right_frames = frames[best_idx + 1 :]
        left_stability = self._estimate_internal_stability(left_frames)
        right_stability = self._estimate_internal_stability(right_frames)

        choose_left = left_duration > right_duration
        if abs(left_duration - right_duration) < 1.2:
            choose_left = left_stability >= right_stability

        refined_start = start_time if choose_left else boundary_time
        refined_end = boundary_time if choose_left else end_time
        chosen_duration = max(0.0, refined_end - refined_start)

        if chosen_duration < max(3.0, duration * 0.30):
            base["selection_reason"] = "chosen_scene_too_short_keep_original"
            base["change_score"] = round(best_score, 4)
            return base

        return {
            "index": idx,
            "text": dec.get("text", ""),
            "enhancement_type": dec.get("enhancement_type", "none"),
            "original_start": start_time,
            "original_end": end_time,
            "refined_start": round(refined_start, 3),
            "refined_end": round(refined_end, 3),
            "detected_scene_count": 2,
            "boundary_time": round(boundary_time, 3),
            "selection_reason": "selected_longer_stable_scene_after_binary_split",
            "kept_original": False,
            "change_score": round(best_score, 4),
        }

    def _build_sample_times(self, start_time: float, end_time: float) -> List[float]:
        duration = max(0.0, end_time - start_time)
        num_samples = max(7, min(13, int(round(duration)) + 3))
        times = np.linspace(start_time, end_time, num=num_samples)
        return [float(t) for t in times]

    def _extract_frame(self, timestamp: float):
        temp_img = os.path.join(
            tempfile.gettempdir(),
            f"placement_seg_{timestamp:.3f}_{uuid.uuid4().hex}.jpg",
        )
        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                self.video_path,
                "-vframes",
                "1",
                "-q:v",
                "2",
                temp_img,
            ]
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=6,
            )
            if not os.path.exists(temp_img):
                return None
            frame = cv2.imread(temp_img)
            return frame
        except Exception:
            return None
        finally:
            if os.path.exists(temp_img):
                os.remove(temp_img)

    def _compute_adjacent_change_scores(self, frames: List[np.ndarray]) -> List[float]:
        scores = []
        for prev_frame, next_frame in zip(frames[:-1], frames[1:]):
            prev_small = cv2.resize(prev_frame, (192, 108))
            next_small = cv2.resize(next_frame, (192, 108))

            prev_gray = cv2.cvtColor(prev_small, cv2.COLOR_BGR2GRAY)
            next_gray = cv2.cvtColor(next_small, cv2.COLOR_BGR2GRAY)
            abs_diff = float(np.mean(np.abs(prev_gray.astype(np.float32) - next_gray.astype(np.float32))) / 255.0)

            prev_hist = cv2.calcHist([prev_small], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            next_hist = cv2.calcHist([next_small], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            prev_hist = cv2.normalize(prev_hist, prev_hist).flatten()
            next_hist = cv2.normalize(next_hist, next_hist).flatten()
            hist_corr = float(cv2.compareHist(prev_hist.astype(np.float32), next_hist.astype(np.float32), cv2.HISTCMP_CORREL))
            hist_change = max(0.0, min(1.0, (1.0 - hist_corr) * 0.5))

            edge_prev = cv2.Canny(prev_gray, 80, 160)
            edge_next = cv2.Canny(next_gray, 80, 160)
            edge_diff = float(np.mean(np.abs(edge_prev.astype(np.float32) - edge_next.astype(np.float32))) / 255.0)

            score = 0.42 * abs_diff + 0.40 * hist_change + 0.18 * edge_diff
            scores.append(score)
        return scores

    def _estimate_internal_stability(self, frames: List[np.ndarray]) -> float:
        if len(frames) < 2:
            return 1.0
        diffs = self._compute_adjacent_change_scores(frames)
        if not diffs:
            return 1.0
        return float(1.0 - min(1.0, np.mean(diffs)))

    def _save_cache(self, records: List[Dict[str, Any]]):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def _load_cache(self) -> Optional[List[Dict[str, Any]]]:
        if not os.path.exists(self.cache_path):
            return None
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _is_cache_compatible(self, cached: List[Dict[str, Any]], decisions: List[Dict[str, Any]]) -> bool:
        if len(cached) != len(decisions):
            return False
        for entry, dec in zip(cached, decisions):
            original_start = float(dec.get("original_start", dec.get("start", 0.0)))
            original_end = float(dec.get("original_end", dec.get("end", original_start)))
            if abs(float(entry.get("original_start", -1.0)) - original_start) > 1e-3:
                return False
            if abs(float(entry.get("original_end", -1.0)) - original_end) > 1e-3:
                return False
            if entry.get("text", "") != dec.get("text", ""):
                return False
        return True

    def _apply_cache(
        self,
        decisions: List[Dict[str, Any]],
        cached: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        refined = []
        for dec, entry in zip(decisions, cached):
            updated = deepcopy(dec)
            original_start = float(entry.get("original_start", dec.get("start", 0.0)))
            original_end = float(entry.get("original_end", dec.get("end", original_start)))
            updated["original_start"] = original_start
            updated["original_end"] = original_end
            updated["start"] = float(entry.get("refined_start", original_start))
            updated["end"] = float(entry.get("refined_end", original_end))
            updated["placement_window"] = {
                "original_start": original_start,
                "original_end": original_end,
                "refined_start": updated["start"],
                "refined_end": updated["end"],
                "detected_scene_count": int(entry.get("detected_scene_count", 1)),
                "boundary_time": entry.get("boundary_time"),
                "selection_reason": entry.get("selection_reason", ""),
                "kept_original": bool(entry.get("kept_original", False)),
                "change_score": float(entry.get("change_score", 0.0)),
            }
            refined.append(updated)
        return refined
