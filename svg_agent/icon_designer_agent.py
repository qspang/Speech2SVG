"""
Icon Designer Agent
====================

图标专家Agent — 为每个实体生成语义精确的SVG图标片段

输入: state["concepts"]["entities"]
输出: state["entity_icons"]: {entity_label: svg_snippet}

核心职责: 确保图标能准确表达实体的语义，而非只是简单圆圈/方块
"""

from typing import Dict, List, Tuple
from base_agent import BaseAgent
from state import SVGState


class IconDesignerAgent(BaseAgent):
    """图标设计专家Agent — 为实体生成语义精确的SVG图标"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("icon_designer", llm_type)
        self.role_description = "Design semantically accurate SVG icons for entities"
        self.capabilities = ["icon_design", "svg_path_generation"]
    
    def execute(self, state: SVGState) -> SVGState:
        """为每个实体生成图标SVG片段"""
        self._log("Designing entity icons...")
        
        concepts = state.get("concepts", {})
        entities = concepts.get("entities", [])
        color_scheme = state.get("color_scheme", {})
        
        primary_color = color_scheme.get("accent_1", "#64ffda")
        secondary_color = color_scheme.get("accent_2", "#f07178")
        tertiary_color = color_scheme.get("accent_3", "#c3e88d")
        
        if not entities:
            state["entity_icons"] = {}
            return state
        
        # 批量生成所有实体的图标，传入完整调色板
        entity_icons = self._design_icons_batch(
            entities, primary_color, secondary_color, tertiary_color
        )
        
        state["entity_icons"] = entity_icons
        
        self._log(f"✓ Designed {len(entity_icons)} icons")
        
        self.record_decision(
            state, "icon_design",
            f"Generated {len(entity_icons)} icons",
            f"Entities: {', '.join(list(entity_icons.keys())[:5])}"
        )
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "icon_design":
            return True, 0.95
        return False, 0.0
    
    def _design_icons_batch(self, entities: List, primary: str, secondary: str, tertiary: str = "#c3e88d") -> Dict[str, str]:
        """批量为所有实体生成图标 — 使用多色调色板"""
        entity_labels = []
        for e in entities:
            if isinstance(e, str):
                entity_labels.append(e)
            elif isinstance(e, dict):
                entity_labels.append(e.get("label", e.get("name", "Unknown")))
        
        if not entity_labels:
            return {}
        
        entity_list = "\n".join([f"  {i+1}. {label}" for i, label in enumerate(entity_labels)])
        
        system_prompt = f"""You are an expert SVG Icon Designer. Your job is to create SEMANTICALLY ACCURATE 
SVG icons that visually represent the meaning of each concept.

ICON REQUIREMENTS:
1. Each icon MUST visually convey what the entity means (e.g., "Database" = cylinder shape, "Brain" = brain outline, "Cloud" = cloud shape)
2. Use SVG <path>, <circle>, <rect>, <ellipse>, <line>, <polyline>, <polygon> elements
3. Each icon should be drawn at origin (0,0) with size roughly 80-120px
4. Use stroke-based design with stroke-width="2" for clean look
5. Available colors:
   - Color A: {primary}
   - Color B: {secondary}
   - Color C: {tertiary}
6. IMPORTANT: VARY the colors! Assign DIFFERENT colors to DIFFERENT icons:
   - Icon 1 should use Color A ({primary})
   - Icon 2 should use Color B ({secondary})
   - Icon 3 should use Color C ({tertiary})
   - And cycle through for more icons
7. DO NOT use text elements in icons — icons are purely graphical

SEMANTIC ICON EXAMPLES:
- "Server/Computer": Draw a monitor shape with a stand
  <rect x="-35" y="-30" width="70" height="50" rx="4" fill="none" stroke="{{color}}" stroke-width="2"/>
  <line x1="-15" y1="20" x2="15" y2="20" stroke="{{color}}" stroke-width="2"/>
  <line x1="0" y1="20" x2="0" y2="35" stroke="{{color}}" stroke-width="2"/>
  <line x1="-20" y1="35" x2="20" y2="35" stroke="{{color}}" stroke-width="2"/>

- "Database": Draw a cylinder
  <ellipse cx="0" cy="-25" rx="30" ry="10" fill="none" stroke="{{color}}" stroke-width="2"/>
  <path d="M-30,-25 L-30,25" stroke="{{color}}" stroke-width="2"/>
  <path d="M30,-25 L30,25" stroke="{{color}}" stroke-width="2"/>
  <ellipse cx="0" cy="25" rx="30" ry="10" fill="none" stroke="{{color}}" stroke-width="2"/>

- "Brain/AI/Intelligence": Draw a brain outline
  <path d="M0,-35 C-20,-35 -35,-20 -35,-5 C-35,5 -30,15 -20,20 C-25,25 -20,35 -10,35 C-5,35 0,32 0,28 C0,32 5,35 10,35 C20,35 25,25 20,20 C30,15 35,5 35,-5 C35,-20 20,-35 0,-35" fill="none" stroke="{{color}}" stroke-width="2"/>
  <path d="M0,-35 L0,28" stroke="{{color}}" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>

- "Network/Cloud": Draw a cloud shape
  <path d="M-30,10 A20,20 0 0,1 -20,-15 A25,25 0 0,1 20,-15 A20,20 0 0,1 30,10 Z" fill="none" stroke="{{color}}" stroke-width="2"/>

- "User/Person": Draw a person silhouette
  <circle cx="0" cy="-20" r="12" fill="none" stroke="{{color}}" stroke-width="2"/>
  <path d="M-25,25 C-25,5 -15,-5 0,-5 C15,-5 25,5 25,25" fill="none" stroke="{{color}}" stroke-width="2"/>

- "Lock/Security": Draw a padlock
  <rect x="-18" y="-5" width="36" height="30" rx="3" fill="none" stroke="{{color}}" stroke-width="2"/>
  <path d="M-10,-5 L-10,-18 A10,10 0 0,1 10,-18 L10,-5" fill="none" stroke="{{color}}" stroke-width="2"/>
  <circle cx="0" cy="10" r="4" fill="{{color}}"/>

- "Rocket/Speed": Draw a rocket
  <path d="M0,-40 C-8,-30 -12,-10 -12,10 L12,10 C12,-10 8,-30 0,-40" fill="none" stroke="{{color}}" stroke-width="2"/>
  <path d="M-12,10 L-18,25 L-8,15" fill="none" stroke="{{color}}" stroke-width="2"/>
  <path d="M12,10 L18,25 L8,15" fill="none" stroke="{{color}}" stroke-width="2"/>
  <circle cx="0" cy="-5" r="4" fill="{{color}}" opacity="0.7"/>

- "Chart/Growth": Draw an upward chart
  <polyline points="-30,25 -10,5 5,15 30,-25" fill="none" stroke="{{color}}" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="-35" y1="30" x2="35" y2="30" stroke="{{color}}" stroke-width="1.5" opacity="0.5"/>
  <line x1="-35" y1="30" x2="-35" y2="-30" stroke="{{color}}" stroke-width="1.5" opacity="0.5"/>

OUTPUT FORMAT — Return a JSON object:
{{
  "icons": {{
    "Entity Name 1": "<g>...SVG elements...</g>",
    "Entity Name 2": "<g>...SVG elements...</g>"
  }}
}}

CRITICAL RULES:
- EVERY icon must be wrapped in <g>...</g>
- Use ACTUAL SVG path/shape elements, NOT just circles or rects
- The icon must VISUALLY MATCH what the entity name means
- If unsure about a concept, draw the closest real-world object it relates to
- Keep icons clean — 3-8 SVG elements per icon maximum"""

        prompt = f"""Design icons for these entities:
{entity_list}

Return JSON with SVG icons for each entity. Every icon must visually represent the entity's meaning."""

        try:
            result = self.invoke_llm(prompt, system_prompt)
            parsed = self._parse_json(result)
            
            icons = parsed.get("icons", {})
            
            # 验证每个 icon 是合法 SVG 片段
            validated = {}
            for label in entity_labels:
                icon_svg = icons.get(label, "")
                if icon_svg and "<" in icon_svg and ">" in icon_svg:
                    validated[label] = icon_svg
                else:
                    # Fallback: 简单几何图标
                    validated[label] = self._fallback_icon(label, primary)
            
            return validated
            
        except Exception as e:
            self._log(f"Icon design failed: {e}", "warning")
            return {label: self._fallback_icon(label, primary) for label in entity_labels}
    
    def _fallback_icon(self, label: str, color: str) -> str:
        """简单 fallback 图标 — 带首字母的圆"""
        initial = label[0].upper() if label else "?"
        return (
            f'<g>'
            f'<circle cx="0" cy="0" r="35" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<text x="0" y="5" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="24" font-weight="bold" fill="{color}">{initial}</text>'
            f'</g>'
        )
    
    def _parse_json(self, response: str) -> Dict:
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
