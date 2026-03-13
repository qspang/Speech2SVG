"""
SVG Generator (Simple Mode) — Fluid, Creative generation directly from Design Brief
=================================================================================

Takes a structured design_brief (from VisualStrategy) and generates arbitrary, 
imaginative SVG code honoring the user's base stylistic limits.

Canvas: 1920×1080
"""

import os
import sys
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(__file__))
from custom_chat_model import CustomChatModel

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class SVGGenerator:
    """Generate generic, creative SVG code from a VisualStrategy design brief without template handcuffs."""

    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        self.llm_type = llm_type
        self.llm = None

    def _ensure_llm(self):
        if self.llm is None:
            self.llm = CustomChatModel(llm_type=self.llm_type, temperature=0.7)  # Higher temperature for simple mode

    def generate(self, design_brief: Dict[str, Any]) -> str:
        """Generate SVG code from a design_brief."""
        try:
            svg = self._llm_generate(design_brief)
        except Exception as e:
            print(f"  [SVGGenerator] LLM failed: {e}, using fallback")
            svg = self._fallback_svg(design_brief)
        return svg

    # ================================================================
    #  LLM Generation
    # ================================================================

    def _llm_generate(self, brief: Dict) -> str:
        """Build a generic, unrestricted prompt combined with safety rules."""
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

        return f"""You are an Expert SVG Illustrator for educational video overlays.
Canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT} pixels. Output RAW SVG code only — no markdown.

═══ COLOR PALETTE (from video frame — MUST USE) ═══
  Background : {bg}  (opacity: {bg_opacity})
  Primary    : {primary}
  Secondary  : {secondary}
  Text       : {text_c}
  ⚠ Use ALL palette colors. Do NOT use default colors like #0f172a or #1e293b.

═══ CSS SAFETY RULES ═══
1. NEVER set opacity: 0 in a CSS class body. Only in @keyframes from {{ }}.
2. Use NESTED <g> — outer for position, inner for animation:
   <g transform="translate(X,Y)"><g class="anim">…</g></g>
3. Always: .anim {{ opacity:1; animation: fadeIn 0.8s ease-out; }}
   @keyframes fadeIn {{ from {{ opacity:0 }} to {{ opacity:1 }} }}
4. NEVER put transform (translateX, translateY, translate) in @keyframes.
   CSS transform OVERRIDES SVG transform="translate()", making elements jump to (0,0).
   Only use opacity in @keyframes. For scale, set transform-origin on the element.
5. NEVER use <animateMotion>. It causes elements to render at (0,0) before animation starts.
6. Ensure all @keyframes blocks have properly matched curly braces {{ }}.

═══ CANVAS RULES ═══
- Safe zone: X 150–1770, Y 120–960
- Center: (960, 540)
- Start SVG with:
  <svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
- ⚠ CRITICAL: DO NOT DRAW ANY BACKGROUND <rect>. The SVG must be completely TRANSPARENT so it acts as an overlay on the video.
- ⚠ CRITICAL: DO NOT use solid black/dark boxes. Rely on glowing strokes, bold text, and transparent gradients to create a cinematic holographic effect.
- You can include a glowing filter in <defs> to make elements pop on video:
  <defs><filter id="glow"><feGaussianBlur stdDeviation="8" result="blur" /><feComposite in="SourceGraphic" in2="blur" operator="over"/></filter></defs>

═══ ⚠ CRITICAL FULL-CANVAS LAYOUT RULE ═══
You MUST spread content across the ENTIRE 1920×1080 canvas. NEVER cluster everything in one corner.
- Title: center-aligned at approximately x=960, y=100-140
- Main content: distribute across the full width x=200 to x=1700
- Vertical spread: use y=150 to y=950 — do NOT leave bottom half empty
- If you have 3+ entities, spread them across the canvas width evenly
- If you have a central element, place it near (960, 500), not (300, 400)
- MINIMUM occupied area: at least 70% of the 1920×1080 space must contain visual elements
- WRONG: everything in x=100-600 (wastes right 2/3 of canvas)
- RIGHT: elements span from x=200 to x=1700 with balanced spacing

═══ MINIMUM SIZE RULES (1920×1080 canvas) ═══
⚠ VERY IMPORTANT: The SVG will be scaled down when overlaid on the video. ALL TEXT MUST BE MASSIVE.
- Title text: font-size >= 60px, font-weight >= 800
- Subtitle text: font-size >= 45px
- Body text / labels / data values: font-size >= 32px (NEVER use 16px, 12px or 10px — they will be invisible!)
- Entity icons: minimum 120×120px bounding box
- Cards / boxes: minimum width 400px, minimum height 120px
- Central element (e.g. VS circle): minimum radius 80px or 150×150px
- Stroke widths: minimum 3px to 5px (thin 1px lines will disappear)"""

    def _build_user_prompt(self, brief: Dict) -> str:
        """Feed the entire design brief directly to the LLM and tell it to create."""
        import json
        
        brief_copy = brief.copy()
        brief_copy.pop("color_instructions", None)
        
        formatted_brief = json.dumps(brief_copy, indent=2, ensure_ascii=False)

        return f"""Here is the structured design brief for the SVG overlay:

{formatted_brief}

YOUR INSTRUCTIONS:
Using the rules specified above, create a highly polished, fully animated SVG illustration that flawlessly matches the design brief.
Do not rely on predefined rigid templates—use your creativity to draw something beautiful and conceptually accurate for the visual_type '{brief.get("visual_type")}'. 
Include SVG animations as detailed in the 'animation_plan'.
Remember you are building an overlay for a video, so it MUST be transparent (no giant background rect).

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
