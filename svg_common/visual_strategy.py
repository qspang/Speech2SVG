"""
Visual Strategy — Context Distillation + Semantic Alignment + Visual Type Classification
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

def print_pretty_json(data):
    try:
        if isinstance(data, str):
            # 如果是字符串，先尝试解析为字典，再格式化输出
            parsed_data = json.loads(data)
            print(json.dumps(parsed_data, indent=4, ensure_ascii=False))
        else:
            # 如果已经是字典或列表，直接格式化输出
            print(json.dumps(data, indent=4, ensure_ascii=False))
    except (json.JSONDecodeError, TypeError):
        # 如果解析失败（比如只是普通字符串，或者包含不能转 JSON 的对象），直接原样输出
        print(data)

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
            Structured design_brief dict with visual_type
        """
        layout_context = layout_context or {}
        scene_context = scene_context or {}
        motion_context = motion_context or {}


        print("==========================================")
        print("layout_context:")
        print_pretty_json(layout_context)

        print("==========================================")
        print("scene_context:")
        print_pretty_json(scene_context)

        print("==========================================")

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

        # Region info — brightness can be string ('dark') or numeric
        raw_brightness = region_ctx.get("region_brightness", 50)
        if isinstance(raw_brightness, (int, float)):
            region_brightness = raw_brightness
        else:
            region_brightness = region_ctx.get("region_brightness_value",
                {"dark": 40, "medium": 128, "bright": 200}.get(str(raw_brightness), 50))
        region_type = region_ctx.get("region_type", "solid")
        bg_opacity = region_ctx.get("svg_bg_opacity",
                    region_ctx.get("recommended_svg_opacity", 0.92))
        # Clamp: 0.0 would make SVG invisible
        if isinstance(bg_opacity, (int, float)):
            bg_opacity = max(0.75, min(0.98, float(bg_opacity)))

        # ── 1b. Dark-floor strategy ─────────────────────────────────
        # If bg is near-black (brightness < 30), use a visible dark instead
        if isinstance(region_brightness, (int, float)) and region_brightness < 30:
            bg_color = "#1e293b"  # Slate-800: dark but not invisible

        # ── 1c. Accent fallback — extract from region_colors ────────
        # If scene_agent failed (accent is default #3498db + frame_count=0),
        # try to use real colors from layout_agent's region_colors
        frame_count = scene_context.get("frame_count", 0)
        is_scene_fallback = (accent_color == "#3498db" and frame_count == 0)
        
        region_colors = region_ctx.get("region_colors", [])
        if is_scene_fallback and len(region_colors) >= 2:
            # region_colors = [bg, mid, highlight]. Pick the most vibrant.
            best_accent = None
            best_saturation = 0
            for rc in region_colors[1:]:  # skip first (bg)
                sat = self._hex_saturation(rc)
                if sat > best_saturation:
                    best_saturation = sat
                    best_accent = rc
            if best_accent and best_saturation > 0.15:
                accent_color = best_accent
                print(f"    [VisualStrategy] Using region accent: {accent_color} (sat={best_saturation:.2f})")
            else:
                # Region also has no color — use a nice default
                accent_color = "#7c3aed"  # Purple-600
                secondary_color = "#06b6d4"  # Cyan-500
                print(f"    [VisualStrategy] Region has no vibrant colors, using default palette")

        # Scene / style
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
            brief["visual_type"] = "concept_map"  # default

        # ── 5. Inject hard color values (override LLM choices) ─────
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
        """Calculate HSL saturation from a hex color string."""
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
        """Build a human-readable context description for the LLM."""
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

        return "\n".join(lines)

    def _llm_create_brief(self, text_input: str, context_block: str) -> Dict:
        """Single LLM call to create the design brief with visual_type."""
        self._ensure_llm()

        from langchain_core.messages import SystemMessage, HumanMessage

        system_prompt = """You are a Visual Strategy Director for educational video overlays.

Your job: Take raw subtitle text + video scene context, and produce a structured design brief
for an SVG illustrator. The SVG will be overlaid on video, so it MUST match the video's topic
and visual style.

═══════════════════════════════════════════════════════
 STEP 1: DETERMINE visual_type (MOST IMPORTANT)
═══════════════════════════════════════════════════════

Choose the visual_type that best matches the content structure:

"data_chart" — when the text contains:
  • Specific numbers, percentages, metrics worth comparing
  • Performance comparisons with quantifiable values
  • Statistics, measurements, or scale differences
  • Example: "GPU is 100x faster than CPU" → bar chart
  • Example: "Market grew 20% in Q1, 35% in Q2" → line chart

"flowchart" — when the text describes:
  • Step-by-step processes, sequential operations
  • Pipelines, workflows, algorithms
  • Cause → effect chains with clear order
  • Example: "Data is preprocessed, then fed to model, then deployed"
  • Example: "First tokenize, then embed, then attend, then classify"

"concept_map" — when the text describes:
  • A central concept with multiple attributes/components
  • Radial relationships: "X includes A, B, C"
  • Features or properties of a main subject
  • Example: "Transformer's core components: self-attention, FFN, residual"
  • Example: "Machine learning branches: supervised, unsupervised, reinforcement"

"comparison" — when the text describes:
  • A vs B comparisons, pros/cons, tradeoffs
  • Side-by-side evaluation of alternatives
  • Example: "CNN excels at spatial features, RNN at temporal"
  • Example: "Python is easy to learn, C++ offers more performance"

"hierarchy" — when the text describes:
  • Classification, taxonomy, categories
  • Parent-child relationships, tree structures
  • Organizational charts, inheritance
  • Example: "Languages: compiled (C, Rust) vs interpreted (Python, JS)"
  • Example: "Animals divide into vertebrates and invertebrates"

"timeline" — when the text describes:
  • Historical events, version evolution, milestones
  • Chronological sequences with dates or periods
  • Development history, before/after changes over time
  • Example: "AI evolved from rule-based systems in the 1960s to deep learning in 2012"
  • Example: "Python 2.0 released in 2000, Python 3.0 in 2008, Python 3.12 in 2023"

"creative" — use this as DEFAULT when:
  • The content does NOT fit any structured type above
  • Abstract concepts, metaphors, analogies
  • Formulas, equations, mathematical visualizations
  • Dashboard-style displays, gauge meters, KPI indicators
  • Tables, feature matrices, multi-dimensional data
  • Any other creative/artistic visualization
  • Example: "Neural networks are like the human brain" → creative metaphor illustration
  • Example: "The attention formula: softmax(QK^T/√d)V" → formula visualization
  • Example: "System health: CPU 80%, Memory 60%, Disk 45%" → dashboard/gauge

═══════════════════════════════════════════════════════
 STEP 2: EXTRACT CONTENT FOR THE CHOSEN TYPE
═══════════════════════════════════════════════════════

CRITICAL RULES:
1. **SEMANTIC ALIGNMENT**: The SVG MUST illustrate the subtitle content.
2. **SCENE MATCHING**: Match illustration style to video scene type.
3. **CONTENT EXTRACTION**: Find the ONE key concept worth visualizing.
4. **PRACTICAL ICONS**: Describe icons SPECIFIC to each entity.

═══════════════════════════════════════════════════════
 OUTPUT FORMAT (JSON)
═══════════════════════════════════════════════════════

{
  "visual_type": "data_chart | flowchart | concept_map | comparison | hierarchy | timeline | creative",
  "core_topic": "One clear sentence describing what to visualize",

  // FOR ALL TYPES (Distill the raw transcript into clean, UI-ready text):
  "display_title": "1-5 words punchy title summarizing the main concept",
  "display_subtitle": "1 concise sentence explaining the core point (do NOT just copy raw transcript)",
  
  "entities": [
    {"label": "Name", "icon_hint": "What to draw for this entity"}
  ],
  "style_directive": "Art direction: line weight, shape style, aesthetic",
  "animation_plan": "What animations to use and why",
  "scene_alignment": "How this SVG's style matches the video scene (do NOT mention position, size, or overlay placement — only describe visual style/mood)",
  "warnings": ["Things to avoid"],

  // FOR data_chart ONLY — include these extra fields:
  "data_points": [
    {"label": "Category name", "value": 100, "unit": "units"}
  ],
  "chart_type": "bar | line | pie | radar",
  "chart_title": "Chart title text",
  "x_label": "X axis label",
  "y_label": "Y axis label",

  // FOR flowchart ONLY — include these extra fields:
  "steps": [
    {"order": 1, "label": "Step name", "description": "Brief description"}
  ],
  "flow_direction": "horizontal | vertical",

  // FOR concept_map ONLY — include these extra fields:
  "center_concept": "The main concept in the center",
  "relationships": [
    {"from": "center", "to": "satellite", "label": "relationship"}
  ],

  // FOR comparison ONLY — include these extra fields:
  "item_a": {"label": "Item A name", "traits": ["trait1", "trait2"]},
  "item_b": {"label": "Item B name", "traits": ["trait1", "trait2"]},
  "comparison_dimensions": ["dimension1", "dimension2"],

  // FOR hierarchy ONLY — include these extra fields:
  "root_label": "Root node name",
  "tree_structure": [
    {"parent": "root", "children": ["child1", "child2"]}
  ],

  // FOR timeline ONLY — include these extra fields:
  "milestones": [
    {"date": "2012", "label": "Event name", "description": "Brief description"}
  ],
  "timeline_direction": "horizontal | vertical",
  "time_span": "Overall time range description",

  // FOR creative — include these extra fields:
  "creative_concept": "The metaphor or visual idea to illustrate",
  "visual_elements": [
    {"element": "What to draw", "role": "How it connects to the concept"}
  ],
  "layout_suggestion": "Free-form layout description"
}

RULES:
- Extract 3-6 entities, no more
- Each entity MUST have a specific icon_hint
- For data_chart: extract ACTUAL numbers from the text, or estimate reasonable ones
- For flowchart: order steps correctly, 3-6 steps max
- For comparison: extract REAL differences, not generic ones
- For timeline: extract dates/periods, 3-7 milestones
- For creative: describe a clear visual metaphor or artistic concept
- If UNSURE which type, choose "creative" — it is the safest default
"""

        prompt = f"""Create a design brief for this SVG overlay.

SUBTITLE TEXT:
"{text_input}"

{context_block}

IMPORTANT: First decide the visual_type, then extract the appropriate structured data.
Think about what kind of visualization BEST represents the structure of this information.

Return JSON only."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]

        # print("==========================================")
        # print(system_prompt)
        print("==========================================")
        try:
            # 情况 1: 如果 prompt 已经是字典或列表，直接转换并美化输出
            if isinstance(prompt, (dict, list)):
                pretty_json = json.dumps(prompt, indent=4, ensure_ascii=False)
                print("visual strategy prompt (Dict/List -> JSON格式):")
                print(pretty_json)
            
            # 情况 2: 如果 prompt 是字符串，尝试先解析它，再美化输出
            elif isinstance(prompt, str):
                parsed_json = json.loads(prompt) # 尝试解析字符串
                pretty_json = json.dumps(parsed_json, indent=4, ensure_ascii=False)
                print("visual strategy prompt (String -> 解析并格式化为 JSON):")
                print(pretty_json)
                
            # 情况 3: 其他奇怪的类型
            else:
                print(f"visual strategy prompt (未知类型 {type(prompt)}，直接打印):")
                print(prompt)

        except json.JSONDecodeError:
            print("⚠️ 解析失败：prompt 是字符串，但不是有效的 JSON 格式。原样输出：")
            print(prompt)
        except TypeError:
            print("⚠️ 转换失败：prompt 包含无法转换为 JSON 的对象。原样输出：")
            print(prompt)
        print("==========================================")

        result = self.llm._generate(messages)
        content = result.generations[0].message.content
        parsed = self.llm.parse_json_response(content)

        print("==========================================")
        try:
            if isinstance(parsed, (dict, list)):
                pretty_json = json.dumps(parsed, indent=4, ensure_ascii=False)
                print("visual strategy result (JSON Format):")
                print(pretty_json)
            else:
                print("visual strategy result (Raw string):")
                print(parsed)
        except Exception:
            print(parsed)
        print("==========================================")

        # Validate minimum structure
        if not parsed.get("core_topic"):
            parsed["core_topic"] = text_input[:80]
        if not parsed.get("visual_type"):
            parsed["visual_type"] = "concept_map"
        if not parsed.get("entities"):
            parsed["entities"] = [{"label": "Concept", "icon_hint": "abstract diagram"}]
        if not parsed.get("style_directive"):
            parsed["style_directive"] = "Clean technical style, 2px strokes"
        if not parsed.get("animation_plan"):
            parsed["animation_plan"] = "Sequential fadeIn for each entity"
        if not parsed.get("scene_alignment"):
            parsed["scene_alignment"] = "educational diagram"
        if not parsed.get("warnings"):
            parsed["warnings"] = []

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
            "visual_type": "concept_map",
            "core_topic": text_input[:80],
            "entities": [
                {"label": e, "icon_hint": "simple labeled box"}
                for e in entities
            ],
            "center_concept": entities[0] if entities else "Topic",
            "relationships": [],
            "scene_alignment": "general educational diagram",
            "style_directive": "Clean minimalist, 2px strokes, sans-serif",
            "animation_plan": "Simple fadeIn for each entity",
            "warnings": [],
        }
