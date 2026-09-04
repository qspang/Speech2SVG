"""
Visual Strategy (Simple Mode)
=============================

Generate a compact, LLM-friendly design brief for direct SVG code generation.
"""

import os
import sys
from typing import Dict, Any, Optional
import json

# Ensure custom_chat_model is importable
sys.path.insert(0, os.path.dirname(__file__))
from custom_chat_model import CustomChatModel

VISUAL_TYPES = ["data_chart", "flowchart", "concept_map", "comparison", "hierarchy", "timeline", "creative"]


class VisualStrategy:
    """Build a lightweight visual brief instead of a template-oriented motion spec."""

    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        self.llm_type = llm_type
        self.llm = None

    def _ensure_llm(self):
        if self.llm is None:
            self.llm = CustomChatModel(llm_type=self.llm_type, temperature=0.4)

    def create_design_brief(
        self,
        text_input: str,
        layout_context: Optional[Dict] = None,
        scene_context: Optional[Dict] = None,
        motion_context: Optional[Dict] = None,
        visual_description: str = "",
    ) -> Dict[str, Any]:
        """
        Distill all video context into a structured design brief.

        Args:
            text_input: Subtitle text to visualize
            layout_context: {width, height, position, region_context}
            scene_context: {design_guide, color_palette, ...}
            visual_description: Visual hint from decision_agent

        Returns:
            Lightweight design_brief dict for direct LLM SVG generation
        """
        layout_context = layout_context or {}
        scene_context = scene_context or {}
        motion_context = motion_context or {}

        # print("==========================================")
        # print("layout_context:")
        # try:
        #     print(json.dumps(layout_context, indent=4, ensure_ascii=False))
        # except Exception:
        #     print(layout_context)

        # print("==========================================")
        # print("scene_context:")
        # try:
        #     print(json.dumps(scene_context, indent=4, ensure_ascii=False))
        # except Exception:
        #     print(scene_context)

        # print("==========================================")

        # ── 1. Extract raw context ──────────────────────────────────
        region_ctx = layout_context.get("region_context", {})
        design_guide = scene_context.get("design_guide", {})

        # Colors — base values from scene_agent design_guide
        bg_color = region_ctx.get("region_bg_color",
                    design_guide.get("recommended_bg", "none"))
        accent_color = design_guide.get("recommended_accent", "#58a6ff")
        text_color = region_ctx.get("contrast_text_color",
                     design_guide.get("recommended_text", "#e6edf3"))
        secondary_color = design_guide.get("recommended_secondary", "#64ffda")

        # Region info
        raw_brightness = region_ctx.get("region_brightness", 50)
        if isinstance(raw_brightness, (int, float)):
            region_brightness = raw_brightness
        else:
            region_brightness = region_ctx.get("region_brightness_value",
                {"dark": 40, "medium": 128, "bright": 200}.get(str(raw_brightness), 50))
        region_type = region_ctx.get("region_type", "solid")
        bg_opacity = 0.0

        frame_count = scene_context.get("frame_count", 0)
        is_scene_fallback = (accent_color == "#3498db" and frame_count == 0)
        
        region_colors = region_ctx.get("region_colors", [])
        if is_scene_fallback and len(region_colors) >= 2:
            best_accent = None
            best_saturation = 0
            for rc in region_colors[1:]:
                sat = self._hex_saturation(rc)
                if sat > best_saturation:
                    best_saturation = sat
                    best_accent = rc
            if best_accent and best_saturation > 0.15:
                accent_color = best_accent
                print(f"    [VisualStrategy] Using region accent: {accent_color} (sat={best_saturation:.2f})")
            else:
                accent_color = "#7c3aed"
                secondary_color = "#06b6d4"
                print(f"    [VisualStrategy] Region has no vibrant colors, using default palette")

        svg_prompt = design_guide.get("svg_prompt", "")
        scene_description = design_guide.get("scene_description", "")
        position = layout_context.get("position", "center")
        target_width = int(layout_context.get("width", 640) or 640)
        target_height = int(layout_context.get("height", 360) or 360)
        min_title_font = max(88, min(132, int(target_width * 0.145)))
        min_body_font = max(56, min(84, int(target_width * 0.090)))
        min_caption_font = min_body_font

        # ── 2. Build context summary for LLM ───────────────────────
        context_block = self._build_context_block(
            bg_color=bg_color,
            accent_color=accent_color,
            secondary_color=secondary_color,
            text_color=text_color,
            region_brightness=region_brightness,
            region_type=region_type,
            bg_opacity=bg_opacity,
            svg_prompt=svg_prompt,
            scene_description=scene_description,
            position=position,
            target_width=target_width,
            target_height=target_height,
            min_title_font=min_title_font,
            min_body_font=min_body_font,
            min_caption_font=min_caption_font,
            motion_context=motion_context,
            visual_description=visual_description,
        )

        # ── 3. LLM call — distill + align + classify type ─────────
        try:
            brief = self._llm_create_brief(text_input, context_block, motion_context=motion_context)
        except Exception as e:
            print(f"  [VisualStrategy] LLM failed: {e}, using fallback")
            brief = self._fallback_brief(text_input)

        # ── 4. Validate / normalize ────────────────────────────────
        vtype = brief.get("visual_type", "concept_map")
        if vtype not in VISUAL_TYPES:
            brief["visual_type"] = "creative"

        # ── 5. Inject hard color values ────────────────────────────
        brief["color_instructions"] = {
            "background": "none",
            "border": "none",
            "primary_accent": accent_color,
            "secondary_accent": secondary_color,
            "text": text_color,
            "bg_opacity": bg_opacity,
            "region_brightness": region_brightness,
            "region_type": region_type,
        }
        brief["target_render"] = {
            "width": target_width,
            "height": target_height,
            "min_title_font": min_title_font,
            "min_body_font": min_body_font,
            "min_caption_font": min_caption_font,
        }

        print(f"    ✓ Visual type: {brief.get('visual_type', 'N/A')}")
        print(f"    ✓ SVG mode: {brief.get('svg_mode', 'static')}")
        print(f"    ✓ Colors → bg={bg_color} accent={accent_color} secondary={secondary_color}")
        return brief

    @staticmethod
    def _hex_saturation(hex_color: str) -> float:
        try:
            hex_color = hex_color.lstrip("#")
            r, g, b = int(hex_color[0:2], 16) / 255, int(hex_color[2:4], 16) / 255, int(hex_color[4:6], 16) / 255
            cmax, cmin = max(r, g, b), min(r, g, b)
            delta = cmax - cmin
            if delta == 0:
                return 0.0
            l = (cmax + cmin) / 2
            return delta / (1 - abs(2 * l - 1))
        except Exception:
            return 0.0

    # ================================================================
    #  LLM Prompt
    # ================================================================

    def _build_context_block(self, **kwargs) -> str:
        lines = []
        lines.append("=== VIDEO SCENE CONTEXT ===")

        if kwargs.get("scene_description"):
            lines.append(f"Scene: {kwargs['scene_description']}")
        if kwargs.get("svg_prompt"):
            lines.append(f"Style guidance: {kwargs['svg_prompt']}")
        if kwargs.get("visual_description"):
            lines.append(f"Visual hint from classifier: {kwargs['visual_description']}")
        motion_ctx = kwargs.get("motion_context", {}) or {}
        if motion_ctx:
            lines.append(
                "Animation routing hint: "
                f"mode={motion_ctx.get('svg_mode_hint', 'none')}, "
                f"worth={motion_ctx.get('motion_worthiness', 0.0)}, "
                f"grammar={motion_ctx.get('motion_grammar_hint', 'none')}"
            )
            if motion_ctx.get("animation_reason"):
                lines.append(f"Animation reason: {motion_ctx.get('animation_reason')}")

        brightness = kwargs.get("region_brightness", 50)
        if brightness < 80:
            lines.append(f"Background: DARK (brightness={brightness}), use light text and accents")
        elif brightness > 180:
            lines.append(f"Background: BRIGHT (brightness={brightness}), use dark text and subtle colors")
        else:
            lines.append(f"Background: MEDIUM (brightness={brightness}), use moderate contrast")

        rtype = kwargs.get("region_type", "solid")
        if rtype == "complex":
            lines.append("Region is COMPLEX/BUSY — keep SVG simple and rely on visible text/icon colors instead of a background plate")
        elif rtype == "gradient":
            lines.append("Region has GRADIENT — maintain transparency and use stable high-contrast text/icon colors")
        else:
            lines.append("Region is CLEAN/SOLID — keep the background transparent and focus on clear colored entities")

        lines.append(f"Available colors: bg={kwargs.get('bg_color')}, "
                     f"primary={kwargs.get('accent_color')}, "
                     f"secondary={kwargs.get('secondary_color')}, "
                     f"text={kwargs.get('text_color')}")
        lines.append(
            "Target render region: "
            f"{kwargs.get('target_width')}x{kwargs.get('target_height')} px; "
            f"title >= {kwargs.get('min_title_font')} px, "
            f"supporting text >= {kwargs.get('min_body_font')} px. "
            f"Use only two font scales total."
        )

        return "\\n".join(lines)

    def _llm_create_brief(self, text_input: str, context_block: str, motion_context: Optional[Dict] = None) -> Dict:
        self._ensure_llm()
        from langchain_core.messages import SystemMessage, HumanMessage
        motion_context = motion_context or {}

        system_prompt = """You are a visual brief writer for educational SVG overlays.

Write a SHORT, useful design brief for an LLM that will directly author the SVG code.

Goals:
1. Capture the actual meaning of the subtitle, not isolated words.
2. Suggest a strong visual composition that explains the idea clearly.
3. Encourage animation when it helps, but keep even static-style graphics slightly animated.
4. Avoid generic box-and-arrow filler unless the content truly needs it.

Return JSON only with this schema:
{
  "visual_type": "data_chart | flowchart | concept_map | comparison | hierarchy | timeline | creative",
  "core_topic": "one clear sentence",
  "display_title": "short title, ideally under 6 words",
  "display_subtitle": "one concise explanatory sentence",
  "key_elements": ["2-5 meaningful visual elements or concepts"],
  "layout_concept": "how the composition should be arranged on canvas",
  "style_directive": "art direction in one sentence",
  "animation_intent": "high | light",
  "animation_notes": "what should move, reveal, pulse, orbit, flow, or shimmer",
  "scene_alignment": "how it should blend with the video scene",
  "font_plan": "how large the title and supporting text should be using only two font sizes"
}
"""

        prompt = f"""Create a design brief for this SVG overlay.

SUBTITLE TEXT:
"{text_input}"

{context_block}

IMPORTANT:
- Do not just extract random words from the subtitle.
- key_elements must be meaningful concepts, objects, stages, or entities.
- The SVG will be scaled down into a video overlay, so decide the font sizes first and keep them large.
- Use only two font sizes total: one dominant size and one supporting size.
- Do not create a third tiny annotation tier.
- If text becomes too small, reduce the number of elements instead of shrinking fonts below readable size.
- If the segment is suitable for strong explanatory animation, set animation_intent to "high".
- Otherwise set animation_intent to "light" and still suggest subtle motion.
- Prefer a clean, expressive composition over generic labeled boxes.
Return JSON only."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]

        # print("==========================================")
        # try:
        #     if isinstance(prompt, (dict, list)):
        #         pretty_json = json.dumps(prompt, indent=4, ensure_ascii=False)
        #         print("visual strategy prompt (JSON Format):")
        #         # print(pretty_json)
        #     elif isinstance(prompt, str):
        #         try:
        #             parsed_json = json.loads(prompt)
        #             pretty_json = json.dumps(parsed_json, indent=4, ensure_ascii=False)
        #             print("visual strategy prompt (String -> 解析并格式化为 JSON):")
        #             print(pretty_json)
        #         except json.JSONDecodeError:
        #             print(prompt)
        #     else:
        #         print(prompt)
        # except Exception:
        #     print(prompt)
        # print("==========================================")

        result = self.llm._generate(messages)
        content = result.generations[0].message.content
        parsed = self.llm.parse_json_response(content)

        # print("==========================================")
        # try:
        #     if isinstance(parsed, (dict, list)):
        #         pretty_json = json.dumps(parsed, indent=4, ensure_ascii=False)
        #         print("visual strategy result (JSON Format):")
        #         # print(pretty_json)
        #     else:
        #         print("visual strategy result (Raw string):")
        #         # print(parsed)
        # except Exception:
        #     print(parsed)
        # print("==========================================")

        # Validate minimum structure
        if not parsed.get("core_topic"):
            parsed["core_topic"] = text_input[:80]
        if not parsed.get("visual_type"):
            parsed["visual_type"] = "creative"
        if not parsed.get("key_elements"):
            parsed["key_elements"] = self._extract_key_elements(text_input)
        if not parsed.get("layout_concept"):
            parsed["layout_concept"] = "Use a balanced full-canvas composition with a clear visual focal point."
        if not parsed.get("style_directive"):
            parsed["style_directive"] = "Clean style"
        if not parsed.get("animation_notes"):
            parsed["animation_notes"] = "Add subtle reveal, pulse, or line-draw motion to keep the SVG alive."
        if parsed.get("animation_intent") not in ("high", "light"):
            parsed["animation_intent"] = "light"
        if not parsed.get("scene_alignment"):
            parsed["scene_alignment"] = "Blend with the frame colors while preserving strong readability."
        if not parsed.get("font_plan"):
            parsed["font_plan"] = "Use only two font sizes: a dominant title size and a large supporting size. Avoid tiny annotations."

        key_elements = parsed.get("key_elements", [])
        if isinstance(key_elements, list):
            parsed["key_elements"] = [str(item).strip()[:40] for item in key_elements if str(item).strip()][:5]
        else:
            parsed["key_elements"] = self._extract_key_elements(text_input)

        hint_mode = motion_context.get("svg_mode_hint", "none") if isinstance(motion_context, dict) else "none"
        hint_score = float(motion_context.get("motion_worthiness", 0.0)) if isinstance(motion_context, dict) else 0.0
        if hint_mode == "animated_svg" or hint_score >= 0.6:
            parsed["svg_mode"] = "animated_explanatory"
            parsed["animation_intent"] = "high"
        else:
            parsed["svg_mode"] = "static"

        return parsed

    def _extract_key_elements(self, text_input: str):
        words = text_input.split()
        stop_words = {
            "the", "is", "are", "was", "and", "but", "or", "this", "that",
            "with", "for", "from", "not", "can", "will", "has", "have",
            "about", "into", "what", "when", "how", "why", "also", "very",
            "they", "them", "where", "there", "like", "good", "just",
        }
        elements = []
        for word in words:
            clean = word.strip(".,;:!?\"'()[]{}")
            if len(clean) <= 3 or clean.lower() in stop_words:
                continue
            elements.append(clean)
            if len(elements) >= 4:
                break
        return elements or ["Core idea", "Key relation"]

    # ================================================================
    #  Fallback
    # ================================================================

    def _fallback_brief(self, text_input: str) -> Dict:
        """Fallback when LLM is unavailable."""
        return {
            "visual_type": "creative",
            "core_topic": text_input[:80],
            "display_title": text_input[:28],
            "display_subtitle": text_input[:80],
            "key_elements": self._extract_key_elements(text_input),
            "layout_concept": "Use a balanced composition with one focal visual and supporting elements around it.",
            "scene_alignment": "general educational diagram",
            "style_directive": "fallback clean lines",
            "animation_intent": "light",
            "animation_notes": "Add subtle fade-in, line-draw, and pulse motion.",
            "svg_mode": "static",
            "font_plan": "Use only two font sizes: a dominant title size and a large supporting size.",
        }
