"""
Concept Analyzer Agent
======================

精炼层 - 从杂乱字幕中提取核心可视化内容，融合场景上下文
输出：干净的concepts供VisualStrategist使用
"""

from typing import Dict, Tuple
from base_agent import BaseAgent
from state import SVGState


class ConceptAnalyzerAgent(BaseAgent):
    """概念分析Agent - 从字幕提取可视化核心"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("concept_analyzer", llm_type)
        self.role_description = "Extract visual concepts from subtitle text"
        self.capabilities = ["entity_extraction", "relationship_mapping", "context_fusion"]
    
    def execute(self, state: SVGState) -> SVGState:
        """执行概念分析"""
        self._log("Analyzing concepts...")
        
        input_text = state.get("input_text", "")
        concepts = self._analyze_with_context(input_text)
        
        state["concepts"] = concepts
        state["entities"] = concepts.get("entities", [])
        state["relationships"] = concepts.get("relationships", [])
        state["layout_type"] = concepts.get("layout_type", "flow")
        
        self.record_decision(
            state,
            "concept_analysis",
            f"Extracted: {concepts.get('core_topic', 'N/A')}",
            f"Entities: {len(concepts.get('entities', []))}"
        )
        
        self._log(f"✓ Core topic: {concepts.get('core_topic', 'N/A')}")
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "concept_analysis":
            return True, 0.95
        return False, 0.0
    
    def _analyze_with_context(
        self,
        text: str
    ) -> Dict:
        """
        从字幕文本中提取可视化核心
        
        输入：杂乱的字幕文本 (忽略视频上下文，专注于文本)
        输出：干净的概念描述，供VisualStrategist使用
        """
        try:
            # 场景风格信息（辅助决策）
            # 场景风格信息（无上下文）
            style_hint = "Dynamic SVG animation for video enhancement"
            
            system_prompt = """You are a Concept Extractor for educational video overlays.

Your job: Extract the CORE VISUAL CONCEPT from messy subtitle text.

The input is raw subtitle text - it may contain filler words, incomplete sentences, 
or tangential comments. You must find the KEY IDEA that deserves visual explanation.

Output JSON:
{
  "core_topic": "One clear sentence describing what to visualize",
  "entities": ["entity1", "entity2", "entity3"],
  "relationships": [
    {"from": "entity1", "to": "entity2", "label": "connects to"}
  ],
  "layout_type": "best layout for this content",
  "entity_count": 3,
  "visual_hint": "Brief description of what the diagram should look like"
}

Rules:
1. core_topic must be a CLEAR, SPECIFIC statement (not vague)
2. entities: 3-6 key nouns/concepts (not verbs, not filler)
3. relationships: how entities connect (flow, contains, compares, etc.)
4. layout_type: Choose the BEST layout for this specific content:
   - "flow" — sequential process, step-by-step (A→B→C)
   - "hierarchy" — tree/org structure, top-down layers
   - "radial" — central concept with surrounding elements
   - "cycle" — circular process, feedback loops
   - "comparison" — side-by-side contrast (vs, before/after)
   - "grid" — matrix/table of related items
   - "scatter" — free-form spatial arrangement
   DO NOT always pick "flow"! Match the layout to the MEANING of the content.
5. visual_hint: describe the diagram in 10 words or less
6. Keep entity_count between 3-6"""
            
            prompt = f"""Extract the visual concept from this subtitle text:

"{text}"

Scene context: {style_hint}

What is the ONE key concept here that would benefit from a diagram?
Return JSON only."""
            
            print("ConceptAnalyzerAgent prompt:",prompt)
            result = self.invoke_llm(prompt, system_prompt)
            parsed = self.parse_json_response(result)
            print("ConceptAnalyzerAgent result:",parsed)
            
            # 验证并补充
            if not parsed.get("core_topic"):
                parsed["core_topic"] = text[:80]
            if not parsed.get("entities"):
                parsed["entities"] = self._simple_extract_entities(text)

            if not parsed.get("visual_hint"):
                parsed["visual_hint"] = "Diagram showing " + parsed["core_topic"][:30]
            
            return parsed
            
        except Exception as e:
            self._log(f"Concept analysis failed: {e}", "warning")
            return self._fallback_analysis(text)
    
    # _extract_style_hint removed as requested
    
    def _simple_extract_entities(self, text: str) -> list:
        """简单实体提取（降级）"""
        words = text.split()
        # 过滤掉短词和常见停用词
        stop_words = {'the', 'is', 'are', 'was', 'were', 'and', 'but', 'or', 'this', 'that',
                      'with', 'for', 'from', 'not', 'can', 'will', 'has', 'have', 'had',
                      'about', 'into', 'what', 'when', 'how', 'why', 'its', 'also', 'very',
                      'just', 'then', 'than', 'more', 'some', 'like', 'been', 'would', 'could'}
        entities = [w.strip('.,;:!?"\'') for w in words 
                   if len(w) > 3 and w.lower() not in stop_words]
        return entities[:5]
    
    def _fallback_analysis(self, text: str) -> Dict:
        """降级分析"""
        entities = self._simple_extract_entities(text)
        return {
            "core_topic": text[:80],
            "entities": entities,
            "relationships": [],
            "entity_count": len(entities),
            "visual_hint": "Simple diagram"
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