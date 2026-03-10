"""
SVG Agent Workflow
==================

完整工作流 - 整合RouteAgent + 自适应路由
画布: 1920x1080
"""

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from state import SVGState, create_initial_state
from concept_analyzer_agent import ConceptAnalyzerAgent
from route_agent import RouteAgent
from scene_adapter_agent import SceneAdapterAgent
from layout_expert_agent import LayoutExpertAgent
from icon_designer_agent import IconDesignerAgent
from judge_agent import JudgeAgent
from visual_strategist_agent import VisualStrategistAgent
from art_director_agent import ArtDirectorAgent
from svg_creator_agent import SVGCreatorAgent
from code_validator_agent import CodeValidatorAgent
from svg_reviewer_agent import SVGReviewerAgent
from svg_refiner_agent import SVGRefinerAgent

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080

import functools
import pprint

def debug_agent(func):
    @functools.wraps(func)
    def wrapper(self, state):
        # 1. 执行原函数
        result = func(self, state)
        
        # 2. 获取 Agent 名字
        agent_name = func.__name__.strip("_").upper()
        
        # 3. 处理打印显示 (只修改副本，不影响原数据)
        display_data = {}
        if isinstance(result, dict):
            display_data = result.copy()
            
            # === ✂️ 裁剪长字段 ===
            
            # 1. 隐藏 SVG 代码
            if "current_svg" in display_data:
                svg_content = display_data["current_svg"]
                if svg_content:
                    display_data["current_svg"] = f"<SVG Code hidden, {len(svg_content)} chars>"
            
            # 2. 隐藏消息历史
            if "messages" in display_data:
                 display_data["messages"] = "<Message History hidden>"

            # 3. 隐藏决策日志 (User 指定不需要)
            if "decision_log" in display_data:
                log = display_data["decision_log"]
                count = len(log) if isinstance(log, list) else 0
                display_data["decision_log"] = f"<Decision Log hidden, {count} entries>"

            # 4. 简化 SharedContext (如果它是个对象或大字典)
            if "shared_context" in display_data:
                # 只显示类型或者简单的占位符
                ctx = display_data["shared_context"]
                display_data["shared_context"] = f"<SharedContext Object: {type(ctx).__name__}>"

            # 5. 隐藏其他可能的长列表 (可选)
            if "svg_history" in display_data:
                 display_data["svg_history"] = f"<History hidden, {len(display_data['svg_history'])} items>"

        else:
            display_data = result

        # 4. 打印
        print(f"\n🔹 [{agent_name}] Result:")
        # depth=2 可以限制嵌套打印的深度，防止打印出太深层的细节
        pprint.pprint(display_data, indent=2, width=100, sort_dicts=False)
        print("-" * 50)
        
        return result
    return wrapper

class SVGWorkflow:
    """SVG生成工作流"""
    
    def __init__(
        self,
        llm_type: str = "claude-sonnet-4-5-20250929",
        vision_llm_type: str = None
    ):
        self.llm_type = llm_type
        self.vision_llm_type = vision_llm_type or llm_type
        
        # 初始化所有Agents
        self.concept_analyzer = ConceptAnalyzerAgent(llm_type)
        self.route_agent = RouteAgent(llm_type)
        self.scene_adapter = SceneAdapterAgent(llm_type)
        self.layout_expert = LayoutExpertAgent(llm_type)
        self.icon_designer = IconDesignerAgent(llm_type)     # NEW
        self.judge = JudgeAgent(llm_type)                    # NEW
        self.visual_strategist = VisualStrategistAgent(llm_type)
        self.art_director = ArtDirectorAgent(llm_type)
        self.svg_creator = SVGCreatorAgent(llm_type)
        self.code_validator = CodeValidatorAgent(llm_type)
        self.svg_reviewer = SVGReviewerAgent(self.vision_llm_type)
        self.svg_refiner = SVGRefinerAgent(llm_type)
        
        self.workflow = self._build_workflow()
        
        self.max_iterations = 2
        self.min_score = 7.0
        
        print(f"✓ SVGWorkflow initialized (Canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT})")
        print(f"  LLM: {llm_type}")
        print(f"  Pipeline: Concept → [Scene+Layout] → Strategy → [Judge(complex)] → Icons → SVG")
    
    def _build_workflow(self) -> StateGraph:
        """构建工作流图 — 分层架构 + simple/complex 分流"""
        workflow = StateGraph(SVGState)
        
        # 节点定义
        workflow.add_node("concept_analysis", self._concept_analysis)
        workflow.add_node("routing", self._routing)
        workflow.add_node("scene_adaptation", self._scene_adaptation)
        workflow.add_node("layout_planning", self._layout_planning)
        workflow.add_node("visual_strategy", self._visual_strategy)
        workflow.add_node("judging", self._judging)              # NEW
        workflow.add_node("art_direction", self._art_direction)
        workflow.add_node("icon_design", self._icon_design)      # NEW
        workflow.add_node("svg_generation", self._svg_generation)
        workflow.add_node("code_validation", self._code_validation)
        workflow.add_node("visual_review", self._visual_review)
        workflow.add_node("refinement", self._refinement)
        workflow.add_node("finalize", self._finalize)
        
        workflow.set_entry_point("concept_analysis")
        
        # === 共同前置: concept → routing → scene → layout → strategy ===
        workflow.add_edge("concept_analysis", "routing")
        workflow.add_edge("routing", "scene_adaptation")
        workflow.add_edge("scene_adaptation", "layout_planning")
        workflow.add_edge("layout_planning", "visual_strategy")
        
        # === 分流: simple 走快通道, complex 走精细通道 ===
        workflow.add_conditional_edges(
            "visual_strategy",
            self._route_by_complexity,
            {
                "simple": "icon_design",        # simple: 跳过judge+art, 直接图标→SVG
                "complex": "judging",            # complex: judge→art→图标→SVG
            }
        )
        
        # Complex 路径: judge → art → icon → svg
        workflow.add_edge("judging", "art_direction")
        workflow.add_edge("art_direction", "icon_design")
        
        # 共同后置: icon → svg → validate → review → refine
        workflow.add_edge("icon_design", "svg_generation")
        workflow.add_edge("svg_generation", "code_validation")
        
        workflow.add_conditional_edges(
            "code_validation",
            self._check_code_valid,
            {"valid": "visual_review", "invalid": "refinement"}
        )
        
        workflow.add_conditional_edges(
            "visual_review",
            self._check_quality,
            {"good": "finalize", "needs_improvement": "refinement"}
        )
        
        workflow.add_conditional_edges(
            "refinement",
            self._check_iterations,
            {"continue": "code_validation", "stop": "finalize"}
        )
        
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    def generate(
        self,
        input_text: str,
        context: str = "technical",
        layout_context: Optional[Dict] = None,
        scene_context: Optional[Dict] = None,
        output_dir: Optional[str] = None,
        sample_id: Optional[str] = None,
        enable_complex_mode: bool = False
    ) -> Dict[str, Any]:
        """生成SVG"""
        initial_state = create_initial_state(
            input_text=input_text,
            context=context
        )
        
        if layout_context:
            initial_state["layout_context"] = layout_context
        if scene_context:
            initial_state["scene_context"] = scene_context
        if output_dir:
            initial_state["output_dir"] = output_dir
        if sample_id:
            initial_state["sample_id"] = sample_id
        
        initial_state["enable_complex_mode"] = enable_complex_mode
        
        try:
            final_state = self.workflow.invoke(initial_state)
        except Exception as e:
            print(f"Workflow error: {e}")
            final_state = initial_state
            final_state["current_svg"] = self._emergency_fallback(input_text)
        
        return {
            "svg_content": final_state.get("current_svg", ""),
            "svg_path": final_state.get("svg_path", ""),
            "overall_score": final_state.get("overall_score", 0),
            "iteration": final_state.get("iteration", 0),
            "concepts": final_state.get("concepts", {}),
            "visual_strategy": final_state.get("visual_strategy", {}),
            "validation_result": final_state.get("validation_result", {}),
            "workflow_mode": final_state.get("workflow_mode", "simple"),
            "decisions": final_state.get("decisions", [])
        }
    
    # ========== 节点函数 ==========
    # @debug_agent
    def _concept_analysis(self, state: SVGState) -> SVGState:
        state["phase"] = "concept_analysis"
        return self.concept_analyzer.execute(state)
    

    # @debug_agent
    def _routing(self, state: SVGState) -> SVGState:
        state["phase"] = "routing"
        return self.route_agent.execute(state)
    
    # @debug_agent
    def _scene_adaptation(self, state: SVGState) -> SVGState:
        """场景适配 — 视频帧→SVG配色"""
        state["phase"] = "scene_adaptation"
        return self.scene_adapter.execute(state)
    
    # @debug_agent
    def _layout_planning(self, state: SVGState) -> SVGState:
        """布局规划 — 选择布局+生成坐标"""
        state["phase"] = "layout_planning"
        return self.layout_expert.execute(state)
    
    # @debug_agent
    def _visual_strategy(self, state: SVGState) -> SVGState:
        state["phase"] = "visual_strategy"
        return self.visual_strategist.execute(state)
    
    # @debug_agent
    def _judging(self, state: SVGState) -> SVGState:
        """NEW: 裁判竞演方案"""
        state["phase"] = "judging"
        return self.judge.execute(state)
    
    # @debug_agent
    def _art_direction(self, state: SVGState) -> SVGState:
        state["phase"] = "art_direction"
        return self.art_director.execute(state)
    
    # @debug_agent
    def _icon_design(self, state: SVGState) -> SVGState:
        """NEW: 图标设计"""
        state["phase"] = "icon_design"
        return self.icon_designer.execute(state)
    
    # @debug_agent
    def _svg_generation(self, state: SVGState) -> SVGState:
        state["phase"] = "svg_generation"
        return self.svg_creator.execute(state)
    
    # @debug_agent
    def _code_validation(self, state: SVGState) -> SVGState:
        state["phase"] = "code_validation"
        return self.code_validator.execute(state)
    
    # @debug_agent
    def _visual_review(self, state: SVGState) -> SVGState:
        state["phase"] = "review"
        return self.svg_reviewer.execute(state)
    
    # @debug_agent
    def _refinement(self, state: SVGState) -> SVGState:
        state["phase"] = "refinement"
        state["iteration"] = state.get("iteration", 0) + 1
        return self.svg_refiner.execute(state)
    
    
    def _finalize(self, state: SVGState) -> SVGState:
        state["phase"] = "finalize"
        return state
    
    # ========== 条件判断 ==========
    
    def _route_by_complexity(self, state: SVGState) -> str:
        """simple/complex 分流"""
        return "complex" if state.get("enable_complex_mode", False) else "simple"

    def _check_code_valid(self, state: SVGState) -> str:
        validation = state.get("validation_result", {})
        return "valid" if validation.get("valid", False) else "invalid"
    
    def _check_quality(self, state: SVGState) -> str:
        score = state.get("overall_score", 0)
        iteration = state.get("iteration", 0)
        if score >= self.min_score or iteration >= self.max_iterations:
            return "good"
        return "needs_improvement"
    
    def _check_iterations(self, state: SVGState) -> str:
        iteration = state.get("iteration", 0)
        return "continue" if iteration < self.max_iterations else "stop"
    
    def _emergency_fallback(self, text: str) -> str:
        safe = text[:40].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="#0a192f"/>
  <text x="960" y="540" font-family="sans-serif" font-size="36" fill="#64ffda" text-anchor="middle">
    {safe}
  </text>
</svg>'''