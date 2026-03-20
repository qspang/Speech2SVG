"""
SVG Generator (Simple Mode)
===========================

Primary path: direct LLM-authored SVG code from a compact visual brief.
"""

import os
import sys
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(__file__))
from custom_chat_model import CustomChatModel

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class SVGGenerator:
    """Generate SVG code directly with the LLM; avoid template-first composition."""

    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        self.llm_type = llm_type
        self.llm = None

    def _ensure_llm(self):
        if self.llm is None:
            self.llm = CustomChatModel(llm_type=self.llm_type, temperature=0.65)

    def generate(self, design_brief: Dict[str, Any]) -> str:
        """Generate SVG code from a design_brief."""
        try:
            svg = self._llm_generate(design_brief)
        except Exception as e:
            print(f"  [SVGGenerator] Direct generation failed: {e}, using fallback")
            svg = self._fallback_svg(design_brief)
        return svg

    # ================================================================
    #  LLM Generation
    # ================================================================

    def _llm_generate(self, brief: Dict) -> str:
        """Direct LLM SVG generation from a compact brief."""
        self._ensure_llm()
        from langchain_core.messages import SystemMessage, HumanMessage

        system_prompt = self._build_system_prompt(brief)
        user_prompt = self._build_user_prompt(brief)
        # print("svg generator system prompt:", system_prompt)
        # print("==========================================")
        # print("svg generator user prompt:", user_prompt)
        # print("==========================================")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        result = self.llm._generate(messages)
        content = result.generations[0].message.content
        svg = self._extract_svg(content)
        return svg

    # ════════════════════════════════════════════════════════════════
    #  SYSTEM PROMPT — Base Safety Rules Only
    # ════════════════════════════════════════════════════════════════

    def _build_system_prompt(self, brief: Dict) -> str:
        colors = brief.get("color_instructions", {})
        bg = colors.get("background", "#0d1117")
        primary = colors.get("primary_accent", "#58a6ff")
        secondary = colors.get("secondary_accent", "#64ffda")
        text_c = colors.get("text", "#e6edf3")
        bg_opacity = colors.get("bg_opacity", 0.92)
        svg_mode = brief.get("svg_mode", "static")
        animation_intent = brief.get("animation_intent", "light")

        return f"""You are an Expert SVG Illustrator for educational video overlays.
Canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT} pixels. Output RAW SVG code only — no markdown.

Use the LLM's drawing ability. Do NOT reduce everything to generic boxes with single-word labels.

Palette from video frame — MUST USE:
- background: {bg} (opacity hint {bg_opacity})
- primary: {primary}
- secondary: {secondary}
- text: {text_c}

Core rules:
1. The SVG must explain the idea, not just decorate the subtitle.
2. Use the full canvas. Avoid cramming content into one corner.
3. Prefer meaningful shapes, spatial composition, visual metaphor, and large legible labels.
4. Every SVG should include animation:
   - if svg_mode is {svg_mode} and animation_intent is {animation_intent}, make animation stronger when explanation benefits from motion
   - otherwise still add subtle animation such as reveal, line-draw, pulse, shimmer, staged emphasis, or orbital/flow accents
5. Avoid random isolated words as node labels. Use meaningful short phrases.
6. Do not output simplistic box-and-arrow filler unless the concept truly requires it.

Technical safety:
- Transparent overlay only. Do not draw a full solid background rect.
- Use large readable text suitable for video overlay.
- Avoid CSS translate keyframes that break SVG positioning.
- Prefer opacity, scale, stroke-dashoffset, rotate, cx/cy/x/y, and SVG-native animation.
- You may use animateTransform for rotate/scale.

Output raw SVG only."""

    def _build_user_prompt(self, brief: Dict) -> str:
        """Feed a compact brief directly to the LLM."""
        import json

        payload = {
            "visual_type": brief.get("visual_type", "creative"),
            "core_topic": brief.get("core_topic", ""),
            "display_title": brief.get("display_title", ""),
            "display_subtitle": brief.get("display_subtitle", ""),
            "key_elements": brief.get("key_elements", []),
            "layout_concept": brief.get("layout_concept", ""),
            "style_directive": brief.get("style_directive", ""),
            "animation_intent": brief.get("animation_intent", "light"),
            "animation_notes": brief.get("animation_notes", ""),
            "scene_alignment": brief.get("scene_alignment", ""),
            "visual_hint": brief.get("visual_hint", ""),
        }
        formatted_brief = json.dumps(payload, indent=2, ensure_ascii=False)

        return f"""Here is the structured design brief for the SVG overlay:

{formatted_brief}

YOUR INSTRUCTIONS:
Create a polished SVG that actually visualizes the meaning.
Use composition, iconography, relationships, and motion intentionally.
If the concept benefits from animation, make the animation explanatory.
If not, still add subtle animated life so the graphic never feels completely static.
Avoid generic template-looking results.

Output RAW SVG code only. Start with <svg> and end with </svg>. No markdown formatting blocks."""

    def _extract_svg(self, text: str) -> str:
        if "```svg" in text:
            start = text.find("```svg") + 6
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        
        start = text.find("<svg")
        end = text.rfind("</svg>")
        if start != -1 and end != -1:
            return text[start:end+6].strip()
            
        return text.strip()

    def _fallback_svg(self, brief: Dict) -> str:
        topic = brief.get("core_topic", "Info")[:30]
        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <text x="{CANVAS_WIDTH//2}" y="{CANVAS_HEIGHT//2}" font-size="64" fill="#ffffff" text-anchor="middle">
    Generation Failed: {topic}
  </text>
</svg>'''
