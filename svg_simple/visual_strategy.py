"""
Visual Strategy (Simple Mode) — Context Distillation + Semantic Alignment + Visual Type Classification
==========================================================================================

Core responsibility: Take raw video context (scene_context, layout_context, region_context)
and subtitle text, produce a structured design_brief that ensures:
1. SVG content matches the video scene semantically
2. Colors/style blend with the video frame
3. Layout and animation are appropriate for the content
4. visual_type is correctly identified for type-specific SVG generation

Uses 1 LLM call to do all of the above.
"""

import os
import sys
from typing import Dict, Any, Optional
import json

# Ensure custom_chat_model is importable
sys.path.insert(0, os.path.dirname(__file__))
from custom_chat_model import CustomChatModel

# Valid SVG visual types
VISUAL_TYPES = ["data_chart", "flowchart", "concept_map", "comparison", "hierarchy", "timeline", "creative"]


class VisualStrategy:
    """Context distillation + semantic alignment + visual type routing."""

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
            Structured design_brief dict with visual_type
        """
        layout_context = layout_context or {}
        scene_context = scene_context or {}

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
                    design_guide.get("recommended_bg", "#0d1117"))
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
        bg_opacity = region_ctx.get("svg_bg_opacity",
                    region_ctx.get("recommended_svg_opacity", 0.92))
        
        if isinstance(bg_opacity, (int, float)):
            bg_opacity = max(0.75, min(0.98, float(bg_opacity)))

        if isinstance(region_brightness, (int, float)) and region_brightness < 30:
            bg_color = "#1e293b"

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
            visual_description=visual_description,
        )

        # ── 3. LLM call — distill + align + classify type ─────────
        try:
            brief = self._llm_create_brief(text_input, context_block)
        except Exception as e:
            print(f"  [VisualStrategy] LLM failed: {e}, using fallback")
            brief = self._fallback_brief(text_input)

        # ── 4. Validate visual_type ─────────────────────────────────
        vtype = brief.get("visual_type", "concept_map")
        if vtype not in VISUAL_TYPES:
            brief["visual_type"] = "concept_map"

        # ── 5. Inject hard color values ────────────────────────────
        brief["color_instructions"] = {
            "background": bg_color,
            "primary_accent": accent_color,
            "secondary_accent": secondary_color,
            "text": text_color,
            "bg_opacity": bg_opacity,
            "region_brightness": region_brightness,
            "region_type": region_type,
        }

        print(f"    ✓ Visual type: {brief.get('visual_type', 'N/A')}")
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

        brightness = kwargs.get("region_brightness", 50)
        if brightness < 80:
            lines.append(f"Background: DARK (brightness={brightness}), use light text and accents")
        elif brightness > 180:
            lines.append(f"Background: BRIGHT (brightness={brightness}), use dark text and subtle colors")
        else:
            lines.append(f"Background: MEDIUM (brightness={brightness}), use moderate contrast")

        rtype = kwargs.get("region_type", "solid")
        if rtype == "complex":
            lines.append("Region is COMPLEX/BUSY — use higher opacity background, keep SVG simple")
        elif rtype == "gradient":
            lines.append("Region has GRADIENT — use semi-transparent background")
        else:
            lines.append("Region is CLEAN/SOLID — can use lower opacity, more visual detail")

        lines.append(f"Available colors: bg={kwargs.get('bg_color')}, "
                     f"primary={kwargs.get('accent_color')}, "
                     f"secondary={kwargs.get('secondary_color')}, "
                     f"text={kwargs.get('text_color')}")

        return "\\n".join(lines)

    def _llm_create_brief(self, text_input: str, context_block: str) -> Dict:
        self._ensure_llm()
        from langchain_core.messages import SystemMessage, HumanMessage

        system_prompt = """You are a Visual Strategy Director for educational video overlays.

Your job: Take raw subtitle text + video scene context, and produce a structured design brief for an SVG illustrator.

═══════════════════════════════════════════════════════
 STEP 1: DETERMINE visual_type
═══════════════════════════════════════════════════════
Identify the best structure for the content. MUST be one of:
[ data_chart | flowchart | concept_map | comparison | hierarchy | timeline | creative ]

Use your best judgment to select the type that makes the information clearest. If unsure, choose 'creative'.

═══════════════════════════════════════════════════════
 STEP 2: EXTRACT CONTENT & ALIGN WITH SCENE
═══════════════════════════════════════════════════════
CRITICAL RULES:
1. SEMANTIC ALIGNMENT: The SVG MUST illustrate the subtitle content.
2. SCENE MATCHING: Match illustration style to video scene type.
3. CONTENT EXTRACTION: Find the ONE key concept worth visualizing.

═══════════════════════════════════════════════════════
 OUTPUT FORMAT (JSON ONLY)
═══════════════════════════════════════════════════════
Your response must be a valid JSON object. Do not include markdown blocks.

{
  "visual_type": "Selected type from the list above",
  "core_topic": "One clear sentence describing what to visualize",

  "display_title": "1-5 words punchy title",
  "display_subtitle": "1 concise sentence explaining the core point",
  
  "entities": [
    {"label": "Name", "icon_hint": "What to draw, e.g. 'geometric nodes'"}
  ],
  "style_directive": "Art direction: line weight, shape style, aesthetic",
  "animation_plan": "What SVG animations to use and why",
  "scene_alignment": "How this style matches the video scene context",
  "warnings": ["Things to avoid based on scene/context"],

  "custom_data": {
    "// NOTE": "Add any additional highly structured fields here that are relevant to the chosen visual_type.",
    "// Examples (do not copy exactly, just generate what makes sense)": "steps for flowchart, relationships for concept map, comparison_dimensions for comparison, variables for formulas, etc."
  }
}
"""

        prompt = f"""Create a design brief for this SVG overlay.

SUBTITLE TEXT:
"{text_input}"

{context_block}

IMPORTANT: First decide the visual_type, then extract the appropriate structured data into the 'custom_data' schema.
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
        if not parsed.get("entities"):
            parsed["entities"] = [{"label": "Concept", "icon_hint": "abstract diagram"}]
        if not parsed.get("style_directive"):
            parsed["style_directive"] = "Clean style"
        if not parsed.get("animation_plan"):
            parsed["animation_plan"] = "Sequential fadeIn"

        return parsed

    # ================================================================
    #  Fallback
    # ================================================================

    def _fallback_brief(self, text_input: str) -> Dict:
        """Fallback when LLM is unavailable."""
        words = text_input.split()
        stop_words = {
            "the", "is", "are", "was", "and", "but", "or", "this", "that",
            "with", "for", "from", "not", "can", "will", "has", "have",
            "about", "into", "what", "when", "how", "why", "also", "very",
        }
        entities = [
            w.strip(".,;:!?\"'")
            for w in words
            if len(w) > 3 and w.lower() not in stop_words
        ][:5]

        return {
            "visual_type": "creative",
            "core_topic": text_input[:80],
            "entities": [
                {"label": e, "icon_hint": "simple labeled box"}
                for e in entities
            ],
            "custom_data": {},
            "scene_alignment": "general educational diagram",
            "style_directive": "fallback clean lines",
            "animation_plan": "basic fade in",
        }
