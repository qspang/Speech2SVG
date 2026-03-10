"""
Judge Agent
===========

裁判Agent — 从多个竞演方案中选出最佳

输入: state["competing_blueprints"] (3个方案: 保守/大胆/中立)
输出: state["visual_strategy"] (选中的最佳方案)

仅在 complex 模式下使用
"""

from typing import Dict, List, Tuple
from base_agent import BaseAgent
from state import SVGState


class JudgeAgent(BaseAgent):
    """裁判Agent — 从竞演方案中选最佳"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("judge", llm_type)
        self.role_description = "Judge and select the best visual blueprint from competing proposals"
        self.capabilities = ["design_evaluation", "proposal_selection"]
    
    def execute(self, state: SVGState) -> SVGState:
        """评估并选出最佳方案"""
        self._log("Judging competing blueprints...")
        
        blueprints = state.get("competing_blueprints", [])
        
        if not blueprints or len(blueprints) <= 1:
            # 只有1个或没有方案，直接使用
            if blueprints:
                state["visual_strategy"] = blueprints[0]
            self._log("  Single/no proposals — skipping judgment")
            return state
        
        # LLM 评判
        best = self._judge_blueprints(blueprints, state)
        state["visual_strategy"] = best
        
        self._log(f"✓ Selected: {best.get('style_name', 'unknown')} style")
        
        self.record_decision(
            state, "judging",
            f"Selected: {best.get('style_name', 'unknown')}",
            f"From {len(blueprints)} competing proposals"
        )
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "judging":
            return True, 0.95
        return False, 0.0
    
    def _judge_blueprints(self, blueprints: List[Dict], state: SVGState) -> Dict:
        """LLM 评判选最佳"""
        try:
            input_text = state.get("input_text", "")
            
            proposals = []
            for i, bp in enumerate(blueprints):
                style = bp.get("style_name", f"Style_{i+1}")
                desc = bp.get("diagram_description", "N/A")
                layout = bp.get("layout_type", "N/A")
                entities = bp.get("entities", [])
                entity_names = [e if isinstance(e, str) else e.get("label", "?") for e in entities[:6]]
                
                proposals.append(
                    f"PROPOSAL {i+1} ({style}):\n"
                    f"  Description: {desc}\n"
                    f"  Layout: {layout}\n"
                    f"  Entities: {', '.join(entity_names)}"
                )
            
            proposals_text = "\n\n".join(proposals)
            
            system_prompt = """You are a Design Judge evaluating visual diagram proposals.

EVALUATION CRITERIA (scored 1-10):
1. **Visual Impact** — Will it look stunning and memorable?
2. **Semantic Accuracy** — Does the layout/design match the content meaning?
3. **Creativity** — Is the approach original and interesting?
4. **Clarity** — Will viewers understand the information at a glance?
5. **Animation Potential** — Can it be animated in engaging ways?

Output JSON:
{
  "winner": 1,
  "scores": [
    {"proposal": 1, "total": 35, "impact": 7, "accuracy": 8, "creativity": 6, "clarity": 8, "animation": 6},
    {"proposal": 2, "total": 40, "impact": 9, "accuracy": 7, "creativity": 9, "clarity": 7, "animation": 8},
    {"proposal": 3, "total": 37, "impact": 8, "accuracy": 7, "creativity": 8, "clarity": 7, "animation": 7}
  ],
  "reason": "Brief explanation of why the winner is best"
}

IMPORTANT: Favor BOLD and CREATIVE proposals over safe/boring ones.
A visually stunning diagram is better than a technically perfect but dull one."""

            prompt = f"""TOPIC: {input_text}

{proposals_text}

Judge these proposals and select the winner. Return JSON only."""

            result = self.invoke_llm(prompt, system_prompt)
            parsed = self._parse_json(result)
            
            winner_idx = parsed.get("winner", 1) - 1  # 0-indexed
            winner_idx = max(0, min(winner_idx, len(blueprints) - 1))
            
            reason = parsed.get("reason", "")
            if reason:
                self._log(f"  Judgment: {reason[:80]}")
            
            return blueprints[winner_idx]
            
        except Exception as e:
            self._log(f"Judgment failed: {e}, using first proposal", "warning")
            return blueprints[0]
    
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
