"""
SVG Refine
==========

Refine an existing SVG according to visual critic feedback.
"""

import json
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from custom_chat_model import CustomChatModel


class SVGRefiner:
    """Rewrite SVG using critic feedback while preserving the core idea."""

    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        self.llm_type = llm_type
        self.llm = CustomChatModel(llm_type=self.llm_type, temperature=0.45)

    def refine(
        self,
        svg_content: str,
        design_brief: Dict[str, Any],
        critic_report: Dict[str, Any],
    ) -> str:
        messages = [
            SystemMessage(content=self._build_system_prompt(design_brief)),
            HumanMessage(content=self._build_user_prompt(svg_content, design_brief, critic_report)),
        ]
        result = self.llm._generate(messages)
        content = result.generations[0].message.content
        svg = self._extract_svg(str(content))
        if "<svg" not in svg.lower() or "</svg>" not in svg.lower():
            raise ValueError("SVGRefiner did not return valid SVG")
        return svg

    def _build_system_prompt(self, brief: Dict[str, Any]) -> str:
        target_render = brief.get("target_render", {})
        title_font = int(target_render.get("min_title_font", 120) or 120)
        body_font = int(target_render.get("min_body_font", 96) or 96)
        return f"""You are refining an SVG educational overlay after a visual critique.

Output RAW SVG only.
Keep the overlay background transparent.
Preserve the core meaning, but fix the issues identified by the critic.

Hard rules:
- Use the full canvas more effectively when needed.
- Keep the composition bold and suitable for a small video overlay.
- Keep the number of entities limited if the image is too dense.
- Use only two font sizes total:
  - dominant text: {title_font}px
  - supporting text: {body_font}px
- Do not introduce a third tiny text tier.
- Do not add a full-canvas background plate.
- Improve clarity first, aesthetics second."""

    def _build_user_prompt(
        self,
        svg_content: str,
        design_brief: Dict[str, Any],
        critic_report: Dict[str, Any],
    ) -> str:
        payload = {
            "design_brief": {
                "core_topic": design_brief.get("core_topic", ""),
                "display_title": design_brief.get("display_title", ""),
                "display_subtitle": design_brief.get("display_subtitle", ""),
                "key_elements": design_brief.get("key_elements", []),
                "layout_concept": design_brief.get("layout_concept", ""),
                "target_render": design_brief.get("target_render", {}),
            },
            "critic_report": {
                "scores": critic_report.get("scores", {}),
                "average_score": critic_report.get("average_score", 0.0),
                "issues": critic_report.get("issues", []),
                "improvement_suggestions": critic_report.get("improvement_suggestions", []),
                "summary": critic_report.get("summary", ""),
            },
        }
        return (
            "Refine the following SVG according to the critic feedback.\n"
            "Preserve the semantic meaning, but make the visual result clearer and better balanced.\n\n"
            f"Context JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"Original SVG:\n{svg_content}"
        )

    def _extract_svg(self, text: str) -> str:
        if "```svg" in text:
            start = text.find("```svg") + 6
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        start = text.find("<svg")
        end = text.rfind("</svg>")
        if start != -1 and end != -1:
            return text[start:end + 6].strip()
        return text.strip()
