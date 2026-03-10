"""
SVG Reviewer Agent
==================

视觉评审 - 单一Prompt盲测（描述→一致性→美观→建议）
统一画布: 1920x1080
"""

import os
from typing import Dict, Tuple
from base_agent import BaseAgent
from state import SVGState

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class SVGReviewerAgent(BaseAgent):
    """视觉评审Agent - 统一盲测评审"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("svg_reviewer", llm_type)
        self.role_description = "Review SVG with comprehensive blind test"
        self.capabilities = ["visual_analysis", "consistency_check", "quality_scoring", "improvement_guidance"]
    
    def execute(self, state: SVGState) -> SVGState:
        """执行视觉评审"""
        self._log("Comprehensive visual review...")
        
        svg_content = state.get("current_svg", "")
        svg_png_path = state.get("svg_png_path", "")
        input_text = state.get("input_text", "")
        concepts = state.get("concepts", {})
        
        # Construct concept description for review
        core_topic = concepts.get("core_topic", input_text[:50])
        entities = concepts.get("entities", [])
        concept_desc = f"Topic: {core_topic}. Entities: {', '.join(entities) if entities else 'N/A'}"
        
        if not svg_content:
            self._log("No SVG to review", "warning")
            state["overall_score"] = 0
            return state
        
        review_result = self._comprehensive_blind_review(
            svg_content, svg_png_path, concept_desc
        )
        
        state["review_result"] = review_result
        state["overall_score"] = review_result.get("overall_score", 0)
        state["improvement_suggestions"] = review_result.get("improvement_suggestions", [])
        
        self.record_decision(
            state,
            "visual_review",
            f"Score: {review_result.get('overall_score', 0)}/10",
            f"Consistency: {review_result.get('consistency_score', 0)}/10"
        )
        
        self._log(f"✓ Review complete: {review_result.get('overall_score', 0)}/10")
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        """检查是否可以贡献"""
        phase = state.get("phase", "")
        if phase == "review":
            return True, 0.95
        return False, 0.0
    
    def _comprehensive_blind_review(
        self,
        svg_content: str,
        png_path: str,
        concept_description: str
    ) -> Dict:
        """统一盲测评审"""
        try:
            system_prompt = f"""You are an Expert SVG Visual Reviewer conducting a comprehensive blind test evaluation.

The target canvas is {CANVAS_WIDTH}x{CANVAS_HEIGHT} pixels.

Your task: Analyze an SVG animation in 4 steps within ONE response.

═══════════════════════════════════════════════════════════════════

STEP 1: BLIND VISUAL DESCRIPTION
Objectively describe what you see in the SVG code.

**LAYOUT QUALITY CHECKS (CRITICAL):**
- Verify elements use the full {CANVAS_WIDTH}x{CANVAS_HEIGHT} canvas
- Check if elements are clustered (all x < 400, y < 300 = PROBLEM)
- Verify horizontal spread > 800px and vertical spread > 400px
- Note if layout is balanced or cramped

═══════════════════════════════════════════════════════════════════

STEP 2: CONSISTENCY CHECK
Compare your description with intended concept. Score 0-10.

═══════════════════════════════════════════════════════════════════

STEP 3: AESTHETIC QUALITY (0-10 each)
- Color Harmony
- Visual Balance (-5 if clustering detected!)
- Clarity
- Professionalism

═══════════════════════════════════════════════════════════════════

STEP 4: IMPROVEMENT SUGGESTIONS (Specific & Actionable)

**PRIORITY: If clustering detected, suggest specific redistributions:**
Example: "Move element from x='50' to x='960' (center of {CANVAS_WIDTH}px canvas)"

Each suggestion MUST have:
- type: color_adjustment/size_adjustment/layout_fix/animation_enhancement/position_adjustment
- target: Which element
- current: Current value
- suggested: Specific new value (for {CANVAS_WIDTH}x{CANVAS_HEIGHT} canvas)
- reason: Why

═══════════════════════════════════════════════════════════════════

OUTPUT FORMAT (JSON):

{{
  "visual_description": {{
    "elements": ["..."],
    "colors": ["..."],
    "layout": "description",
    "animations": "description",
    "apparent_concept": "what it looks like"
  }},
  "consistency_check": {{
    "score": 1-10,
    "matches": ["..."],
    "mismatches": ["..."],
    "verdict": "summary"
  }},
  "aesthetic_scores": {{
    "color_harmony": 1-10,
    "visual_balance": 1-10,
    "clarity": 1-10,
    "professionalism": 1-10,
    "overall_aesthetic": 1-10
  }},
  "improvement_suggestions": [
    {{
      "type": "E.g. position_adjustment",
      "target": "E.g. element description",
      "current": "E.g. x='100'",
      "suggested": "E.g. x='960'",
      "reason": "E.g. Center on canvas for better balance"
    }}
  ],
  "overall_score": 1-10
}}

overall_score = (consistency_score * 0.6) + (overall_aesthetic * 0.4)"""
            
            prompt = f"""Review this SVG (target canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT}):

INTENDED CONCEPT: "{concept_description}"

SVG CODE:
{svg_content}

Perform all 4 steps. Return JSON only."""
            

            result = self.invoke_llm(prompt, system_prompt)
            parsed = self.parse_json_response(result)
            print("ReviewerAgent result:", parsed)
            # 确保overall_score存在
            if "overall_score" not in parsed:
                consistency = parsed.get("consistency_check", {}).get("score", 5)
                aesthetic = parsed.get("aesthetic_scores", {}).get("overall_aesthetic", 5)
                parsed["overall_score"] = round(consistency * 0.6 + aesthetic * 0.4, 1)
            
            parsed["consistency_score"] = parsed.get("consistency_check", {}).get("score", 5)
            parsed["aesthetic_score"] = parsed.get("aesthetic_scores", {}).get("overall_aesthetic", 5)
            
            return parsed
            
        except Exception as e:
            self._log(f"Comprehensive review failed: {e}", "error")
            return self._fallback_review()
    
    def _fallback_review(self) -> Dict:
        """降级评审"""
        return {
            "visual_description": {
                "elements": ["unknown"], "colors": ["unknown"],
                "layout": "unknown", "animations": "unknown",
                "apparent_concept": "unclear"
            },
            "consistency_check": {
                "score": 5, "matches": [], "mismatches": [],
                "verdict": "unable to evaluate"
            },
            "aesthetic_scores": {
                "color_harmony": 5, "visual_balance": 5,
                "clarity": 5, "professionalism": 5,
                "overall_aesthetic": 5.0
            },
            "improvement_suggestions": [],
            "consistency_score": 5,
            "aesthetic_score": 5,
            "overall_score": 5.0,
            "review_mode": "fallback"
        }
    
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