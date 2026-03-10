"""
Art Director Agent
==================

轻量艺术指导 - 丰富visual_strategy（blueprint），不产生独立的refined_design
简单模式下直接跳过，复杂模式下对blueprint做微调
"""

from typing import Dict, Tuple
from base_agent import BaseAgent
from state import SVGState


class ArtDirectorAgent(BaseAgent):
    """艺术指导Agent - 丰富blueprint"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("art_director", llm_type)
        self.role_description = "Enrich visual blueprint"
        self.capabilities = ["design_refinement"]
    
    def execute(self, state: SVGState) -> SVGState:
        """执行艺术指导 - 丰富blueprint"""
        self._log("Art Direction...")
        
        direction_mode = state.get("direction_mode", "simple")
        blueprint = state.get("visual_strategy", {})
        
        if direction_mode == "simple":
            # 简单模式：不做任何修改，blueprint直接传给SVGCreator
            self._log("  Mode: Simple (pass-through)")
            state["refined_design"] = {}
        else:
            # 复杂模式：LLM丰富blueprint
            enriched = self._enrich_blueprint(blueprint, state)
            # 把enrichment合并回visual_strategy
            if enriched:
                blueprint.update(enriched)
                state["visual_strategy"] = blueprint
            state["refined_design"] = enriched or {}
            self._log("  Mode: Complex (blueprint enriched)")
        
        self.record_decision(
            state, "art_direction",
            f"Mode: {direction_mode}",
            "Blueprint enriched" if direction_mode != "simple" else "Pass-through"
        )
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "art_direction":
            return True, 0.9
        return False, 0.0
    
    def _enrich_blueprint(self, blueprint: Dict, state: SVGState) -> Dict:
        """LLM丰富blueprint"""
        try:
            entities = blueprint.get("entities", [])
            layout_type = blueprint.get("layout_type", "flow")
            diagram_desc = blueprint.get("diagram_description", "")
            
            system_prompt = """You are a Creative Director for a high-end motion graphics studio.
Your job is to take a functional diagram blueprint and add "Visual Soul" and "Polish".

**Output JSON (Enrichment):**
{
  "visual_theme_refinement": "Refined style name (e.g., 'Neon Glassmorphism')",
  "animation_style": "Specific animation directive (e.g., 'Staggered elastic entry from center')",
  "special_instructions": "ONE high-impact visual rule (e.g., 'All connecting lines must have a flowing gradient stroke')",
  "element_shapes": {"entity1": "specific_shape", "entity2": "specific_shape"},
  "color_adjustments": "Suggestion to shift colors (optional)"
}

**DIRECTIVES:**
1. **Be Opinionated**: Don't be boring. Suggest specific stroke patterns (dashed, dotted), gradients, or layout tweaks.
2. **Animation**: Suggest *how* things move. "Smooth fade" is boring. "Explosive pop-in with damping" is better.
3. **Cohesion**: Ensure shapes match the vibe (e.g., Sharp angles for Tech, Soft blobs for Organic)."""
            
            prompt = f"""Enrich this blueprint:

Diagram: {diagram_desc}
Layout: {layout_type}
Entities: {entities}

What animation style and visual polish would improve this?
Return JSON only."""
            
            result = self.invoke_llm(prompt, system_prompt)
            return self.parse_json_response(result)
            
        except Exception as e:
            self._log(f"Enrichment failed: {e}", "warning")
            return {}
    
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