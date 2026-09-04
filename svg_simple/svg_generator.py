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
        print(f"  [SVGGenerator] Raw response chars: {len(content)}")
        preview = content[:400].replace("\n", "\\n")
        print(f"  [SVGGenerator] Raw response preview: {preview}")
        svg = self._extract_svg(content)
        print(f"  [SVGGenerator] Extracted SVG chars: {len(svg)}")
        if "<svg" not in svg.lower() or "</svg>" not in svg.lower():
            raise ValueError(f"Model did not return valid SVG. Preview: {preview}")
        return svg

    # ════════════════════════════════════════════════════════════════
    #  SYSTEM PROMPT — Base Safety Rules Only
    # ════════════════════════════════════════════════════════════════

    def _build_system_prompt(self, brief: Dict) -> str:
        colors = brief.get("color_instructions", {})
        bg = colors.get("background", "none")
        primary = colors.get("primary_accent", "#58a6ff")
        secondary = colors.get("secondary_accent", "#64ffda")
        border_c = colors.get("border", "none")
        text_c = colors.get("text", "#e6edf3")
        bg_opacity = colors.get("bg_opacity", 0.0)
        svg_mode = brief.get("svg_mode", "static")
        animation_intent = brief.get("animation_intent", "light")
        target_render = brief.get("target_render", {})
        target_w = int(target_render.get("width", 640) or 640)
        target_h = int(target_render.get("height", 360) or 360)
        min_title_font = int(target_render.get("min_title_font", 120) or 120)
        min_body_font = int(target_render.get("min_body_font", 96) or 96)
        title_font = min_title_font
        body_font = min_body_font

        return f"""You are an Expert SVG Illustrator for educational video overlays.
Canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT} pixels. Output RAW SVG code only — no markdown.
This SVG will be rendered inside an on-video overlay roughly {target_w}x{target_h}px, so readability at small display size is critical.

Use the LLM's drawing ability. Do NOT reduce everything to generic boxes with single-word labels.

Palette from video frame — MUST USE:
- overlay background: transparent
- primary: {primary}
- secondary: {secondary}
- border: none unless absolutely necessary
- text: {text_c}

Core rules:
1. The SVG must explain the idea, not just decorate the subtitle.
2. Use the full canvas. Avoid cramming content into one corner.
3. Prefer meaningful shapes, spatial composition, visual metaphor, and large legible labels.
4. Design for small on-video display: emphasize one clear main structure, not many tiny details.
5. Use fewer elements when possible. A simpler, bolder composition is better than a dense infographic.
6. Make the main shapes and symbols physically larger on the canvas so the subject reads immediately.
7. Prefer thicker lines, stronger connectors, and sturdier outlines. Avoid hairline strokes and fragile micro-details.
8. Use only TWO font sizes in the whole SVG, and they must be these exact sizes:
   - dominant text: {title_font}px
   - supporting text: {body_font}px
   Do not create a third tiny text tier. Do not use any other font-size values anywhere in the SVG, including labels, legends, ticks, micro annotations, or CSS classes.
4. Every SVG should include animation:
   - if svg_mode is {svg_mode} and animation_intent is {animation_intent}, make animation stronger when explanation benefits from motion
   - otherwise still add subtle animation such as reveal, line-draw, pulse, shimmer, staged emphasis, or orbital/flow accents
9. Avoid random isolated words as node labels. Use meaningful short phrases.
10. Do not output simplistic box-and-arrow filler unless the concept truly requires it.
11. Do NOT draw any full-canvas or nearly full-canvas background rectangle, background panel, dark plate, or tinted overlay behind the composition.

Technical safety:
- Keep the overall SVG background transparent so the video remains visible behind it.
- Choose text, icons, connectors, and graphic entities in colors that remain clearly visible over the local video region.
- Never make important elements nearly the same color as the underlying video area. If uncertain, prefer white or near-white text.
- Use large readable text suitable for video overlay.
- Decide font sizes BEFORE drawing the graphic.
- Title text must use exactly {title_font}px.
- Primary labels and key explanatory text must use exactly {body_font}px.
- There must be no third annotation size in normal cases.
- If the layout becomes crowded, reduce the number of elements or enlarge shapes; do not solve it by making text tiny.
- Make icon/entity sizes and spacing subordinate to text legibility, not the other way around.
- Favor bold silhouette and structural clarity over ornamental detail.
- Use transparent fills or no fill for large background panels unless they are essential to explain the concept.
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
            "font_plan": brief.get("font_plan", ""),
            "target_render": brief.get("target_render", {}),
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
Think through font sizing first, then arrange entities, connectors, and icons around that readable typography.
Keep the SVG background transparent. Do not add a full-screen rect, plate, or background wash.
Text, icons, lines, and other entities must use visible colors so they can still be read on top of the video.
Keep the composition bold and simple enough to stay clear when reduced to a small video overlay.
Use fewer nodes, fewer labels, thicker strokes, and larger primary shapes.
Do not fill the canvas with many tiny details.
Use only two font sizes total, and use these exact values from target_render:
- title/display text = {brief.get("target_render", {}).get("min_title_font", 120)}px
- supporting/body text = {brief.get("target_render", {}).get("min_body_font", 96)}px
Do not add a third tiny caption style, and do not invent extra font-size values in CSS.
Keep text big and the number of labeled items low.

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
