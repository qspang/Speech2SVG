"""
Placement Judge Agent
====================

Use a vision-capable LLM to rerank a few candidate overlay placements.
Falls back silently when vision is unavailable or parsing fails.
"""

import json
import os
import tempfile
from typing import Dict, List, Optional

import cv2

from svg_simple.custom_chat_model import CustomChatModel
from langchain_core.messages import SystemMessage


class PlacementJudgeAgent:
    def __init__(self, llm_type: str, debug_print: bool = False):
        self.llm_type = llm_type
        self.llm = CustomChatModel(llm_type=llm_type, temperature=0.1)
        self.debug_print = debug_print

    def available(self) -> bool:
        try:
            return self.llm.supports_vision()
        except Exception:
            return False

    def choose(self, frames, candidates: List[Dict], content_type: str) -> Optional[Dict]:
        if not self.available() or not frames or not candidates:
            return None
        reference_frame = frames[len(frames) // 2]
        preview_path = None
        try:
            preview_path = self._render_preview(frames, candidates)
            prompt = self._build_prompt(content_type)
            messages = [
                SystemMessage(content="Return JSON only."),
                self.llm.create_vision_message(prompt, preview_path),
            ]
            result = self.llm._generate(messages)
            raw = result.generations[0].message.content.strip().replace('```json', '').replace('```', '').strip()
            data = json.loads(raw)
            if self.debug_print:
                print(f"      [PlacementJudge/raw] {data}")
            choice = str(data.get('best_candidate', '')).strip().upper()
            for cand in candidates:
                if cand.get('label') == choice:
                    adjusted = dict(cand)
                    adjusted = self._apply_adjustment(
                        frame=reference_frame,
                        candidate=adjusted,
                        x_shift_ratio=data.get('x_shift_ratio', 0.0),
                        y_shift_ratio=data.get('y_shift_ratio', 0.0),
                        scale_ratio=data.get('scale_ratio', 1.0),
                    )
                    adjusted['judge_reason'] = str(data.get('reason', '')).strip()
                    return adjusted
            return None
        except Exception as e:
            print(f"      PlacementJudgeAgent failed: {e}")
            return None
        finally:
            if preview_path and os.path.exists(preview_path):
                try:
                    os.remove(preview_path)
                except Exception:
                    pass

    def _build_prompt(self, content_type: str) -> str:
        return f"""You are judging overlay placement on a video over time.
We need the best candidate rectangle for a {content_type} overlay.
You are shown a multi-frame preview sampled across the overlay duration, so judge temporal safety, not just one instant.
First inspect the frames and reason about:
- where the speaker, face, body, or main subject is
- where important objects, stage text, logos, screens, microphones, props, or bright salient regions are
- which regions are darker, emptier, less important, and visually quieter
- whether a candidate stays safe across all shown times, not only the middle frame
- treat non-face clutter, saliency, lines, audience texture, and stage geometry only as SOFT references, not hard restrictions

Important visualization rule:
- imagine that the chosen candidate rectangle becomes a fully opaque black overlay that completely covers that region of the video
- judge the placement by this stronger thought experiment, not as a light transparent graphic
- ask yourself: if this area were fully blacked out, would it cover anything truly important?
- then ask yourself: could that black rectangle be enlarged safely, or should it be reduced slightly?

Prioritize:
1. Hard rule: do NOT cover faces at any shown time point.
2. Be bold about size. Prefer the LARGEST candidate that stays reasonably safe.
3. If a bigger candidate only overlaps low-importance background clutter, audience texture, empty stage, or weak saliency, that is acceptable.
4. Keep only a small margin from the video edges; edge proximity is a softer concern than maximizing usable size.
5. Avoid covering the main speaking subject's head and upper torso; other constraints are softer.
6. Do not choose an unnecessarily tiny candidate if a larger one is still acceptable.
7. As a weak prior only, it is acceptable to lean slightly toward the right-lower area when it is clearly as safe or safer, because it is often less critical than upper speaker regions.
8. After choosing the best candidate, you may request:
   - a SMALL position adjustment inside nearby free space
   - a SMALL size reduction if the overlay still feels too dominant
   - a SMALL size increase if there is clearly more free space around it

Candidates are labeled A, B, C, D.
Return JSON only:
{{"best_candidate": "A", "x_shift_ratio": 0.0, "y_shift_ratio": 0.0, "scale_ratio": 1.0, "reason": "short"}}

Adjustment rules:
- x_shift_ratio and y_shift_ratio must be between -0.18 and 0.18
- values are relative to the candidate width / height
- use small shifts only
- prefer shifting inward from edges
- do not invent a completely different placement
- scale_ratio must be between 0.72 and 1.20
- reduce size when the candidate still overlaps visual importance or feels too heavy
- increase size only when the candidate is clearly surrounded by safe empty space
"""

    def _apply_adjustment(self, frame, candidate: Dict, x_shift_ratio, y_shift_ratio, scale_ratio) -> Dict:
        try:
            x_ratio = max(-0.18, min(0.18, float(x_shift_ratio)))
        except Exception:
            x_ratio = 0.0
        try:
            y_ratio = max(-0.18, min(0.18, float(y_shift_ratio)))
        except Exception:
            y_ratio = 0.0
        try:
            scale = max(0.72, min(1.20, float(scale_ratio)))
        except Exception:
            scale = 1.0

        h, w = frame.shape[:2]
        orig_w = int(candidate['width'])
        orig_h = int(candidate['height'])
        cand_w = max(220, int(orig_w * scale))
        cand_h = max(140, int(orig_h * scale))
        safe_x = max(8, int(w * 0.015))
        safe_y = max(8, int(h * 0.018))

        center_x = candidate['x'] + orig_w / 2.0
        center_y = candidate['y'] + orig_h / 2.0
        x = int(center_x - cand_w / 2.0 + cand_w * x_ratio)
        y = int(center_y - cand_h / 2.0 + cand_h * y_ratio)

        x = max(safe_x, min(w - safe_x - cand_w, x))
        y = max(safe_y, min(h - safe_y - cand_h, y))

        candidate['x'] = x
        candidate['y'] = y
        candidate['width'] = cand_w
        candidate['height'] = cand_h
        return candidate

    def _render_preview(self, frames, candidates: List[Dict]) -> str:
        picked_frames = self._pick_representative_frames(frames)
        colors = {
            'A': (80, 180, 255),
            'B': (120, 220, 140),
            'C': (255, 190, 90),
            'D': (210, 145, 255),
        }
        panels = []
        panel_titles = ["Start", "Middle", "End"]
        for idx, frame in enumerate(picked_frames):
            canvas = frame.copy()
            for cand in candidates:
                label = cand['label']
                x, y, w, h = cand['x'], cand['y'], cand['width'], cand['height']
                color = colors.get(label, (255, 255, 255))
                cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 4)
                cv2.rectangle(canvas, (x, max(0, y - 34)), (x + 46, y), color, -1)
                cv2.putText(canvas, label, (x + 12, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2, cv2.LINE_AA)
            cv2.putText(canvas, panel_titles[min(idx, len(panel_titles) - 1)], (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (245, 245, 245), 2, cv2.LINE_AA)
            panels.append(canvas)
        canvas = cv2.hconcat(panels) if len(panels) > 1 else panels[0]
        fd, path = tempfile.mkstemp(suffix='.jpg', prefix='placement_preview_')
        os.close(fd)
        cv2.imwrite(path, canvas)
        return path

    def _pick_representative_frames(self, frames) -> List:
        if not frames:
            return []
        if len(frames) <= 3:
            return frames
        indices = [0, len(frames) // 2, len(frames) - 1]
        return [frames[i] for i in indices]
