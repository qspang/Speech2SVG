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

    def choose(self, frame, candidates: List[Dict], content_type: str) -> Optional[Dict]:
        if not self.available() or frame is None or not candidates:
            return None
        preview_path = None
        try:
            preview_path = self._render_preview(frame, candidates)
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
                        frame=frame,
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
        return f"""You are judging overlay placement on a video frame.
We need the best candidate rectangle for a {content_type} overlay.
First inspect the frame and reason about:
- where the speaker, face, body, or main subject is
- where important objects, stage text, logos, screens, microphones, props, or bright salient regions are
- which regions are darker, emptier, less important, and visually quieter

Prioritize:
1. Do not cover faces or important speaking subject regions.
2. Keep a comfortable margin from video edges and rounded video corners.
3. Prefer readable negative space and avoid awkward attachment to frame edges.
4. Avoid corners if a safer mid-side position exists.
5. Avoid crossing obvious lines, microphone arms, desk edges, shelves, audience blocks, stage props, large text, logos, or dense objects when possible.
6. Prefer left-middle or right-middle placements over cramped top-corner placements when readability is better.
7. Prefer darker / emptier / visually quieter zones over bright or semantically important regions.
8. After choosing the best candidate, you may request:
   - a SMALL position adjustment inside nearby free space
   - a SMALL size reduction if the overlay still feels too dominant

Candidates are labeled A, B, C, D.
Return JSON only:
{{"best_candidate": "A", "x_shift_ratio": 0.0, "y_shift_ratio": 0.0, "scale_ratio": 0.9, "reason": "short"}}

Adjustment rules:
- x_shift_ratio and y_shift_ratio must be between -0.18 and 0.18
- values are relative to the candidate width / height
- use small shifts only
- prefer shifting inward from edges
- do not invent a completely different placement
- scale_ratio must be between 0.72 and 1.0
- reduce size when the candidate still overlaps visual importance or feels too heavy
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
            scale = max(0.72, min(1.0, float(scale_ratio)))
        except Exception:
            scale = 1.0

        h, w = frame.shape[:2]
        orig_w = int(candidate['width'])
        orig_h = int(candidate['height'])
        cand_w = max(220, int(orig_w * scale))
        cand_h = max(140, int(orig_h * scale))
        safe_x = max(18, int(w * 0.035))
        safe_y = max(18, int(h * 0.04))

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

    def _render_preview(self, frame, candidates: List[Dict]) -> str:
        canvas = frame.copy()
        colors = {
            'A': (80, 180, 255),
            'B': (120, 220, 140),
            'C': (255, 190, 90),
            'D': (210, 145, 255),
        }
        for cand in candidates:
            label = cand['label']
            x, y, w, h = cand['x'], cand['y'], cand['width'], cand['height']
            color = colors.get(label, (255, 255, 255))
            cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 4)
            cv2.rectangle(canvas, (x, max(0, y - 34)), (x + 46, y), color, -1)
            cv2.putText(canvas, label, (x + 12, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2, cv2.LINE_AA)
        fd, path = tempfile.mkstemp(suffix='.jpg', prefix='placement_preview_')
        os.close(fd)
        cv2.imwrite(path, canvas)
        return path
