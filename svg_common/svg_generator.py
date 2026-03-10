"""
SVG Generator — Type-Specific Code Generation from Design Brief
=================================================================

Takes a structured design_brief (from VisualStrategy) and generates SVG code
via a single LLM call.  Uses type-specific prompt templates based on visual_type:
  - data_chart   → axes, bars/lines/pie, value labels
  - flowchart    → boxes, arrows, sequential steps
  - concept_map  → center node, satellite nodes, radial connections
  - comparison   → left/right panels, VS divider
  - hierarchy    → tree layout, root → branches

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
    """Generate type-specific SVG code from a VisualStrategy design brief."""

    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        self.llm_type = llm_type
        self.llm = None

    def _ensure_llm(self):
        if self.llm is None:
            self.llm = CustomChatModel(llm_type=self.llm_type, temperature=0.5)

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
        """Build type-specific prompt from design_brief and call LLM."""
        self._ensure_llm()
        from langchain_core.messages import SystemMessage, HumanMessage

        system_prompt = self._build_system_prompt(brief)
        user_prompt = self._build_user_prompt(brief)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        result = self.llm._generate(messages)
        content = result.generations[0].message.content
        svg = self._extract_svg(content)
        return svg

    # ════════════════════════════════════════════════════════════════
    #  SYSTEM PROMPT — Base rules + Type-specific template
    # ════════════════════════════════════════════════════════════════

    def _build_system_prompt(self, brief: Dict) -> str:
        colors = brief.get("color_instructions", {})
        bg = colors.get("background", "#0d1117")
        primary = colors.get("primary_accent", "#58a6ff")
        secondary = colors.get("secondary_accent", "#64ffda")
        text_c = colors.get("text", "#e6edf3")
        bg_opacity = colors.get("bg_opacity", 0.92)

        visual_type = brief.get("visual_type", "concept_map")

        # ── Base rules (shared by all types) ──────────────────────
        base = f"""You are an Expert SVG Illustrator for educational video overlays.
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
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20" fill="{bg}" opacity="{bg_opacity}"/>

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
- Title text: font-size >= 42px, font-weight >= 600
- Subtitle text: font-size >= 20px
- Body text / labels: font-size >= 16px (NEVER use 12px or 10px — too small!)
- Entity icons: minimum 80×80px bounding box
- Cards / boxes: minimum width 320px, minimum height 80px
- Central element (e.g. VS circle): minimum radius 50px or 100×100px
- Header boxes: minimum width 380px, height 80px"""

        # ── Type-specific template ────────────────────────────────
        type_templates = {
            "data_chart":  self._template_data_chart(primary, secondary, text_c),
            "flowchart":   self._template_flowchart(primary, secondary, text_c),
            "concept_map": self._template_concept_map(primary, secondary, text_c),
            "comparison":  self._template_comparison(primary, secondary, text_c),
            "hierarchy":   self._template_hierarchy(primary, secondary, text_c),
            "timeline":    self._template_timeline(primary, secondary, text_c),
            "creative":    self._template_creative(primary, secondary, text_c),
        }

        type_guide = type_templates.get(visual_type, type_templates["creative"])
        return base + "\n\n" + type_guide

    # ────────────────────────────────────────────────────────────────
    #  Type Template: DATA CHART
    # ────────────────────────────────────────────────────────────────

    def _template_data_chart(self, primary, secondary, text_c) -> str:
        return f"""═══ VISUAL TYPE: DATA CHART ═══
You are creating a DATA VISUALIZATION with axes, data elements, and value labels.

CHART LAYOUT:
- Title at top center (y=120), font-size 32px, font-weight 600
- Chart area: x=300 to x=1620, y=200 to y=850
- X axis: horizontal line at y=850, with category labels below
- Y axis: vertical line at x=300, with scale marks on the left
- Leave 80px padding around chart area

BAR CHART (if chart_type=bar):
- Bar width = chart_width / N * 0.6  (with gaps between bars)
- Bar height proportional to max value. Max bar height = 550px
- Round top corners: rx=6
- Color bars alternating {primary} and {secondary}
- Value label ABOVE each bar, font-size 18px

LINE CHART (if chart_type=line):
- Plot points as circles (r=6) connected by <polyline>
- Fill area below line with gradient (20% opacity)
- Animate with stroke-dashoffset

PIE CHART (if chart_type=pie):
- Center at (960, 540), radius=280
- Use <path> with arc commands for each slice
- Place labels outside with leader lines
- Rotate-in animation from 0 to full angle

ANIMATION:
- Bars: animate scaleY from 0→1 on a WRAPPER <g>, staggered 0.15s each
  <g transform="translate(X, 850)">
    <g class="bar-grow-N" style="transform-origin:center bottom">
      <rect y="{{-height}}" width="W" height="H" ... />
    </g>
  </g>
  .bar-grow-N {{ opacity:1; animation: growUp 0.6s ease-out {{delay}} both; }}
  @keyframes growUp {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
- Value labels: fadeIn after bar animation completes

REQUIRED SVG ELEMENTS:
1. Chart title
2. X axis line + category labels
3. Y axis line + scale marks + scale labels
4. Data elements (bars/lines/pie slices)
5. Value labels on each data point
6. Optional: legend if 2+ data series"""

    # ────────────────────────────────────────────────────────────────
    #  Type Template: FLOWCHART
    # ────────────────────────────────────────────────────────────────

    def _template_flowchart(self, primary, secondary, text_c) -> str:
        return f"""═══ VISUAL TYPE: FLOWCHART / PROCESS DIAGRAM ═══
You are creating a STEP-BY-STEP PROCESS diagram with boxes and arrows.

HORIZONTAL LAYOUT (preferred for 3-5 steps):
- Title at top center (y=120), font-size 32px
- Steps arranged at y=480 (vertical center)
- Evenly space boxes: first at x=250, last at x=1670
- Box size: 200×100px, rounded corners rx=14
- Arrows between boxes: horizontal lines with arrowhead markers

VERTICAL LAYOUT (for 4-7 steps or complex flows):
- Steps at x=960 (horizontal center)
- First at y=180, last at y=900
- Box size: 350×80px
- Arrows: vertical lines between boxes

BOX STYLE:
- Fill: {primary} at 15% opacity (semi-transparent)
- Border: 2px solid {primary}
- Step number: small circle at top-left of box, filled {primary}
- Label: font-size 18px, fill="{text_c}", text-anchor="middle"
- Optional: brief description below label in smaller font

ARROW STYLE:
- Stroke: {secondary}, 2px, with arrowhead marker
- Dashed variant for optional/conditional flows
- Marker definition:
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="{secondary}"/>
    </marker>
  </defs>

ANIMATION:
- Reveal steps LEFT → RIGHT (or TOP → DOWN), staggered 0.3s each
- Arrows animate AFTER the source box appears (stroke-dashoffset)
  <line stroke-dasharray="100" stroke-dashoffset="100"
        style="animation: drawLine 0.4s ease-out {{delay}} forwards"/>
  @keyframes drawLine {{ to {{ stroke-dashoffset: 0; }} }}

SPECIAL ELEMENTS:
- Decision diamonds: rotated 45° square for IF/ELSE branches
- Start/End: rounded pill shape (rx=40)
- Parallel: double-border box"""

    # ────────────────────────────────────────────────────────────────
    #  Type Template: CONCEPT MAP
    # ────────────────────────────────────────────────────────────────

    def _template_concept_map(self, primary, secondary, text_c) -> str:
        return f"""═══ VISUAL TYPE: CONCEPT MAP / RADIAL DIAGRAM ═══
You are creating a CENTRAL CONCEPT with satellite nodes radiating outward.

RADIAL LAYOUT:
- Title at top center (y=100), font-size 32px
- CENTER NODE at (960, 500):
  - Large circle: r=90, fill {primary} at 20% opacity, stroke {primary} 3px
  - Center label: font-size 22px, font-weight 600, fill="{text_c}"
  - Optional icon above label

- SATELLITE NODES arranged in a circle around center:
  - Radius from center: 300px
  - Evenly distributed by angle: 360° / N
  - Each satellite: circle r=55, fill {secondary} at 15% opacity, stroke {secondary} 2px
  - Label: font-size 16px, fill="{text_c}", placed below or beside the circle
  - Optional: small icon inside each satellite circle

- CONNECTION LINES from center to each satellite:
  - Stroke: {primary} at 40% opacity, 1.5px
  - Optional label on the line (relationship description)
  - Animate with stroke-dashoffset

ICON GUIDELINES:
- Draw DETAILED, RECOGNIZABLE icons using <path> elements
- Each icon ≈ 40-60px, inside the satellite circle
- Use clean line art, 2px stroke
- Make each icon DIFFERENT and SPECIFIC to its concept

ANIMATION:
- Center appears first (fadeIn 0.5s)
- Connection lines draw out from center (stroke-dashoffset, 0.3s each, staggered)
- Satellites appear as lines reach them (fadeIn 0.3s, delayed)
  Step 1: center fadeIn
  Step 2: line 1 draws (0.5s delay) → satellite 1 fadeIn (0.8s delay)
  Step 3: line 2 draws (0.8s delay) → satellite 2 fadeIn (1.1s delay)
  etc.

VARIATIONS:
- GRID VARIANT: For 6+ concepts, use 2×3 or 3×2 grid instead of radial
- GROUPED: Satellites can cluster by category with color-coded groups"""

    # ────────────────────────────────────────────────────────────────
    #  Type Template: COMPARISON
    # ────────────────────────────────────────────────────────────────

    def _template_comparison(self, primary, secondary, text_c) -> str:
        return f"""═══ VISUAL TYPE: COMPARISON / VS DIAGRAM ═══
You are creating a SIDE-BY-SIDE COMPARISON of two items.

LAYOUT:
- Title at top center (y=100), font-size 32px
- LEFT PANEL:  x=150 to x=900 — for Item A
- RIGHT PANEL: x=1020 to x=1770 — for Item B
- CENTER DIVIDER: vertical line at x=960
  - "VS" badge at center: circle with "VS" text, fill={primary}

PANEL STRUCTURE:
- Panel header (y=200):
  - Item name: font-size 28px, font-weight 700
  - Left panel header color: {primary}
  - Right panel header color: {secondary}
  - Optional icon above or beside the name

- Trait rows (starting y=320, spacing 90px):
  - For each dimension, show a trait block:
    <rect> background + text label
  - Left: aligned right (x=880), right-to-left layout
  - Right: aligned left (x=1040), left-to-right layout
  - Optional: connecting dotted line between matching dimensions

- Visual sizing:
  - Each trait block: width auto, height 60px, rx=8
  - Fill: item color at 12% opacity, border 1.5px solid

DIMENSION LABELS (if provided):
- Place in the center column (x=960) between the two panels
- Small font-size 14px, fill="{text_c}" at 60% opacity

ANIMATION:
- Title fadeIn (0s)
- VS badge scaleIn (0.3s)
- Left panel slides in from left: translateX(-30px → 0)
- Right panel slides in from right: translateX(30px → 0)
- Trait rows stagger 0.15s each, alternating left-right

COLOR RULE:
- Item A consistently uses {primary}
- Item B consistently uses {secondary}
- Never mix colors between items"""

    # ────────────────────────────────────────────────────────────────
    #  Type Template: HIERARCHY
    # ────────────────────────────────────────────────────────────────

    def _template_hierarchy(self, primary, secondary, text_c) -> str:
        return f"""═══ VISUAL TYPE: HIERARCHY / TREE DIAGRAM ═══
You are creating a TOP-DOWN TREE structure showing classification or inheritance.

LAYOUT:
- Title at top center (y=80), font-size 30px

- ROOT NODE at (960, 200):
  - Rounded rect: width 280, height 70, rx=14
  - Fill: {primary} at 20% opacity, border: 2px solid {primary}
  - Label: font-size 20px, font-weight 600, fill="{text_c}"

- LEVEL 2 NODES at y=400:
  - Evenly distributed across x axis
  - Rounded rect: width 220, height 60, rx=12
  - Fill: {secondary} at 15% opacity, border: 1.5px solid {secondary}
  - Label: font-size 17px, fill="{text_c}"

- LEVEL 3 NODES at y=600 (if needed):
  - Smaller: width 180, height 50, rx=10
  - Lighter styling, 1px border
  - Label: font-size 15px

- LEAF NODES at y=780 (if needed):
  - Smallest: width 150, height 40, rx=8
  - Minimal styling

CONNECTION LINES:
- From parent bottom-center to child top-center
- Style: stroke {primary} at 50% opacity, 1.5px
- Use cubic bezier for smooth curves:
  <path d="M {{parentX}},{{parentBottom}} C {{parentX}},{{mid}} {{childX}},{{mid}} {{childX}},{{childTop}}"
        fill="none" stroke="{primary}" stroke-width="1.5" opacity="0.5"/>

ANIMATION:
- Top-down cascade: root first, then level 2 (staggered), then level 3
  Each level delays 0.4s after the previous
- Connection lines draw with stroke-dashoffset, timed between parent and child

SPACING ALGORITHM:
- Level 2: if N children, distribute from x=200 to x=1720
  spacing = 1520 / (N + 1), each child at x = 200 + spacing * (i + 1)
- Level 3: cluster under their parent, narrower spread
- Minimum gap between nodes: 40px

VARIATION — SUNBURST (for deep trees):
- Concentric rings instead of top-down
- Root in center, levels expand outward as arc segments"""

    # ────────────────────────────────────────────────────────────────────
    #  Type Template: TIMELINE
    # ────────────────────────────────────────────────────────────────────

    def _template_timeline(self, primary, secondary, text_c) -> str:
        return f"""═══ VISUAL TYPE: TIMELINE / CHRONOLOGICAL DIAGRAM ═══
You are creating a TIMELINE showing events, milestones, or evolution over time.

HORIZONTAL LAYOUT (preferred, for 3-6 milestones):
- Title at top center (y=120), font-size 32px
- Main axis: horizontal line at y=500, from x=200 to x=1720
- Milestones as nodes ABOVE and BELOW the axis, alternating
- Node above: circle on axis + vertical line up + info card
- Node below: circle on axis + vertical line down + info card

MILESTONE NODE:
- Circle on axis: r=10, fill={primary}
- Vertical connector: 2px line, 80px tall
- Info card: rounded rect 180x70, fill={primary} at 12% opacity, stroke 1.5px
- Date label: font-size 16px, font-weight 700, fill={primary}
- Event label: font-size 14px, fill="{text_c}"
- Alternate: odd milestones above axis, even below

AXIS STYLE:
- Main line: stroke={text_c} at 30% opacity, 2px
- Arrow at right end (indicates future/continuation)
- Optional: gradient fill below axis line

ANIMATION:
- Axis line draws left to right (stroke-dashoffset)
- Each milestone appears sequentially as the line reaches it
  Milestone 1: 0.5s delay, Milestone 2: 0.9s, etc.
- Info cards fade+slide in from above/below

VERTICAL TIMELINE (for 5+ milestones):
- Main axis: vertical line at x=400, from y=150 to y=900
- Milestones arranged on the RIGHT side of the axis
- Connector lines go right from axis to info cards
- Info cards start at x=500, width=1100"""

    # ────────────────────────────────────────────────────────────────────
    #  Type Template: CREATIVE (free-form)
    # ────────────────────────────────────────────────────────────────────

    def _template_creative(self, primary, secondary, text_c) -> str:
        return f"""═══ VISUAL TYPE: CREATIVE / FREE-FORM ILLUSTRATION ═══
You are creating a CREATIVE, ARTISTIC SVG illustration. There are NO rigid layout rules.
You have full freedom to design the most visually impactful representation.

GUIDELINES (flexible, not strict rules):
- Title at top or integrated into the design
- Use the FULL canvas creatively — don't just cluster elements in center
- Create VISUAL METAPHORS: abstract concepts → tangible visual forms
- Use a mix of icons, shapes, lines, gradients, and text
- Prioritize VISUAL IMPACT and CLARITY over completeness

ICON DESIGN:
- Draw DETAILED, RECOGNIZABLE icons using <path> elements
- Each icon ≈ 60-100px, specific to what it represents
- Clean line-art style, 2-3px stroke, optional subtle fills
- Use alternating colors: {primary} and {secondary}

CREATIVE TECHNIQUES TO USE:
1. VISUAL METAPHOR: Represent abstract concepts as physical objects
   (e.g., "security" = shield icon, "growth" = upward arrow/plant)
2. SPATIAL GROUPING: Related concepts near each other, unrelated far apart
3. SIZE HIERARCHY: Important = bigger, secondary = smaller
4. CONNECTION LINES: Show relationships with styled paths
5. GRADIENT FILLS: Use subtle gradients for premium feel
6. DECORATIVE ELEMENTS: Corner accents, subtle grid backgrounds, divider lines

ANIMATION:
- Use meaningful animations that enhance understanding:
  • Sequential reveal for process/narrative content
  • Pulse for emphasis on key elements
  • Float for ambient/decorative elements
  • Draw-in for connections and paths
- Stagger delays 0.2-0.4s between elements

SUITABLE FOR:
- Abstract concepts and metaphors
- Formulas and equations (render as styled text with visual context)
- Dashboard/gauge displays (progress rings, meters)
- Feature matrices and tables (styled SVG grid)
- Any content that doesn't fit structured chart types

QUALITY STANDARD:
- The result should look like a PREMIUM infographic, not a simple diagram
- Every element must serve a purpose — decorative OR informational
- Balance whitespace and content — don't overcrowd"""

    # ════════════════════════════════════════════════════════════════
    #  USER PROMPT — dynamic content from design_brief
    # ════════════════════════════════════════════════════════════════

    def _build_user_prompt(self, brief: Dict) -> str:
        visual_type = brief.get("visual_type", "concept_map")
        
        # Use refined display text from visual strategy LLM
        display_title = brief.get("display_title", brief.get("core_topic", "Visualization"))
        display_subtitle = brief.get("display_subtitle", "")
        
        scene_alignment = brief.get("scene_alignment", "")
        style_directive = brief.get("style_directive", "")
        animation_plan = brief.get("animation_plan", "")
        warnings = brief.get("warnings", [])

        colors = brief.get("color_instructions", {})
        bg = colors.get("background", "#0d1117")
        bg_opacity = colors.get("bg_opacity", 0.92)

        # ── Type-specific content section ──────────────────────────
        type_content = self._format_type_content(brief, visual_type)

        # ── Warnings ──────────────────────────────────────────────
        warn_text = ""
        if warnings:
            warn_text = "\n⚠ AVOID:\n" + "\n".join(f"  - {w}" for w in warnings)

        return f"""Create a premium animated SVG {visual_type.upper()}.

DISPLAY TITLE (Render this as main heading, e.g. <text>): {display_title}
DISPLAY SUBTITLE (Render this as sub-heading, e.g. <text>): {display_subtitle}
VISUAL TYPE: {visual_type}
SCENE CONTEXT: {scene_alignment}
STYLE: {style_directive}
ANIMATION: {animation_plan}

{type_content}
{warn_text}

Background: <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20"
                  fill="{bg}" opacity="{bg_opacity}"/>

⚠ LAYOUT REMINDER: Use the FULL 1920×1080 canvas. Title near x=960. Spread entities from x=200 to x=1700, y=150 to y=950. Do NOT cluster in one corner.

Output SVG code directly. No markdown wrapping."""

    def _format_type_content(self, brief: Dict, visual_type: str) -> str:
        """Format type-specific content for the user prompt."""

        if visual_type == "data_chart":
            data_points = brief.get("data_points", [])
            chart_type = brief.get("chart_type", "bar")
            chart_title = brief.get("chart_title", brief.get("core_topic", ""))
            x_label = brief.get("x_label", "")
            y_label = brief.get("y_label", "")

            dp_lines = []
            for dp in data_points:
                if isinstance(dp, dict):
                    dp_lines.append(f"  - {dp.get('label','?')}: {dp.get('value','?')} {dp.get('unit','')}")
            dp_text = "\n".join(dp_lines) or "  (infer data from topic)"

            return f"""CHART TYPE: {chart_type}
CHART TITLE: {chart_title}
X AXIS: {x_label}
Y AXIS: {y_label}

DATA POINTS:
{dp_text}"""

        elif visual_type == "flowchart":
            steps = brief.get("steps", [])
            direction = brief.get("flow_direction", "horizontal")
            step_lines = []
            for s in steps:
                if isinstance(s, dict):
                    step_lines.append(f"  {s.get('order','?')}. {s.get('label','?')} — {s.get('description','')}")
            step_text = "\n".join(step_lines) or "  (infer steps from topic)"

            return f"""FLOW DIRECTION: {direction}

STEPS:
{step_text}"""

        elif visual_type == "concept_map":
            center = brief.get("center_concept", brief.get("core_topic", "Concept"))
            entities = brief.get("entities", [])
            rels = brief.get("relationships", [])

            ent_lines = []
            for i, e in enumerate(entities):
                if isinstance(e, dict):
                    ent_lines.append(f"  {i+1}. \"{e.get('label','')}\" — draw: {e.get('icon_hint','')}")
            ent_text = "\n".join(ent_lines) or "  (infer from topic)"

            rel_lines = []
            for r in rels[:8]:
                if isinstance(r, dict):
                    rel_lines.append(f"  {r.get('from','?')} --[{r.get('label','→')}]--> {r.get('to','?')}")
            rel_text = "\n".join(rel_lines) or "  Connect center to satellites"

            return f"""CENTER CONCEPT: {center}

SATELLITE ENTITIES:
{ent_text}

CONNECTIONS:
{rel_text}"""

        elif visual_type == "comparison":
            item_a = brief.get("item_a", {})
            item_b = brief.get("item_b", {})
            dims = brief.get("comparison_dimensions", [])

            a_traits = "\n".join(f"    - {t}" for t in item_a.get("traits", []))
            b_traits = "\n".join(f"    - {t}" for t in item_b.get("traits", []))
            dim_text = "\n".join(f"  - {d}" for d in dims) if dims else "  (infer dimensions)"

            return f"""ITEM A: {item_a.get('label', 'Item A')}
  Traits:
{a_traits}

ITEM B: {item_b.get('label', 'Item B')}
  Traits:
{b_traits}

COMPARISON DIMENSIONS:
{dim_text}"""

        elif visual_type == "hierarchy":
            root = brief.get("root_label", brief.get("core_topic", "Root"))
            tree = brief.get("tree_structure", [])
            entities = brief.get("entities", [])

            tree_lines = []
            for node in tree:
                if isinstance(node, dict):
                    parent = node.get("parent", "root")
                    children = node.get("children", [])
                    tree_lines.append(f"  {parent} → [{', '.join(children)}]")
            tree_text = "\n".join(tree_lines) or "  (infer tree from entities)"

            ent_lines = []
            for e in entities:
                if isinstance(e, dict):
                    ent_lines.append(f"  - {e.get('label','')} ({e.get('icon_hint','')})")
            ent_text = "\n".join(ent_lines)

            return f"""ROOT: {root}

TREE STRUCTURE:
{tree_text}

ENTITIES:
{ent_text}"""

        # timeline type
        if visual_type == "timeline":
            milestones = brief.get("milestones", [])
            direction = brief.get("timeline_direction", "horizontal")
            time_span = brief.get("time_span", "")

            ms_lines = []
            for m in milestones:
                if isinstance(m, dict):
                    ms_lines.append(f"  {m.get('date','?')}. {m.get('label','?')} — {m.get('description','')}")
            ms_text = "\n".join(ms_lines) or "  (infer milestones from topic)"

            return f"""TIMELINE DIRECTION: {direction}
TIME SPAN: {time_span}

MILESTONES:
{ms_text}"""

        # creative type
        if visual_type == "creative":
            creative_concept = brief.get("creative_concept", brief.get("core_topic", ""))
            visual_elements = brief.get("visual_elements", [])
            layout_suggestion = brief.get("layout_suggestion", "")
            entities = brief.get("entities", [])

            ve_lines = []
            for ve in visual_elements:
                if isinstance(ve, dict):
                    ve_lines.append(f"  - {ve.get('element','')} → {ve.get('role','')}")
            ve_text = "\n".join(ve_lines)

            ent_lines = []
            for i, e in enumerate(entities):
                if isinstance(e, dict):
                    ent_lines.append(f"  {i+1}. \"{e.get('label','')}\" — draw: {e.get('icon_hint','')}")
            ent_text = "\n".join(ent_lines)

            return f"""CREATIVE CONCEPT: {creative_concept}

VISUAL ELEMENTS:
{ve_text}

ENTITIES:
{ent_text}

LAYOUT: {layout_suggestion}

You have FULL creative freedom. Create a visually stunning and meaningful SVG
that captures the essence of this concept. Use icons, shapes, lines, gradients,
and animations to make a unique, memorable illustration."""

        # unknown type fallback
        entities = brief.get("entities", [])
        ent_lines = []
        for i, e in enumerate(entities):
            if isinstance(e, dict):
                ent_lines.append(f"  {i+1}. \"{e.get('label','')}\" — {e.get('icon_hint','')}")
        return f"ENTITIES:\n" + "\n".join(ent_lines)

    # ================================================================
    #  Utilities
    # ================================================================

    def _extract_svg(self, text: str) -> str:
        """Extract SVG content from LLM response."""
        import re
        match = re.search(r"(<svg[\s\S]*?</svg>)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        if "```" in text:
            lines = text.split("\n")
            svg_lines = []
            inside = False
            for line in lines:
                if line.strip().startswith("```") and not inside:
                    inside = True
                    continue
                elif line.strip().startswith("```") and inside:
                    break
                elif inside:
                    svg_lines.append(line)
            joined = "\n".join(svg_lines)
            if "<svg" in joined:
                return joined
        return text





    # ================================================================
    #  Fallback — type-aware
    # ================================================================

    def _fallback_svg(self, brief: Dict) -> str:
        """Generate a basic type-aware SVG when LLM fails."""
        colors = brief.get("color_instructions", {})
        bg = colors.get("background", "#0d1117")
        primary = colors.get("primary_accent", "#58a6ff")
        secondary = colors.get("secondary_accent", "#64ffda")
        text_c = colors.get("text", "#e6edf3")
        bg_opacity = colors.get("bg_opacity", 0.92)

        visual_type = brief.get("visual_type", "concept_map")
        topic = brief.get("core_topic", "Visualization")
        entities = brief.get("entities", [])

        if visual_type == "data_chart":
            return self._fallback_data_chart(brief, bg, primary, secondary, text_c, bg_opacity)
        elif visual_type == "flowchart":
            return self._fallback_flowchart(brief, bg, primary, secondary, text_c, bg_opacity)
        elif visual_type == "comparison":
            return self._fallback_comparison(brief, bg, primary, secondary, text_c, bg_opacity)
        elif visual_type == "hierarchy":
            return self._fallback_hierarchy(brief, bg, primary, secondary, text_c, bg_opacity)
        elif visual_type == "timeline":
            return self._fallback_timeline(brief, bg, primary, secondary, text_c, bg_opacity)
        elif visual_type == "creative":
            return self._fallback_creative(brief, bg, primary, secondary, text_c, bg_opacity)
        else:
            return self._fallback_concept_map(brief, bg, primary, secondary, text_c, bg_opacity)

    # ── Fallback: Data Chart ──────────────────────────────────────

    def _fallback_data_chart(self, brief, bg, primary, secondary, text_c, bg_opacity):
        topic = brief.get("display_title", brief.get("core_topic", "Data"))[:50]
        safe_topic = _safe(topic)
        data_points = brief.get("data_points", brief.get("entities", []))

        bars = []
        n = max(len(data_points), 1)
        bar_w = min(120, 1200 // n)
        max_val = max((dp.get("value", 50) if isinstance(dp, dict) else 50) for dp in data_points) or 100

        for i, dp in enumerate(data_points[:8]):
            label = dp.get("label", str(dp)) if isinstance(dp, dict) else str(dp)
            val = dp.get("value", 50) if isinstance(dp, dict) else 50
            safe_label = _safe(label[:15])
            x = 350 + i * (bar_w + 40)
            h = int(val / max_val * 500)
            color = primary if i % 2 == 0 else secondary
            delay = f"{0.2 + i * 0.15:.2f}s"

            bars.append(f'''  <g transform="translate({x}, 850)">
    <g class="bar-{i}" style="transform-origin:center bottom; opacity:1; animation: growUp 0.6s ease-out {delay} both">
      <rect x="{-bar_w//2}" y="{-h}" width="{bar_w}" height="{h}" rx="6" fill="{color}" opacity="0.85"/>
      <text x="0" y="{-h-15}" font-family="system-ui" font-size="16" fill="{text_c}" text-anchor="middle">{val}</text>
    </g>
    <text x="0" y="30" font-family="system-ui" font-size="14" fill="{text_c}" text-anchor="middle" opacity="0.7">{safe_label}</text>
  </g>''')

        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>
    @keyframes growUp {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  </style>
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20" fill="{bg}" opacity="{bg_opacity}"/>
  <text x="960" y="120" font-family="system-ui" font-size="32" font-weight="600" fill="{text_c}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.5s ease-out both">{safe_topic}</text>
  <line x1="300" y1="850" x2="1620" y2="850" stroke="{text_c}" stroke-width="1.5" opacity="0.3"/>
  <line x1="300" y1="250" x2="300" y2="850" stroke="{text_c}" stroke-width="1.5" opacity="0.3"/>
{chr(10).join(bars)}
</svg>'''

    # ── Fallback: Flowchart ───────────────────────────────────────

    def _fallback_flowchart(self, brief, bg, primary, secondary, text_c, bg_opacity):
        topic = brief.get("display_title", brief.get("core_topic", "Process"))[:50]
        safe_topic = _safe(topic)
        steps = brief.get("steps", brief.get("entities", []))

        n = max(len(steps), 1)
        spacing = 1400 // (n + 1)
        boxes = []

        for i, step in enumerate(steps[:6]):
            label = step.get("label", str(step)) if isinstance(step, dict) else str(step)
            safe_label = _safe(label[:20])
            x = 260 + spacing * (i + 1)
            y = 500
            delay = f"{0.3 + i * 0.3:.1f}s"

            boxes.append(f'''  <g transform="translate({x}, {y})">
    <g style="opacity:1; animation: fadeIn 0.5s ease-out {delay} both">
      <rect x="-100" y="-45" width="200" height="90" rx="14" fill="{primary}" fill-opacity="0.15" stroke="{primary}" stroke-width="2"/>
      <circle cx="-80" cy="-25" r="12" fill="{primary}" opacity="0.8"/>
      <text x="-80" y="-21" font-family="system-ui" font-size="12" fill="{bg}" text-anchor="middle" font-weight="700">{i+1}</text>
      <text y="8" font-family="system-ui" font-size="16" fill="{text_c}" text-anchor="middle">{safe_label}</text>
    </g>
  </g>''')

            if i < len(steps) - 1:
                x2 = 260 + spacing * (i + 2)
                arrow_delay = f"{0.5 + i * 0.3:.1f}s"
                boxes.append(f'''  <line x1="{x+100}" y1="{y}" x2="{x2-100}" y2="{y}"
        stroke="{secondary}" stroke-width="2" marker-end="url(#arrow)"
        stroke-dasharray="100" stroke-dashoffset="100"
        style="animation: drawLine 0.4s ease-out {arrow_delay} forwards"/>''')

        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="{secondary}"/>
    </marker>
  </defs>
  <style>
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes drawLine {{ to {{ stroke-dashoffset: 0; }} }}
  </style>
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20" fill="{bg}" opacity="{bg_opacity}"/>
  <text x="960" y="200" font-family="system-ui" font-size="32" font-weight="600" fill="{text_c}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.5s ease-out both">{safe_topic}</text>
{chr(10).join(boxes)}
</svg>'''

    # ── Fallback: Concept Map ─────────────────────────────────────

    def _fallback_concept_map(self, brief, bg, primary, secondary, text_c, bg_opacity):
        topic = brief.get("display_title", brief.get("core_topic", "Concept"))[:50]
        safe_topic = _safe(topic)
        center = brief.get("center_concept", topic[:25])
        safe_center = _safe(center)
        entities = brief.get("entities", [])

        import math
        n = max(len(entities), 1)
        radius = 280
        cx, cy = 960, 520
        satellites = []

        for i, ent in enumerate(entities[:8]):
            label = ent.get("label", str(ent)) if isinstance(ent, dict) else str(ent)
            safe_label = _safe(label[:18])
            angle = (2 * math.pi * i / n) - math.pi / 2
            sx = cx + int(radius * math.cos(angle))
            sy = cy + int(radius * math.sin(angle))
            color = primary if i % 2 == 0 else secondary
            line_delay = f"{0.5 + i * 0.25:.2f}s"
            node_delay = f"{0.7 + i * 0.25:.2f}s"

            satellites.append(f'''  <line x1="{cx}" y1="{cy}" x2="{sx}" y2="{sy}"
        stroke="{primary}" stroke-width="1.5" opacity="0.35"
        stroke-dasharray="200" stroke-dashoffset="200"
        style="animation: drawLine 0.4s ease-out {line_delay} forwards"/>
  <g transform="translate({sx}, {sy})">
    <g style="opacity:1; animation: fadeIn 0.4s ease-out {node_delay} both">
      <circle r="50" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.5"/>
      <text y="5" font-family="system-ui" font-size="14" fill="{text_c}" text-anchor="middle">{safe_label}</text>
    </g>
  </g>''')

        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes drawLine {{ to {{ stroke-dashoffset: 0; }} }}
  </style>
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20" fill="{bg}" opacity="{bg_opacity}"/>
  <text x="960" y="100" font-family="system-ui" font-size="30" font-weight="600" fill="{text_c}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.5s ease-out both">{safe_topic}</text>
  <g style="opacity:1; animation: fadeIn 0.3s ease-out both">
    <circle cx="{cx}" cy="{cy}" r="85" fill="{primary}" fill-opacity="0.18" stroke="{primary}" stroke-width="2.5"/>
    <text x="{cx}" y="{cy+6}" font-family="system-ui" font-size="20" font-weight="600" fill="{text_c}" text-anchor="middle">{safe_center}</text>
  </g>
{chr(10).join(satellites)}
</svg>'''

    # ── Fallback: Comparison ──────────────────────────────────────

    def _fallback_comparison(self, brief, bg, primary, secondary, text_c, bg_opacity):
        topic = brief.get("display_title", brief.get("core_topic", "Comparison"))[:50]
        safe_topic = _safe(topic)
        item_a = brief.get("item_a", {})
        item_b = brief.get("item_b", {})
        label_a = _safe(item_a.get("label", "Item A")[:20])
        label_b = _safe(item_b.get("label", "Item B")[:20])
        traits_a = item_a.get("traits", [])
        traits_b = item_b.get("traits", [])

        rows_a = []
        for i, t in enumerate(traits_a[:5]):
            y = 350 + i * 90
            safe_t = _safe(str(t)[:30])
            delay = f"{0.5 + i * 0.15:.2f}s"
            rows_a.append(f'''  <g style="opacity:1; animation: fadeIn 0.4s ease-out {delay} both">
    <rect x="200" y="{y}" width="650" height="55" rx="8" fill="{primary}" fill-opacity="0.1" stroke="{primary}" stroke-width="1"/>
    <text x="525" y="{y+33}" font-family="system-ui" font-size="16" fill="{text_c}" text-anchor="middle">{safe_t}</text>
  </g>''')

        rows_b = []
        for i, t in enumerate(traits_b[:5]):
            y = 350 + i * 90
            safe_t = _safe(str(t)[:30])
            delay = f"{0.6 + i * 0.15:.2f}s"
            rows_b.append(f'''  <g style="opacity:1; animation: fadeIn 0.4s ease-out {delay} both">
    <rect x="1070" y="{y}" width="650" height="55" rx="8" fill="{secondary}" fill-opacity="0.1" stroke="{secondary}" stroke-width="1"/>
    <text x="1395" y="{y+33}" font-family="system-ui" font-size="16" fill="{text_c}" text-anchor="middle">{safe_t}</text>
  </g>''')

        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes scaleIn {{ from {{ transform: scale(0); }} to {{ transform: scale(1); }} }}
  </style>
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20" fill="{bg}" opacity="{bg_opacity}"/>
  <text x="960" y="100" font-family="system-ui" font-size="30" font-weight="600" fill="{text_c}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.5s ease-out both">{safe_topic}</text>
  <line x1="960" y1="150" x2="960" y2="950" stroke="{text_c}" stroke-width="1" opacity="0.2"/>
  <g style="opacity:1; animation: scaleIn 0.3s ease-out 0.3s both; transform-origin: 960px 250px">
    <circle cx="960" cy="250" r="30" fill="{primary}"/>
    <text x="960" y="256" font-family="system-ui" font-size="16" font-weight="700" fill="{bg}" text-anchor="middle">VS</text>
  </g>
  <text x="525" y="250" font-family="system-ui" font-size="26" font-weight="700" fill="{primary}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.4s ease-out 0.2s both">{label_a}</text>
  <text x="1395" y="250" font-family="system-ui" font-size="26" font-weight="700" fill="{secondary}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.4s ease-out 0.3s both">{label_b}</text>
{chr(10).join(rows_a)}
{chr(10).join(rows_b)}
</svg>'''

    # ── Fallback: Hierarchy ───────────────────────────────────────

    def _fallback_hierarchy(self, brief, bg, primary, secondary, text_c, bg_opacity):
        topic = brief.get("display_title", brief.get("core_topic", "Classification"))[:50]
        safe_topic = _safe(topic)
        root = _safe(brief.get("root_label", topic[:25]))
        tree = brief.get("tree_structure", [])
        entities = brief.get("entities", [])

        # Simple 2-level tree
        children = []
        if tree:
            for node in tree:
                if isinstance(node, dict):
                    children.extend(node.get("children", []))
        if not children:
            children = [e.get("label", str(e)) if isinstance(e, dict) else str(e) for e in entities[:6]]

        n = max(len(children), 1)
        nodes = []
        spacing = 1400 // (n + 1)
        root_x, root_y = 960, 220

        for i, child in enumerate(children[:8]):
            safe_child = _safe(str(child)[:20])
            cx = 260 + spacing * (i + 1)
            cy = 500
            color = primary if i % 2 == 0 else secondary
            line_delay = f"{0.4 + i * 0.15:.2f}s"
            node_delay = f"{0.6 + i * 0.15:.2f}s"

            nodes.append(f'''  <path d="M {root_x},{root_y+35} C {root_x},{root_y+120} {cx},{cy-100} {cx},{cy-30}"
        fill="none" stroke="{primary}" stroke-width="1.5" opacity="0.4"
        stroke-dasharray="300" stroke-dashoffset="300"
        style="animation: drawLine 0.5s ease-out {line_delay} forwards"/>
  <g transform="translate({cx}, {cy})">
    <g style="opacity:1; animation: fadeIn 0.4s ease-out {node_delay} both">
      <rect x="-100" y="-30" width="200" height="60" rx="12" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.5"/>
      <text y="6" font-family="system-ui" font-size="16" fill="{text_c}" text-anchor="middle">{safe_child}</text>
    </g>
  </g>''')

        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes drawLine {{ to {{ stroke-dashoffset: 0; }} }}
  </style>
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20" fill="{bg}" opacity="{bg_opacity}"/>
  <text x="960" y="100" font-family="system-ui" font-size="28" font-weight="600" fill="{text_c}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.5s ease-out both">{safe_topic}</text>
  <g style="opacity:1; animation: fadeIn 0.3s ease-out both">
    <rect x="{root_x-130}" y="{root_y-35}" width="260" height="70" rx="14" fill="{primary}" fill-opacity="0.18" stroke="{primary}" stroke-width="2.5"/>
    <text x="{root_x}" y="{root_y+6}" font-family="system-ui" font-size="20" font-weight="600" fill="{text_c}" text-anchor="middle">{root}</text>
  </g>
{chr(10).join(nodes)}
</svg>'''

    # ── Fallback: Timeline ──────────────────────────────────────────

    def _fallback_timeline(self, brief, bg, primary, secondary, text_c, bg_opacity):
        topic = brief.get("display_title", brief.get("core_topic", "Timeline"))[:50]
        safe_topic = _safe(topic)
        milestones = brief.get("milestones", brief.get("entities", []))

        n = max(len(milestones), 1)
        spacing = 1400 // (n + 1)
        nodes_svg = []

        for i, ms in enumerate(milestones[:7]):
            label = ms.get("label", str(ms)) if isinstance(ms, dict) else str(ms)
            date = ms.get("date", "") if isinstance(ms, dict) else ""
            safe_label = _safe(label[:20])
            safe_date = _safe(str(date)[:12])
            x = 200 + spacing * (i + 1)
            above = (i % 2 == 0)
            y_card = 350 if above else 600
            y_line_start = 500
            y_line_end = 400 if above else 560
            color = primary if i % 2 == 0 else secondary
            delay = f"{0.5 + i * 0.3:.1f}s"

            nodes_svg.append(f'''  <circle cx="{x}" cy="500" r="8" fill="{color}"
        style="opacity:1; animation: fadeIn 0.3s ease-out {delay} both"/>
  <line x1="{x}" y1="{y_line_start}" x2="{x}" y2="{y_line_end}"
        stroke="{color}" stroke-width="1.5" opacity="0.5"
        stroke-dasharray="80" stroke-dashoffset="80"
        style="animation: drawLine 0.3s ease-out {delay} forwards"/>
  <g transform="translate({x}, {y_card})">
    <g style="opacity:1; animation: fadeIn 0.4s ease-out {float(delay[:-1])+0.15:.1f}s both">
      <rect x="-85" y="-30" width="170" height="60" rx="10" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.5"/>
      <text y="-8" font-family="system-ui" font-size="13" font-weight="700" fill="{color}" text-anchor="middle">{safe_date}</text>
      <text y="14" font-family="system-ui" font-size="12" fill="{text_c}" text-anchor="middle">{safe_label}</text>
    </g>
  </g>''')

        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes drawLine {{ to {{ stroke-dashoffset: 0; }} }}
  </style>
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20" fill="{bg}" opacity="{bg_opacity}"/>
  <text x="960" y="150" font-family="system-ui" font-size="30" font-weight="600" fill="{text_c}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.5s ease-out both">{safe_topic}</text>
  <line x1="180" y1="500" x2="1740" y2="500" stroke="{text_c}" stroke-width="2" opacity="0.25"
        stroke-dasharray="1600" stroke-dashoffset="1600"
        style="animation: drawLine 1s ease-out 0.3s forwards"/>
  <polygon points="1740,495 1755,500 1740,505" fill="{text_c}" opacity="0.3"
           style="opacity:0.3; animation: fadeIn 0.3s ease-out 1.3s both"/>
{chr(10).join(nodes_svg)}
</svg>'''

    # ── Fallback: Creative ──────────────────────────────────────────

    def _fallback_creative(self, brief, bg, primary, secondary, text_c, bg_opacity):
        topic = brief.get("display_title", brief.get("core_topic", "Concept"))[:50]
        safe_topic = _safe(topic)
        entities = brief.get("entities", [])
        creative_concept = brief.get("creative_concept", topic)
        safe_concept = _safe(str(creative_concept)[:40])

        # Create a scattered layout with entities
        import math
        n = max(len(entities), 1)
        elements = []

        # Fixed positions for variety (avoiding overlap)
        positions = [
            (350, 350), (960, 300), (1550, 380),
            (300, 650), (750, 550), (1200, 600),
            (960, 750), (500, 450),
        ]

        for i, ent in enumerate(entities[:8]):
            label = ent.get("label", str(ent)) if isinstance(ent, dict) else str(ent)
            safe_label = _safe(label[:18])
            px, py = positions[i % len(positions)]
            color = primary if i % 2 == 0 else secondary
            delay = f"{0.3 + i * 0.2:.1f}s"
            size = 55 - i * 3  # slightly smaller for later items

            elements.append(f'''  <g transform="translate({px}, {py})">
    <g style="opacity:1; animation: fadeIn 0.5s ease-out {delay} both">
      <circle r="{size}" fill="{color}" fill-opacity="0.1" stroke="{color}" stroke-width="1.5"/>
      <text y="5" font-family="system-ui" font-size="14" fill="{text_c}" text-anchor="middle">{safe_label}</text>
    </g>
  </g>''')

            # Light connections between adjacent items
            if i > 0:
                ppx, ppy = positions[(i-1) % len(positions)]
                elements.append(f'''  <line x1="{ppx}" y1="{ppy}" x2="{px}" y2="{py}"
        stroke="{primary}" stroke-width="1" opacity="0.15"
        stroke-dasharray="4,6"/>''')

        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  </style>
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" rx="20" fill="{bg}" opacity="{bg_opacity}"/>
  <text x="960" y="130" font-family="system-ui" font-size="30" font-weight="600" fill="{text_c}" text-anchor="middle"
        style="opacity:1; animation: fadeIn 0.5s ease-out both">{safe_topic}</text>
  <text x="960" y="170" font-family="system-ui" font-size="18" fill="{text_c}" text-anchor="middle" opacity="0.6"
        style="opacity:0.6; animation: fadeIn 0.5s ease-out 0.2s both">{safe_concept}</text>
{chr(10).join(elements)}
</svg>'''


# ════════════════════════════════════════════════════════════════════
#  Utilities
# ════════════════════════════════════════════════════════════════════

def _safe(text: str) -> str:
    """Escape XML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
