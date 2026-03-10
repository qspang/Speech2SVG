"""
Route Agent
===========

路由Agent - 判断简单/复杂模式，决定工作流路径
"""

from typing import Dict, Tuple
from base_agent import BaseAgent
from state import SVGState


class RouteAgent(BaseAgent):
    """路由Agent - 智能选择工作流模式"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("route_agent", llm_type)
        self.role_description = "Route workflow based on complexity"
        self.capabilities = ["complexity_analysis", "mode_selection", "adaptive_routing"]
    
    def execute(self, state: SVGState) -> SVGState:
        """执行路由决策"""
        self._log("Routing workflow...")
        
        concepts = state.get("concepts", {})
        enable_complex = state.get("enable_complex_mode", False)
        
        if not enable_complex:
            # 简单模式：始终走简单路径
            self._log("Simple mode enabled - using conservative path")
            state["workflow_mode"] = "simple"
            state["strategy_mode"] = "simple"
            state["direction_mode"] = "simple"
            state["creation_mode"] = "simple"
        else:
            # 复杂模式：每个阶段独立判断
            self._log("Complex mode enabled - analyzing each stage")
            
            # 第一步：判断策略阶段
            strategy_mode = self._judge_strategy_complexity(concepts)
            state["strategy_mode"] = strategy_mode
            self._log(f"  Strategy stage: {strategy_mode}")
            
            # 第二步会在ArtDirector前判断
            state["direction_mode"] = None  # 稍后判断
            
            # 第三步会在SVGCreator前判断
            state["creation_mode"] = None  # 稍后判断
            
            state["workflow_mode"] = "complex"
        
        self.record_decision(
            state,
            "routing",
            f"Mode: {state['workflow_mode']}",
            f"Strategy: {state.get('strategy_mode', 'N/A')}"
        )
        
        self._log(f"✓ Routing complete: {state['workflow_mode']} mode")
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        """检查是否可以贡献"""
        phase = state.get("phase", "")
        if phase == "routing":
            return True, 0.95
        return False, 0.0
    
    def _judge_strategy_complexity(self, concepts: Dict) -> str:
        """
        判断策略阶段的复杂度
        
        简单 → 单个保守方案
        复杂 → 三个方案竞争
        """
        try:
            entities = concepts.get("entities", [])
            relationships = concepts.get("relationships", [])
            layout_type = concepts.get("layout_type", "flow")
            
            system_prompt = """You are a Complexity Analyzer for visual design.

Analyze the concept and decide: SIMPLE or COMPLEX?

SIMPLE criteria:
- Few entities (≤3)
- Simple relationships (linear flow, single connection type)
- Basic layout (flow, linear)
- Common patterns (client-server, request-response)

COMPLEX criteria:
- Many entities (>3)
- Complex relationships (multiple types, cycles, hierarchies)
- Advanced layout (hierarchy, network, matrix)
- Uncommon patterns (distributed systems, multi-layer architectures)

Output JSON:
{
  "complexity": "simple/complex",
  "reason": "Brief justification",
  "entity_count": 3,
  "relationship_complexity": "low/medium/high"
}"""
            
            prompt = f"""Analyze complexity:

Entities: {entities}
Relationships: {relationships}
Layout type: {layout_type}

Is this SIMPLE or COMPLEX? Return JSON only."""
            
            result = self.invoke_llm(prompt, system_prompt)
            parsed = self.parse_json_response(result)
            
            complexity = parsed.get("complexity", "simple")
            return complexity
            
        except Exception as e:
            self._log(f"Strategy complexity analysis failed: {e}", "warning")
            return "simple"  # 默认简单
    
    def judge_direction_complexity(self, state: SVGState) -> str:
        """
        判断艺术指导阶段的复杂度
        
        简单 → 直接分析（无对抗）
        复杂 → 对抗优化（Director vs Refiner）
        """
        try:
            visual_strategy = state.get("visual_strategy", {})
            concepts = state.get("concepts", {})
            
            system_prompt = """You are analyzing if Art Direction needs adversarial refinement.

SIMPLE (direct analysis):
- Strategy is already clear and concrete
- Conservative/safe design approach
- Few visual elements
- Standard patterns

COMPLEX (adversarial refinement):
- Strategy is vague or generic
- Bold/creative design approach
- Many visual elements with interactions
- Novel patterns needing critique

Output JSON:
{
  "complexity": "simple/complex",
  "reason": "Brief justification"
}"""
            
            prompt = f"""Analyze Art Direction complexity:

Strategy: {visual_strategy.get('approach', 'N/A')}
Style: {visual_strategy.get('style', 'N/A')}
Entities: {concepts.get('entities', [])}

Does this need adversarial refinement? Return JSON only."""
            
            result = self.invoke_llm(prompt, system_prompt)
            parsed = self.parse_json_response(result)
            
            return parsed.get("complexity", "simple")
            
        except Exception as e:
            self._log(f"Direction complexity analysis failed: {e}", "warning")
            return "simple"
    
    def judge_creation_complexity(self, state: SVGState) -> str:
        """
        判断创建阶段的复杂度
        
        简单 → 一步生成（直接生成完整SVG）
        复杂 → 双轨生产（几何+动效分离）
        """
        try:
            refined_design = state.get("refined_design", {})
            visual_strategy = state.get("visual_strategy", {})
            
            motion_enhancements = refined_design.get("motion_enhancements", [])
            
            system_prompt = """You are analyzing SVG creation complexity.

SIMPLE (one-step generation):
- Few visual elements (≤5)
- Minimal or no animations
- Static or simple transitions
- Basic shapes only

COMPLEX (dual-track production):
- Many visual elements (>5)
- Multiple coordinated animations
- Complex motion choreography
- Custom paths or gradients

Output JSON:
{
  "complexity": "simple/complex",
  "reason": "Brief justification",
  "animation_count": 0
}"""
            
            prompt = f"""Analyze SVG creation complexity:

Motion enhancements: {motion_enhancements}
Animation style: {visual_strategy.get('animation', 'N/A')}

Should we use dual-track production? Return JSON only."""
            
            result = self.invoke_llm(prompt, system_prompt)
            parsed = self.parse_json_response(result)
            
            return parsed.get("complexity", "simple")
            
        except Exception as e:
            self._log(f"Creation complexity analysis failed: {e}", "warning")
            return "simple"
    
    def parse_json_response(self, response: str) -> Dict:
        """解析JSON"""
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
