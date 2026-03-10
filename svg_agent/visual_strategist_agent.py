"""
Visual Strategist Agent
=======================

视觉策略 - 将concepts转化为SVGCreator可直接使用的visual_blueprint
这是ConceptAnalyzer和SVGCreator之间的桥梁
"""

from typing import Dict, Tuple, List
from base_agent import BaseAgent
from state import SVGState


class VisualStrategistAgent(BaseAgent):
    """视觉策略Agent - 输出visual_blueprint供SVGCreator使用"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("visual_strategist", llm_type)
        self.role_description = "Create visual blueprint for SVG generation"
        self.capabilities = ["blueprint_generation", "color_selection", "layout_planning"]
    
    def execute(self, state: SVGState) -> SVGState:
        """执行视觉策略 — simple模式生成1方案, complex模式生成3方案竞演"""
        self._log("Creating visual blueprint...")
        
        concepts = state.get("concepts", {})
        scene_context = state.get("scene_context", {})
        color_scheme = state.get("color_scheme", None)
        layout_detailed = state.get("layout_plan_detailed", None)
        layout_context = state.get("layout_context", {})
        enable_complex = state.get("enable_complex_mode", False)
        
        if not concepts:
            self._log("No concepts specified, using defaults", "warning")
        
        if enable_complex:
            # 复杂模式: 生成3个风格迥异的方案
            self._log("  Complex mode → generating 3 competing blueprints")
            styles = [
                {"name": "conservative", "desc": "Clean, minimal, professional diagram. Clear structure, muted animations."},
                {"name": "bold", "desc": "Creative, artistic, metaphorical visualization. Vivid colors, dramatic animations, surprising layouts."},
                {"name": "neutral", "desc": "Balanced, informative, moderately stylized. Good mix of clarity and visual appeal."},
            ]
            
            competing = []
            for style in styles:
                bp = self._generate_blueprint_llm(
                    concepts, scene_context, layout_context,
                    color_scheme=color_scheme,
                    layout_detailed=layout_detailed,
                    style_override=style
                )
                bp["style_name"] = style["name"]
                competing.append(bp)
                self._log(f"    ✓ {style['name']} blueprint ready")
            
            state["competing_blueprints"] = competing
            # visual_strategy 会由 JudgeAgent 设置
            state["visual_strategy"] = competing[0]  # 临时，Judge会覆盖
        else:
            # 简单模式: 直接生成1个方案
            blueprint = self._generate_blueprint_llm(
                concepts, scene_context, layout_context,
                color_scheme=color_scheme,
                layout_detailed=layout_detailed
            )
            state["visual_strategy"] = blueprint
        
        vs = state["visual_strategy"]
        self.record_decision(
            state,
            "visual_strategy",
            f"Blueprint: {vs.get('diagram_description', 'N/A')[:50]}",
            f"Layout: {vs.get('layout_type')}, Mode: {'complex(3)' if enable_complex else 'simple(1)'}"
        )
        
        self._log(f"✓ Blueprint ready: {vs.get('layout_type')} layout")
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "visual_strategy":
            return True, 0.95
        return False, 0.0
    
    def _generate_blueprint_simple(self, concepts: Dict, scene: Dict) -> Dict:
        """
        简单模式：规则生成blueprint（不调LLM）
        快速、可靠、不浪费token
        """
        colors = self._pick_colors(scene)
        entities = concepts.get("entities", [])
        layout_type = concepts.get("layout_type", "flow")
        core_topic = concepts.get("core_topic", "")
        visual_hint = concepts.get("visual_hint", "")
        relationships = concepts.get("relationships", [])
        
        return {
            "core_topic": core_topic,
            "diagram_description": visual_hint or f"{layout_type} diagram of {core_topic[:40]}",
            "entities": entities,
            "relationships": relationships,
            "layout_type": layout_type,
            "colors": colors,
            "animation_style": "sequential_reveal",
            "complexity": "low"
        }
    
    def _generate_blueprint_llm(self, concepts: Dict, scene: Dict, layout: Dict,
                                 color_scheme: Dict = None,
                                 layout_detailed: Dict = None,
                                 style_override: Dict = None) -> Dict:
        """
        LLM生成详细blueprint
        style_override: 竞演模式下的风格指令 {"name": "bold", "desc": "..."}
        """
        try:
            # Generate a richer palette — prioritize color_scheme from SceneAdapterAgent
            palette = self._pick_palette(scene, concepts.get("core_topic", ""),
                                          color_scheme=color_scheme)
            
            entities = concepts.get("entities", [])
            layout_type = concepts.get("layout_type", "flow")
            # If LayoutExpertAgent has chosen a better layout, use it
            if layout_detailed:
                layout_type = layout_detailed.get("layout_type", layout_type)
            core_topic = concepts.get("core_topic", "")
            relationships = concepts.get("relationships", [])
            
            # Extract Contexts
            design_guide = scene.get("design_guide", {})
            style_instruction = design_guide.get("svg_prompt", "Professional educational diagram")
            
            # 竞演模式: 注入风格指令
            if style_override:
                style_instruction = f"STYLE DIRECTIVE: {style_override['desc']}. Original hint: {style_instruction}"
            
            # Layout Constraints
            layout_str = "Full 1920x1080 Canvas"
            if layout:
                layout_str = (f"Constrained Region: x={layout.get('x', 0)}, y={layout.get('y', 0)}, "
                              f"w={layout.get('width', 1920)}, h={layout.get('height', 1080)}. "
                              f"Context: {layout.get('description', '')}")
            
            system_prompt = """You are a Visual Blueprint Designer for premium SVG motion graphics.

Transform abstract concepts into rich, symbolic visualizations with MEANINGFUL animations.

Output JSON:
{
  "core_topic": "Topic",
  "diagram_description": "Vivid description of the entire scene",
  "entities": [
    {
      "id": "e1",
      "label": "Satellite",
      "visual_type": "icon",
      "visual_description": "A simplified satellite with two rectangular solar panel wings extending left and right, a cylindrical body, and a small dish antenna on top. Draw using SVG path with clean line-art style, 2px stroke.",
      "suggested_color": "palette_accent_1",
      "animation_hint": "Slowly orbit around the central Earth entity"
    }
  ],
  "relationships": [{"from": "e1", "to": "e2", "label": "connection", "style": "dashed/solid/animated"}],
  "layout_type": "Choose the BEST layout for this content",
  "style_guide": {
     "visual_vibe": "Matches video style",
     "icon_style": "Line art/Filled/Tech"
  }
}

**CRITICAL RULES:**

1. **VISUAL DESCRIPTION** — Each entity MUST have 20+ word drawing instructions:
   - "Database" → "A 3D cylinder with an elliptical top and bottom, three horizontal divider lines, slightly tapered sides. Draw with <ellipse> for caps and <path> for sides."
   - "AI Brain" → "A brain outline with left/right hemispheres, internal circuit traces as thin lines, glowing dots at neural connection points"
   - "Server Rack" → "A tall rectangle with 5 horizontal slots, each with a small green LED dot on the right, ventilation grille lines at bottom"
   - "Shield/Security" → "A pointed shield shape with a checkmark or lock icon centered inside, subtle gradient fill"
   FORBIDDEN: "Standard shape", "circle icon", "basic shape", "simple representation"

2. **LAYOUT** — Choose layout to match content MEANING:
   - "flow": sequential process (A→B→C), timeline, pipeline
   - "hierarchy": tree structure, org chart, layered architecture
   - "radial": central concept with orbiting sub-concepts
   - "cycle": feedback loop, recurring process, lifecycle
   - "comparison": versus, before/after, pros/cons
   - "grid": matrix, feature table, categorized items
   - "scatter": free-form spatial, mind-map, abstract relationships
   DO NOT default to "flow" — pick the layout that best represents the SEMANTICS.

3. **ANIMATION HINTS** — Each entity should have `animation_hint` describing meaningful motion:
   - Planet entities → orbital motion
   - Data/information → flowing along connection paths
   - Growth metrics → bars growing upward
   - Processes → sequential fade-in reveal
   - Comparisons → slide in from opposite sides
   - Cycles → continuous rotation
   Generic "pulse" is OK but prefer SEMANTIC animations.

4. **COLOR VARIETY** — Use palette to differentiate semantic groups.
"""
            
            palette_str = ", ".join([f"{k}: {v}" for k, v in palette.items() if k.startswith('accent')])
            
            prompt = f"""Create a RICH visual blueprint for:
Core topic: "{core_topic}"
Entities: {entities}
Relationships: {relationships}
Suggested Layout: {layout_type} (override if another layout suits the content better)

**DESIGN CONTEXT:**
1. Style: {style_instruction}
2. Palette: {palette_str}
3. Background: {palette.get('background')}

**REQUIREMENTS**: 
- Each entity needs a DETAILED visual_description (20+ words, specific SVG drawing instructions)
- Each entity needs an animation_hint (what motion makes sense for this entity?)
- Choose layout_type based on content semantics, NOT just "flow"
- Assign varied colors from the palette

Return JSON only."""
            
            print("VisualStrategistAgent prompt:",prompt)
            result = self.invoke_llm(prompt, system_prompt)
            parsed = self.parse_json_response(result)
            
            # Ensure colors are preserved
            parsed["colors"] = palette
            
            # Explicitly add style guide for SVGCreator
            parsed["style_guide"] = {
                "visual_vibe": style_instruction,
                "description": parsed.get("diagram_description", style_instruction),
                "layout_description": layout_str,
                "text_style": design_guide.get("text_style", "sans-serif"),
                "recommended_bg": palette.get("background"),
                "recommended_accent": palette.get("primary")
            }
            
            # Backwards compatibility cleanup
            if "entities" in parsed and len(parsed["entities"]) > 0 and isinstance(parsed["entities"][0], dict):
                 # Keep the rich entity objects, but maybe SVGCreator expects strings?
                 # SVGCreator will need update. For now, let's keep 'entities' as the full list of dicts 
                 # and maybe add a simple_list for legacy components if needed.
                 # Actually, let's trust SVGCreator upgrade.
                 pass
            elif "entities" in parsed:
                 # If LLM returned strings, try to upgrade them (unlikely with new prompt)
                 pass

            # 补全缺失字段
            if not parsed.get("core_topic"): parsed["core_topic"] = core_topic
            if not parsed.get("layout_type"): parsed["layout_type"] = layout_type
            
            return parsed
            
        except Exception as e:
            self._log(f"LLM blueprint failed: {e}, using simple mode", "warning")
            return self._generate_blueprint_simple(concepts, scene)
    
    def _pick_palette(self, scene: Dict, topic: str, color_scheme: Dict = None) -> Dict:
        """Generate a multi-color palette — 优先使用 SceneAdapter 的动态配色"""
        # Priority 1: SceneAdapterAgent的color_scheme（始终有值，因为SceneAdapter在前面执行）
        if color_scheme:
            return {
                "background": color_scheme.get("background", "#0a192f"),
                "primary": color_scheme.get("accent_1", "#64ffda"),
                "accent_1": color_scheme.get("accent_1", "#64ffda"),
                "accent_2": color_scheme.get("accent_2", "#f07178"),
                "accent_3": color_scheme.get("accent_3", "#c3e88d"),
                "text": color_scheme.get("text", "#ccd6f6")
            }
        
        # Priority 2: scene_context
        if scene:
            design = scene.get("design_guide", {})
            color_hierarchy = scene.get("color_hierarchy", {})
            
            bg = design.get("recommended_bg") or color_hierarchy.get("background_color")
            primary = design.get("recommended_accent") or color_hierarchy.get("accent_color")
            text = design.get("recommended_text") or color_hierarchy.get("text_color")
            
            if bg or primary:
                bg = bg or "#0a192f"
                primary = primary or "#64ffda"
                text = text or "#ccd6f6"
                return {
                    "background": bg,
                    "primary": primary,
                    "accent_1": primary,
                    "accent_2": self._get_complementary(primary),
                    "accent_3": _lighten(primary, 0.3) if hasattr(self, '_lighten') else "#ffffff",
                    "text": text
                }
        
        # Priority 3: 兜底 — 不要用硬编码，用中性色让LLM自由发挥
        return {
            "background": "#0a192f",
            "primary": "#64ffda",
            "accent_1": "#64ffda",
            "accent_2": "#f07178",
            "accent_3": "#c3e88d",
            "text": "#ccd6f6"
        }
    
    def _get_complementary(self, hex_color: str) -> str:
        """互补色"""
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"#{255-r:02x}{255-g:02x}{255-b:02x}"
        except:
            return "#ff7043"

    def _pick_colors(self, scene: Dict) -> Dict:
        # Legacy support
        return self._pick_palette(scene, "")
    
    def _default_colors(self) -> Dict:
        """默认配色 — 不再使用 GitHub 暗色系硬编码"""
        return {
            "background": "#0a192f",
            "primary": "#64ffda",
            "secondary": "#8892b0",
            "text": "#ccd6f6"
        }
    
    def parse_json_response(self, response: str) -> Dict:
        import json
        try:
            response = response.strip()
            if response.startswith('```'):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
            response = response.replace('```json', '').replace('```', '').strip()
            return json.loads(response)
        except:
            return {}