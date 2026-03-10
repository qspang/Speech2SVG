"""
SVG Creator Agent
=================

SVG生成 - 从visual_blueprint生成SVG
画布: 1920x1080

核心修复: CSS transform 和 SVG transform 属性冲突
  - CSS @keyframes 中的 transform: translateY(0) 会覆盖 SVG transform="translate(x,y)"
  - 解决: 1) prompt 要求嵌套 <g> 分离定位和动画 2) 后处理移除 keyframes 中的 translate
"""

import os
import re
import math
from typing import Dict, Tuple, List, Optional
from base_agent import BaseAgent
from state import SVGState

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
VIEWBOX = f"0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}"

# Colors known to be LLM training bias that should be replaced
_LLM_BIAS_COLORS = [
    "#0f172a", "#0F172A",
    "#1e293b", "#1E293B",
    "#334155",
    "#0d1117", "#0D1117",  # GitHub 暗黑主题
    "#1a1a2e", "#1A1A2E",
]

# Diverse accent palette for fallback — 不含 #58a6ff/#d2a8ff 旧色
_ACCENT_PALETTE = [
    "#64ffda", "#f07178", "#c3e88d", "#ff7b72",
    "#00bcd4", "#f778ba", "#ffa657", "#e17055",
]


class SVGCreatorAgent(BaseAgent):
    """SVG创建Agent"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("svg_creator", llm_type)
        self.role_description = "Generate SVG from visual blueprint"
        self.capabilities = ["svg_generation", "animation_coding"]
    
    def execute(self, state: SVGState) -> SVGState:
        """执行SVG生成"""
        self._log("Generating SVG from blueprint...")
        
        blueprint = state.get("visual_strategy", {})
        colors = blueprint.get("colors", {})
        
        max_retries = 3
        svg_content = None
        enable_complex = state.get("enable_complex_mode", False)
        
        for attempt in range(max_retries):
            try:
                if enable_complex:
                    svg_content = self._generate_dual_track(state)
                else:
                    svg_content = self._generate_from_blueprint(state)
                # Post-processing pipeline (顺序很重要):
                svg_content = self._extract_svg(svg_content)
                svg_content = self._light_post_process(svg_content)
                svg_content = self._fix_all_css_bugs(svg_content)
                svg_content = self._enforce_color_palette(svg_content, colors,
                                                          color_scheme=state.get("color_scheme"))
                
                if self._validate_svg_structure(svg_content):
                    self._log(f"✓ SVG generated (attempt {attempt + 1})")
                    break
                else:
                    self._log(f"⚠ Invalid SVG (attempt {attempt + 1}/{max_retries})", "warning")
            except Exception as e:
                self._log(f"✗ Generation error: {e}", "error")
                if attempt == max_retries - 1:
                    svg_content = None
        
        if not svg_content or not self._validate_svg_structure(svg_content):
            self._log("Using fallback SVG", "warning")
            svg_content = self._create_fallback_svg(blueprint)
        
        state["current_svg"] = svg_content
        
        if state.get("output_dir"):
            svg_path = self._save_svg(svg_content, state)
            state["svg_path"] = svg_path
            png_path = self._render_svg_to_png(svg_path, state)
            if png_path:
                state["svg_png_path"] = png_path
        
        state["svg_history"].append({
            "iteration": state.get("iteration", 0),
            "svg": svg_content,
            "timestamp": __import__("time").time()
        })
        
        self.record_decision(
            state, "svg_generation",
            f"Generated {len(svg_content)} chars",
            f"Blueprint-driven with CSS transform fix"
        )
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "svg_generation":
            return True, 0.9
        return False, 0.0
    
    # ═══════════════════════════════════════════════════════════════
    # CSS Bug Fix (核心修复 — 3个独立bug)
    # ═══════════════════════════════════════════════════════════════
    
    def _fix_all_css_bugs(self, svg_content: str) -> str:
        """
        修复 LLM 生成的 SVG 中 3 个常见 CSS 致命 bug:
        
        Bug 1 — 元素永远不可见 (opacity: 0 锁死):
          .delay-1 { animation-name: fadeIn; opacity: 0; }
          .breathe  { animation: breathe 6s infinite; }  ← shorthand 覆盖 fadeIn!
          结果: fadeIn 永远不执行, opacity: 0 永远不消失
        
        Bug 2 — 元素跑到左上角 (transform 覆盖):
          CSS @keyframes { transform: translateY(0) } 覆盖 SVG transform="translate(960,540)"
        
        Bug 3 — animation-fill-mode 被 shorthand 重置:
          animation shorthand 重置 fill-mode, 导致 forwards 失效
        
        修复策略:
          1. 从 CSS 选择器中移除 opacity: 0 (不影响 @keyframes 中的)
          2. 从 CSS 中移除 translate 相关的 transform
          3. 注入安全规则保证所有 g 元素可见
        """
        if not svg_content:
            return svg_content
        
        style_match = re.search(r'(<style[^>]*>)(.*?)(</style>)', svg_content, re.DOTALL)
        if not style_match:
            return svg_content
        
        css = style_match.group(2)
        original_css = css
        fixes_applied = []
        
        # ── Fix 1: 保护 @keyframes 块, 然后从普通选择器中移除 opacity: 0 ──
        keyframe_blocks = []
        def save_keyframe(match):
            keyframe_blocks.append(match.group(0))
            return f'__KEYFRAME_{len(keyframe_blocks)-1}__'
        
        # 临时替换 @keyframes 块
        css_work = re.sub(
            r'@keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}',
            save_keyframe,
            css
        )
        
        # 从普通选择器中移除 opacity: 0
        css_before = css_work
        css_work = re.sub(r'\bopacity\s*:\s*0\s*;?', '', css_work)
        if css_work != css_before:
            fixes_applied.append('opacity:0')
        
        # 从普通选择器中移除 transform: translate*
        css_before = css_work
        css_work = re.sub(r'\btransform\s*:\s*translate[XYxy]?\([^)]*\)\s*;?', '', css_work)
        if css_work != css_before:
            fixes_applied.append('translate-in-selectors')
        
        # 恢复 @keyframes 块
        for i, block in enumerate(keyframe_blocks):
            css_work = css_work.replace(f'__KEYFRAME_{i}__', block)
        
        # ── Fix 2: 从 @keyframes 内移除 translate (防止覆盖 SVG transform) ──
        css_before = css_work
        css_work = re.sub(
            r'\btransform\s*:\s*translate[XYxy]?\([^)]*\)\s*;?',
            '',
            css_work
        )
        if css_work != css_before:
            fixes_applied.append('translate-in-keyframes')
        
        # ── Fix 3: 注入安全规则 — 保证所有元素在动画完成后可见 ──
        safety_css = """
      /* SAFETY: Force all entities visible after animation */
      svg g > g { opacity: 1; }"""
        
        if safety_css.strip() not in css_work:
            css_work += safety_css
            fixes_applied.append('safety-visibility')
        
        # 清理多余空行
        css_work = re.sub(r'\n\s*\n\s*\n', '\n\n', css_work)
        
        if fixes_applied:
            self._log(f"CSS fixes applied: {', '.join(fixes_applied)}", "info")
            svg_content = svg_content[:style_match.start(2)] + css_work + svg_content[style_match.end(2):]
        
        # ── Fix 4: 内联 style 中的 transform: translate... ──
        svg_content = re.sub(
            r'(style="[^"]*?)\s*transform\s*:\s*translate[^;"]*;?\s*',
            r'\1',
            svg_content
        )
        
        # ── Fix 5: 移除元素上的 opacity="0" 属性 ──
        svg_content = re.sub(
            r'\s+opacity\s*=\s*["\']0["\']',
            '',
            svg_content
        )
        
        return svg_content
    
    # ═══════════════════════════════════════════════════════════════
    # Color Enforcement (Post-Processing)
    # ═══════════════════════════════════════════════════════════════
    
    def _enforce_color_palette(self, svg_content: str, colors: Dict,
                                color_scheme: Dict = None) -> str:
        """替换 LLM 偏好的默认颜色，优先使用 SceneAdapter 的 color_scheme
        
        修复：不仅替换背景色，还替换 #58a6ff (蓝) 和 #d2a8ff (紫) 强调色
        """
        if not svg_content:
            return svg_content
        
        # 优先级: color_scheme (SceneAdapter) > blueprint colors > 默认
        if color_scheme:
            bg_color = color_scheme.get("background", "#0d1117")
            accent_1 = color_scheme.get("accent_1", colors.get("primary", "#64ffda"))
            accent_2 = color_scheme.get("accent_2", colors.get("accent_2", "#f07178"))
            accent_3 = color_scheme.get("accent_3", colors.get("accent_3", "#c3e88d"))
            text_color = color_scheme.get("text", colors.get("text", "#ccd6f6"))
        elif colors:
            bg_color = colors.get("background", "#0d1117")
            accent_1 = colors.get("primary", "#64ffda")
            accent_2 = colors.get("accent_2", "#f07178")
            accent_3 = colors.get("accent_3", "#c3e88d")
            text_color = colors.get("text", "#ccd6f6")
        else:
            bg_color = "#0d1117"
            accent_1 = "#64ffda"
            accent_2 = "#f07178"
            accent_3 = "#c3e88d"
            text_color = "#ccd6f6"
        
        # === 1. 替换 LLM bias 背景色 ===
        for bias_color in _LLM_BIAS_COLORS:
            svg_content = svg_content.replace(bias_color, bg_color)
        
        # 关键: 如果目标背景不是常见暗色，也要替换它们
        if bg_color.lower() != "#0d1117":
            svg_content = svg_content.replace("#0d1117", bg_color)
            svg_content = svg_content.replace("#0D1117", bg_color)
        
        if bg_color.lower() != "#1a1a2e":
            svg_content = svg_content.replace("#1a1a2e", bg_color)
            svg_content = svg_content.replace("#1A1A2E", bg_color)
        
        # === 2. 替换 LLM bias 强调色 (#58a6ff 蓝 + #d2a8ff 紫) ===
        _ACCENT_BIAS = {
            "#58a6ff": accent_1,
            "#58A6FF": accent_1,
            "#d2a8ff": accent_2,
            "#D2A8FF": accent_2,
            # GitHub 暗色系文字色
            "#f0f6fc": text_color,
            "#F0F6FC": text_color,
            "#8b949e": accent_3,
            "#8B949E": accent_3,
        }
        for bias, replacement in _ACCENT_BIAS.items():
            if bias.lower() != replacement.lower():
                svg_content = svg_content.replace(bias, replacement)
        
        # === 3. 替换 CSS 中的 rgba 版本 ===
        # rgba(88, 166, 255, ...) → accent_1 的 rgba 版本
        # rgba(210, 168, 255, ...) → accent_2 的 rgba 版本
        import re
        
        def _hex_to_rgb_tuple(hex_c: str):
            h = hex_c.lstrip("#")
            if len(h) != 6:
                return (128, 128, 128)
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        
        a1_r, a1_g, a1_b = _hex_to_rgb_tuple(accent_1)
        a2_r, a2_g, a2_b = _hex_to_rgb_tuple(accent_2)
        
        # 替换 rgba(88, 166, 255, X) → rgba(accent_1_r, accent_1_g, accent_1_b, X)
        svg_content = re.sub(
            r'rgba\(\s*88\s*,\s*166\s*,\s*255\s*,\s*([^)]+)\)',
            lambda m: f'rgba({a1_r}, {a1_g}, {a1_b}, {m.group(1).strip()})',
            svg_content
        )
        # 替换 rgba(210, 168, 255, X) → rgba(accent_2_r, accent_2_g, accent_2_b, X)
        svg_content = re.sub(
            r'rgba\(\s*210\s*,\s*168\s*,\s*255\s*,\s*([^)]+)\)',
            lambda m: f'rgba({a2_r}, {a2_g}, {a2_b}, {m.group(1).strip()})',
            svg_content
        )
        
        return svg_content
    
    # ═══════════════════════════════════════════════════════════════
    # Core Generation
    # ═══════════════════════════════════════════════════════════════
    
    def _generate_from_blueprint(self, state: SVGState) -> str:
        """核心：从vvisual_blueprint生成SVG——布局完全由LLM决定"""
        blueprint = state.get("visual_strategy", {})
        
        core_topic = blueprint.get("core_topic", "Visualization")
        entities = blueprint.get("entities", [])
        relationships = blueprint.get("relationships", [])
        layout_type = blueprint.get("layout_type", "flow")
        diagram_desc = blueprint.get("diagram_description", "")
        colors = blueprint.get("colors", {})
        special = blueprint.get("special_instructions", "")
        
        bg_color = colors.get("background", "#0a192f")
        primary_color = colors.get("primary", "#64ffda")
        accent_color = colors.get("accent_2", colors.get("accent_1", "#f07178"))
        
        # Get color scheme mode for background opacity guidance
        color_scheme = state.get("color_scheme", {})
        bg_mode = color_scheme.get("mode", "dark")
        bg_opacity = color_scheme.get("background_opacity", 0.92)
        overlay_style = color_scheme.get("overlay_style", "dark-solid")
        
        color_section = f"""COLOR PALETTE (MUST USE — adapted from video scene, mode={bg_mode}):
  Background: {bg_color} (opacity: {bg_opacity})
  Primary: {primary_color}
  Secondary: {colors.get("accent_2", accent_color)}
  Accent: {colors.get("accent_3", "#c3e88d")}
  Text: {colors.get("text", "#ccd6f6")}
  Overlay style: {overlay_style}
  ⚠️ Background color is derived from VIDEO FRAME analysis. Do NOT override it!
  ⚠️ Use ALL colors in the palette — vary icon colors, do NOT use the same color for every element!
  FORBIDDEN: #0f172a, #1e293b, #334155, #0d1117, #58a6ff, #d2a8ff"""

        # Build entity descriptions
        # Get entity icons from IconDesignerAgent
        entity_icons = state.get("entity_icons", {})
        
        entity_lines = []
        for i, entity in enumerate(entities):
            if isinstance(entity, dict):
                label = entity.get("label", f"Entity{i+1}")
                vis_desc = entity.get("visual_description", entity.get("description", ""))
                icon_snippet = entity_icons.get(label, "")
                line = f"  {i+1}. \"{label}\""
                if vis_desc:
                    line += f" — {vis_desc[:80]}"
                if icon_snippet:
                    line += f"\n     ICON SVG (MUST USE): {icon_snippet}"
                entity_lines.append(line)
            else:
                label = str(entity)
                icon_snippet = entity_icons.get(label, "")
                line = f"  {i+1}. \"{entity}\""
                if icon_snippet:
                    line += f"\n     ICON SVG (MUST USE): {icon_snippet}"
                entity_lines.append(line)
        entity_text = "\n".join(entity_lines)
        
        # Relationships
        rel_text = ""
        if relationships:
            rel_lines = []
            for r in relationships[:6]:
                if isinstance(r, dict):
                    fr = r.get("from", "")
                    to = r.get("to", "")
                    lbl = r.get("label", "→")
                    rel_lines.append(f"  {fr} --[{lbl}]--> {to}")
            rel_text = "\n".join(rel_lines)
        
        # Get entity positions from LayoutExpertAgent
        layout_plan = state.get("layout_plan_detailed", {})
        entity_positions = layout_plan.get("entity_positions", [])
        position_section = ""
        if entity_positions:
            pos_lines = []
            for ep in entity_positions:
                pos_lines.append(f"  • \"{ep.get('label', '?')}\" → suggested position ({ep['x']}, {ep['y']})")
            position_section = "\nSUGGESTED POSITIONS (from layout algorithm, you may fine-tune):\n" + "\n".join(pos_lines)
            position_section += f"\n  Connection style: {layout_plan.get('connection_style', 'straight')}"
        
        style_guide = blueprint.get("style_guide", {})
        if not style_guide:
            scene_ctx = state.get("scene_context", {})
            design_guide = scene_ctx.get("design_guide", {})
            style_guide = {
                "visual_vibe": design_guide.get("svg_prompt", "Professional, clear"),
                "text_style": design_guide.get("text_style", "sans-serif")
            }

        system_prompt = f"""You are an Expert SVG Illustrator creating premium motion graphics.
Canvas: 1920x1080. Output raw SVG only.

═══ CSS SAFETY RULES (elements will be INVISIBLE if violated) ═══
1. NEVER set opacity: 0 in CSS classes (only inside @keyframes from {{ }})
2. NEVER use animation shorthand if another class sets animation-name
3. NEVER use transform: translate in @keyframes
4. Use nested <g>: outer for position, inner for animation
   <g transform="translate(X, Y)">     ← position only
     <g style="animation: fadeIn 1s forwards"> ← animation only
       ...content...
     </g>
   </g>

═══ LAYOUT RULES ═══
YOU decide the layout. The requested type is "{layout_type}", but YOU choose the
best spatial arrangement for the content. Use the FULL 1920x1080 canvas:
  - Entity safe zone: X from 150 to 1770, Y from 150 to 930
  - Center: (960, 540)
  - Distribute entities across the canvas — NEVER cluster in one area
  - Leave room for labels (text below/beside each entity)
  - Connections go between entities, not through them

═══ ICON DESIGN GUIDE ═══
Draw DETAILED, RECOGNIZABLE icons using SVG <path> elements. NOT just circles/rectangles.

SIZE: Each icon should be approximately 80-120px wide/tall.
STYLE: Clean line-art with 2-3px stroke, optionally with subtle fills.
COLORS: Use the colors from the COLOR PALETTE above. Use Primary for main strokes, Secondary/Accent for highlights.
         VARY the colors across different icons — do NOT use the same color for every icon!

EXAMPLE — How to draw a "Database" icon (cylinder shape):
  <ellipse cx="0" cy="-25" rx="30" ry="10" fill="none" stroke="{primary_color}" stroke-width="2"/>
  <path d="M-30,-25 L-30,25" stroke="{primary_color}" stroke-width="2"/>
  <path d="M30,-25 L30,25" stroke="{primary_color}" stroke-width="2"/>
  <ellipse cx="0" cy="25" rx="30" ry="10" fill="none" stroke="{primary_color}" stroke-width="2"/>
  <line x1="-20" y1="0" x2="20" y2="0" stroke="{primary_color}" stroke-width="1" opacity="0.5"/>

EXAMPLE — How to draw a "Brain" icon (use a DIFFERENT accent color):
  <path d="M0,-30 C-20,-30 -35,-15 -35,5 C-35,20 -25,30 -10,35 C-5,37 0,35 5,37
           C20,30 35,20 35,5 C35,-15 20,-30 0,-30Z"
        fill="none" stroke="{accent_color}" stroke-width="2"/>
  <path d="M0,-20 C-8,-10 -8,10 0,20" fill="none" stroke="{accent_color}" stroke-width="1.5" opacity="0.6"/>
  <path d="M-15,0 L15,0" stroke="{accent_color}" stroke-width="1" opacity="0.4"/>

IMPORTANT: Each icon should use a DIFFERENT color from the palette!
DO NOT use generic shapes (plain circle, rectangle, triangle). Each icon must be SPECIFIC
to what it represents — a server looks like a rack, a person looks like a silhouette, etc.

═══ ANIMATION GUIDE ═══
Create MEANINGFUL animations that match the content semantics:

- “Satellite orbiting Earth” → @keyframes orbit {{ 0% {{ transform: rotate(0deg) }} 100% {{ transform: rotate(360deg) }} }}
  Apply on a wrapper <g> around the satellite with transform-origin at the Earth center.
- “Data flowing” → animate stroke-dashoffset on a dashed path line
- “Growth/Scaling” → animate a bar chart growing: @keyframes grow {{ from {{ transform: scaleY(0) }} to {{ transform: scaleY(1) }} }}
- “Pulse/Heartbeat” → @keyframes pulse {{ 0%,100% {{ filter: brightness(1) }} 50% {{ filter: brightness(1.4) }} }}
- “Connection established” → draw a line with stroke-dashoffset animation
- “Fade in reveal” → @keyframes fadeIn {{ from {{ opacity: 0 }} to {{ opacity: 1 }} }}

IMPORTANT: Animations using transform (rotate, scale) MUST be on elements that do NOT
have a SVG transform="translate()" attribute. Use a SEPARATE nested wrapper <g> for animation.

Animate ONLY the inner content, not the positioning <g>.
"""

        prompt = f"""Create a premium SVG illustration:

TOPIC: {core_topic}
CONCEPT: {diagram_desc}
LAYOUT: {layout_type} (you decide the best spatial arrangement)

{color_section}
{position_section}

ENTITIES:
{entity_text}

CONNECTIONS:
{rel_text if rel_text else '  Connect entities with styled paths/arrows'}

STYLE:
  Vibe: {style_guide.get('visual_vibe', 'Professional')}
  Font: {style_guide.get('text_style', 'sans-serif')}
{f'  Special: {special}' if special else ''}

Draw each entity as a DETAILED icon with label text. Use contextual animations.
Background: <rect width="1920" height="1080" fill="{bg_color}" opacity="{bg_opacity}"/>
Output SVG code directly."""

        try:
            result = self.invoke_llm(prompt, system_prompt)
            return result
        except Exception as e:
            self._log(f"Generation failed: {e}", "error")
            return self._create_fallback_svg(blueprint)
    
    def _generate_dual_track(self, state: SVGState) -> str:
        """双轨生产: GeometryCoder(静态结构) + MotionCoder(CSS动画) 分离"""
        self._log("  Dual-track: Geometry → Motion")
        
        blueprint = state.get("visual_strategy", {})
        entities = blueprint.get("entities", [])
        relationships = blueprint.get("relationships", [])
        colors = blueprint.get("colors", {})
        layout_type = blueprint.get("layout_type", "flow")
        core_topic = blueprint.get("core_topic", "Visualization")
        diagram_desc = blueprint.get("diagram_description", "")
        
        bg_color = colors.get("background", "#0a192f")
        primary = colors.get("primary", "#64ffda")
        text_color = colors.get("text", "#ccd6f6")
        
        # 获取图标和位置
        entity_icons = state.get("entity_icons", {})
        layout_plan = state.get("layout_plan_detailed", {})
        entity_positions = layout_plan.get("entity_positions", [])
        
        color_scheme = state.get("color_scheme", {})
        bg_opacity = color_scheme.get("background_opacity", 0.92)
        
        # 构建实体描述（带图标和位置）
        entity_parts = []
        for i, entity in enumerate(entities):
            label = entity if isinstance(entity, str) else entity.get("label", f"E{i}")
            icon = entity_icons.get(label, "")
            pos = entity_positions[i] if i < len(entity_positions) else {"x": 200 + i * 300, "y": 400}
            
            part = f'Entity #{i+1}: "{label}" at ({pos["x"]}, {pos["y"]})'
            if icon:
                part += f"\n  Icon SVG: {icon}"
            entity_parts.append(part)
        
        entity_desc = "\n".join(entity_parts)
        
        # ═══ Step 1: GeometryCoder — 静态结构 ═══
        geo_system = f"""You are a Geometry Coder. Generate STATIC SVG structure ONLY.
Canvas: 1920x1080. NO ANIMATIONS, NO @keyframes, NO CSS animation properties.

RULES:
1. Background: <rect width="1920" height="1080" fill="{bg_color}" opacity="{bg_opacity}"/>
2. Each entity gets a unique id: id="node-{{label-lowercase}}"
3. Use nested <g> for each entity: <g id="node-xyz" transform="translate(X, Y)">
4. Draw icons using the provided SVG snippets — place them inside the entity <g>
5. Add <text> labels below each icon
6. Draw connection lines/paths between entities
7. All colors from palette: bg={bg_color}, primary={primary}, text={text_color}
8. DO NOT include any <style> block or animations

Output raw SVG only."""

        geo_prompt = f"""Static SVG for: {core_topic}
Description: {diagram_desc}
Layout: {layout_type}

{entity_desc}

Connections: {', '.join([f'{r.get("from","?")}→{r.get("to","?")}' for r in relationships[:6] if isinstance(r, dict)])}

Draw the complete static SVG structure. NO animations."""

        try:
            self._log("    Step 1: GeometryCoder...")
            static_svg = self.invoke_llm(geo_prompt, geo_system)
            static_svg = self._extract_svg(static_svg)
            
            if not static_svg or '<svg' not in static_svg:
                self._log("    GeometryCoder failed, falling back", "warning")
                return self._generate_from_blueprint(state)
            
            # ═══ Step 2: MotionCoder — CSS动画注入 ═══
            motion_system = """You are a Motion Choreographer. Add CSS animations to an existing SVG.

RULES:
1. You receive a complete static SVG — DO NOT change the structure or positions
2. Add a <style> block with @keyframes and animation classes
3. Reference elements by their existing id attributes
4. Animation types to consider:
   - fadeIn: elements appear sequentially with delays
   - pulse: glowing/breathing effect on important nodes
   - dataFlow: stroke-dashoffset animation on connection lines
   - float: gentle up/down movement for emphasis
   - orbit: rotation around a center point (use transform-origin)
5. CSS SAFETY: 
   - NEVER use transform: translate in @keyframes
   - NEVER set opacity: 0 in class definitions (only in @keyframes from{})
   - Apply animation via style="animation: ..." on wrapper <g> elements
6. Add staggered delays for sequential reveal effect

Output the COMPLETE SVG (structure + animations). Output raw SVG only."""

            motion_prompt = f"""Add meaningful animations to this SVG:

TOPIC: {core_topic}
DESCRIPTION: {diagram_desc}

EXISTING SVG:
{static_svg}

Add CSS animations that match the content semantics. Output the complete SVG with animations."""

            self._log("    Step 2: MotionCoder...")
            animated_svg = self.invoke_llm(motion_prompt, motion_system)
            
            if animated_svg and '<svg' in animated_svg:
                return animated_svg
            else:
                self._log("    MotionCoder failed, using static SVG", "warning")
                return static_svg
                
        except Exception as e:
            self._log(f"    Dual-track failed: {e}, fallback to single-step", "warning")
            return self._generate_from_blueprint(state)

    # ═══════════════════════════════════════════════════════════════
    # Post-Processing
    # ═══════════════════════════════════════════════════════════════

    def _light_post_process(self, svg_content: str) -> str:
        """轻量后处理 - 修复结构"""
        if not svg_content:
            return svg_content
            
        svg_content = re.sub(r'@import\s+url\s*\([^)]+\)\s*;', '', svg_content)
        
        if 'xmlns=' not in svg_content:
            svg_content = re.sub(
                r'<svg([^>]*)>',
                r'<svg xmlns="http://www.w3.org/2000/svg"\1>',
                svg_content, count=1
            )
            
        if 'viewBox=' not in svg_content:
            svg_content = re.sub(
                r'<svg([^>]*)>',
                f'<svg\\1 viewBox="{VIEWBOX}">',
                svg_content, count=1
            )
        
        if 'preserveAspectRatio=' not in svg_content:
            svg_content = re.sub(
                r'<svg([^>]*)>',
                r'<svg\1 preserveAspectRatio="xMidYMid meet">',
                svg_content, count=1
            )
        
        svg_content = re.sub(r'(<svg[^>]*)\s+width=["\'][^"\']*["\']', r'\1', svg_content)
        svg_content = re.sub(r'(<svg[^>]*)\s+height=["\'][^"\']*["\']', r'\1', svg_content)
        
        return svg_content
    
    def _extract_svg(self, text: str) -> str:
        """Extract SVG from LLM output"""
        text = text.replace('```svg', '').replace('```xml', '').replace('```', '')
        text = re.sub(r'<layout_calculation>.*?</layout_calculation>', '', text, flags=re.DOTALL)
        
        match = re.search(r'<svg.*?</svg>', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(0).strip()
        return text.strip()
    
    def _validate_svg_structure(self, svg: str) -> bool:
        if not svg or len(svg) < 50:
            return False
        if '<svg' not in svg.lower() or '</svg>' not in svg.lower():
            return False
        content_tags = ['<rect', '<circle', '<path', '<line', '<polygon', '<text', '<g']
        return any(tag in svg for tag in content_tags)
    
    # ═══════════════════════════════════════════════════════════════
    # Fallback SVG (Python-generated, guaranteed correct)
    # ═══════════════════════════════════════════════════════════════
    
    def _create_fallback_svg(self, blueprint: Dict) -> str:
        """Python构建的fallback SVG — 保证布局正确，无CSS transform冲突"""
        core_topic = blueprint.get("core_topic", "Visualization")
        entities = blueprint.get("entities", ["Concept"])[:6]
        colors = blueprint.get("colors", {})
        layout_type = blueprint.get("layout_type", "flow")
        
        bg = colors.get("background", "#0a192f")
        primary = colors.get("primary", "#64ffda")
        secondary = colors.get("secondary", "#8892b0")
        text_col = colors.get("text", "#ccd6f6")
        
        safe_topic = self._sanitize_text(core_topic[:50])
        
        # Simple inline layout for fallback (no longer using _calculate_layout_anchors)
        n = len(entities) or 1
        margin_x = 250
        usable_w = CANVAS_WIDTH - 2 * margin_x
        cy = CANVAS_HEIGHT // 2
        anchors = []
        for i in range(n):
            entity = entities[i] if i < len(entities) else f"Node{i+1}"
            label = entity if isinstance(entity, str) else entity.get("label", f"Node{i+1}")
            x = margin_x + int(i * usable_w / max(n - 1, 1)) if n > 1 else CANVAS_WIDTH // 2
            anchors.append({"label": label, "x": x, "y": cy})
        
        nodes_svg = []
        lines_svg = []
        
        for i, anchor in enumerate(anchors):
            x, y = anchor["x"], anchor["y"]
            label = anchor["label"]
            safe_ent = self._sanitize_text(label[:20]) if isinstance(label, str) else f"Node{i+1}"
            delay = 0.2 + i * 0.3
            accent = _ACCENT_PALETTE[i % len(_ACCENT_PALETTE)]
            
            nodes_svg.append(f'''  <g transform="translate({x}, {y})">
    <g style="animation: fadeIn 0.8s ease-out {delay:.1f}s forwards;">
      <circle cx="0" cy="0" r="50" fill="none" stroke="{accent}" stroke-width="2.5" filter="url(#glow)"/>
      <text x="0" y="5" font-family="sans-serif" font-size="24" fill="{accent}" text-anchor="middle" font-weight="bold">{safe_ent[0].upper()}</text>
      <text x="0" y="70" font-family="sans-serif" font-size="20" fill="{text_col}" text-anchor="middle" font-weight="600">{safe_ent}</text>
    </g>
  </g>''')
            
            if i < len(anchors) - 1:
                nx, ny = anchors[i + 1]["x"], anchors[i + 1]["y"]
                lines_svg.append(
                    f'  <line x1="{x+55}" y1="{y}" x2="{nx-55}" y2="{ny}" '
                    f'stroke="{secondary}" stroke-width="1.5" stroke-dasharray="8,4" '
                    f'marker-end="url(#arrow)" style="animation: drawLine 1.5s ease-out {delay + 0.15:.1f}s forwards;"/>'
                )
        
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" preserveAspectRatio="xMidYMid meet">
  <defs>
    <style>
      @keyframes fadeIn {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
      }}
      @keyframes drawLine {{
        from {{ stroke-dashoffset: 500; }}
        to {{ stroke-dashoffset: 0; }}
      }}
      svg g > g {{ opacity: 1; }} /* Safety */
    </style>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0,0 10,3.5 0,7" fill="{secondary}"/>
    </marker>
  </defs>
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="{bg}"/>
  <text x="960" y="100" font-family="sans-serif" font-size="40" font-weight="bold" 
        fill="{primary}" text-anchor="middle">{safe_topic}</text>
{chr(10).join(lines_svg)}
{chr(10).join(nodes_svg)}
</svg>'''
    
    # ═══════════════════════════════════════════════════════════════
    # File I/O & Rendering
    # ═══════════════════════════════════════════════════════════════
    
    def _save_svg(self, svg_content: str, state: SVGState) -> str:
        output_dir = state.get("output_dir")
        sample_id = state.get("sample_id", "output")
        filepath = os.path.join(output_dir, f"{sample_id}.svg")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        print(f"  Saved SVG: file://{os.path.abspath(filepath)}")
        return filepath
    
    def _render_svg_to_png(self, svg_path: str, state: SVGState) -> str:
        try:
            from playwright.async_api import async_playwright
            import asyncio
            
            png_path = svg_path.replace('.svg', '.png')
            temp_html = svg_path + '_temp.html'
            
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg = f.read()
            
            html = f'<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{{margin:0;background:#000;display:flex;justify-content:center;align-items:center;min-height:100vh}}svg{{max-width:100%;height:auto}}</style></head><body>{svg}</body></html>'
            
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(html)
            
            async def render():
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    page = await browser.new_page()
                    await page.set_viewport_size({"width": 1920, "height": 1080})
                    await page.goto(f"file:///{os.path.abspath(temp_html).replace(os.sep, '/')}")
                    await page.wait_for_timeout(1000)
                    loc = page.locator("svg").first
                    if await loc.count() > 0:
                        await loc.screenshot(path=png_path)
                    else:
                        await page.screenshot(path=png_path)
                    await browser.close()
            
            asyncio.run(render())
            if os.path.exists(temp_html):
                os.remove(temp_html)
            return png_path if os.path.exists(png_path) else None
        except:
            return None
    
    def _sanitize_text(self, text: str) -> str:
        for old, new in [('&','&amp;'), ('<','&lt;'), ('>','&gt;'), ('"','&quot;'), ("'",'&apos;')]:
            text = text.replace(old, new)
        return text
    
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