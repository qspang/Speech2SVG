"""
Visual Critic
=============

Use a vision-capable LLM to score a rendered SVG overlay and provide
actionable refinement suggestions.
"""

import json
import os
import tempfile
from typing import Any, Dict, Optional

from langchain_core.messages import SystemMessage

from custom_chat_model import CustomChatModel


class VisualCritic:
    """Score the rendered SVG from multiple dimensions with a vision LLM."""

    def __init__(self, vision_llm_type: str = "glm-4.6v"):
        self.vision_llm_type = vision_llm_type or "glm-4.6v"
        self.llm = CustomChatModel(llm_type=self.vision_llm_type, temperature=0.2)

    def evaluate(
        self,
        svg_content: str,
        subtitle_text: str,
        design_brief: Optional[Dict[str, Any]] = None,
        sample_id: str = "svg_output",
    ) -> Dict[str, Any]:
        if not self.llm.supports_vision():
            return self._fallback_report("vision_model_unavailable")

        render = self._render_svg_to_png(svg_content, sample_id)
        if not render.get("ok"):
            return self._fallback_report(f"render_failed:{render.get('error')}")

        image_path = render["image_path"]
        try:
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(subtitle_text, design_brief or {})
            messages = [
                SystemMessage(content=system_prompt),
                self.llm.create_vision_message(user_prompt, image_path),
            ]
            result = self.llm._generate(messages)
            content = result.generations[0].message.content
            parsed = self.llm.parse_json_response(content)
            report = self._normalize_report(parsed, raw_response=content)
            return report
        except Exception as e:
            return self._fallback_report(f"critic_exception:{e}")
        finally:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)

    def _render_svg_to_png(self, svg_content: str, sample_id: str) -> Dict[str, Any]:
        try:
            import cairosvg

            with tempfile.NamedTemporaryFile(
                suffix=f"_{sample_id}.png",
                delete=False,
            ) as f:
                png_path = f.name
            cairosvg.svg2png(bytestring=svg_content.encode("utf-8"), write_to=png_path)
            return {"ok": True, "image_path": png_path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _build_system_prompt(self) -> str:
        return """You are a strict visual critic for educational SVG video overlays.

Your job is to evaluate a rendered SVG overlay image against the subtitle meaning.
Score from 0.0 to 10.0 on exactly these five dimensions:
1. clarity_readability
2. semantic_consistency
3. composition_balance
4. small_overlay_suitability
5. visual_emphasis_aesthetics

Definitions:
- clarity_readability: text legibility, visual separation, immediate comprehensibility
- semantic_consistency: whether the graphic actually matches the subtitle meaning
- composition_balance: use of canvas, spacing, focal balance, not cramped or awkward
- small_overlay_suitability: whether it remains understandable when reduced in a video corner
- visual_emphasis_aesthetics: hierarchy, emphasis, polish, tasteful motion/shape choices

Rules:
- Be strict.
- Always provide specific improvement suggestions, even if the score is high.
- Prefer concrete actionable feedback over vague praise.
- Return JSON only.

JSON schema:
{
  "scores": {
    "clarity_readability": 0.0,
    "semantic_consistency": 0.0,
    "composition_balance": 0.0,
    "small_overlay_suitability": 0.0,
    "visual_emphasis_aesthetics": 0.0
  },
  "average_score": 0.0,
  "strengths": ["..."],
  "issues": ["..."],
  "improvement_suggestions": ["...", "..."],
  "summary": "one concise paragraph"
}"""

    def _build_user_prompt(self, subtitle_text: str, design_brief: Dict[str, Any]) -> str:
        payload = {
            "subtitle_text": subtitle_text,
            "core_topic": design_brief.get("core_topic", ""),
            "display_title": design_brief.get("display_title", ""),
            "display_subtitle": design_brief.get("display_subtitle", ""),
            "key_elements": design_brief.get("key_elements", []),
            "layout_concept": design_brief.get("layout_concept", ""),
            "animation_intent": design_brief.get("animation_intent", ""),
        }
        return (
            "Please score this rendered SVG overlay for an educational video.\n"
            "Pay special attention to whether the image matches the subtitle meaning and whether it would remain clear in a small overlay.\n"
            f"Context JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _normalize_report(self, parsed: Any, raw_response: str = "") -> Dict[str, Any]:
        if not isinstance(parsed, dict):
            return self._fallback_report("invalid_json", raw_response=raw_response)

        scores = parsed.get("scores", {}) if isinstance(parsed.get("scores"), dict) else {}
        dims = [
            "clarity_readability",
            "semantic_consistency",
            "composition_balance",
            "small_overlay_suitability",
            "visual_emphasis_aesthetics",
        ]
        normalized_scores = {}
        for dim in dims:
            try:
                value = float(scores.get(dim, 0.0))
            except Exception:
                value = 0.0
            normalized_scores[dim] = round(max(0.0, min(10.0, value)), 2)

        if any(normalized_scores.values()):
            average = round(sum(normalized_scores.values()) / len(dims), 2)
        else:
            try:
                average = round(float(parsed.get("average_score", 0.0)), 2)
            except Exception:
                average = 0.0

        return {
            "ok": True,
            "scores": normalized_scores,
            "average_score": average,
            "strengths": self._coerce_list(parsed.get("strengths")),
            "issues": self._coerce_list(parsed.get("issues")),
            "improvement_suggestions": self._coerce_list(parsed.get("improvement_suggestions")),
            "summary": str(parsed.get("summary", "")).strip(),
            "raw_response": raw_response,
        }

    def _coerce_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _fallback_report(self, reason: str, raw_response: str = "") -> Dict[str, Any]:
        return {
            "ok": False,
            "scores": {
                "clarity_readability": 0.0,
                "semantic_consistency": 0.0,
                "composition_balance": 0.0,
                "small_overlay_suitability": 0.0,
                "visual_emphasis_aesthetics": 0.0,
            },
            "average_score": 0.0,
            "strengths": [],
            "issues": [reason],
            "improvement_suggestions": ["Improve readability, semantic match, composition balance, and small-overlay clarity."],
            "summary": reason,
            "raw_response": raw_response,
        }
