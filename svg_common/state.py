"""
State Definition for SVG Agent System
======================================

SVG动画生成的状态定义
"""

from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated
from operator import add
from shared_context import SharedVisualContext
import time


class AgentMessage(TypedDict):
    """Agent消息"""
    agent_id: str
    content: str
    timestamp: float
    message_type: str  # "contribution" | "critique" | "question" | "answer"
    target_agent: Optional[str]


class SVGState(TypedDict):
    """
    SVG生成状态
    
    包含从输入到SVG输出的完整状态
    """
    
    # ========== 输入 ==========
    input_text: str  # 输入描述（主题）
    context: str  # 上下文类型
    
    # ========== 视频增强系统集成 ==========
    video_timestamp: Optional[float]  # 视频时间戳
    video_context: Optional[Dict[str, Any]]  # 视频上下文信息
    enhancement_type: Optional[str]  # 增强类型
    
    # ========== 共享上下文 ==========
    shared_context: Optional[SharedVisualContext]
    
    # ========== Agent通信 ==========
    messages: Annotated[List[AgentMessage], add]
    
    # ========== 概念分析 ==========
    concepts: List[Dict[str, Any]]  # 提取的概念列表
    key_elements: List[str]  # 关键元素
    
    # ========== 视觉策略 ==========
    visual_strategy: Optional[Dict[str, Any]]  # 视觉策略
    layout_plan: Optional[Dict[str, Any]]  # 布局规划
    
    # ========== 场景适配 + 布局规划 ==========
    color_scheme: Optional[Dict[str, Any]]  # SceneAdapterAgent输出: 背景/文字/强调色
    layout_plan_detailed: Optional[Dict[str, Any]]  # LayoutExpertAgent输出: 布局类型+坐标
    
    # ========== 图标设计 + 竞演 ==========
    entity_icons: Optional[Dict[str, str]]  # IconDesignerAgent输出: {label: svg_snippet}
    competing_blueprints: Optional[List[Dict[str, Any]]]  # 3方案竞演（complex模式）
    
    # ========== 验证 ==========
    validation_passed: bool
    validation_issues: List[Dict[str, Any]]
    
    # ========== SVG输出 ==========
    current_svg: Optional[str]  # 当前SVG内容
    svg_path: Optional[str]  # SVG文件路径
    svg_png_path: Optional[str]  # PNG渲染路径（用于视觉评审）
    
    # ========== 评审和迭代 ==========
    scores: Dict[str, float]  # 各项评分
    overall_score: float  # 总分
    critiques: List[Dict[str, Any]]  # 批评建议
    improvements: List[Dict[str, Any]]  # 改进点
    refine_count: int  # 精炼版本计数（v1, v2, ...）
    
    # ========== 历史 ==========
    svg_history: List[Dict[str, Any]]  # SVG版本历史
    
    # ========== 流程控制 ==========
    phase: str  # 当前阶段
    iteration: int  # 当前迭代次数
    max_iterations: int  # 最大迭代次数
    
    # 内部计数器
    _validation_count: int
    
    # ========== 决策日志 ==========
    decision_log: Annotated[List[Dict], add]
    
    # ========== 元数据 ==========
    active_agents: List[str]
    start_time: float
    last_modified: float
    
    # ========== 输出配置 ==========
    output_dir: Optional[str]
    sample_id: Optional[str]


def create_initial_state(
    input_text: str,
    context: str = "educational",
    video_timestamp: Optional[float] = None,
    video_context: Optional[Dict] = None
) -> SVGState:
    """
    创建初始状态
    
    Args:
        input_text: 输入描述
        context: 上下文类型
        video_timestamp: 视频时间戳（可选）
        video_context: 视频上下文（可选）
    """
    from shared_context import create_initial_context
    
    return SVGState(
        # 输入
        input_text=input_text,
        context=context,
        
        # 视频集成
        video_timestamp=video_timestamp,
        video_context=video_context,
        enhancement_type=None,
        
        # 共享上下文
        shared_context=create_initial_context(input_text, context),
        
        # 通信
        messages=[],
        
        # 分析
        concepts=[],
        key_elements=[],
        
        # 策略
        visual_strategy=None,
        layout_plan=None,
        
        # 场景适配 + 布局规划
        color_scheme=None,
        layout_plan_detailed=None,
        
        # 图标设计 + 竞演
        entity_icons=None,
        competing_blueprints=None,
        
        # 验证
        validation_passed=False,
        validation_issues=[],
        
        # SVG
        current_svg=None,
        svg_path=None,
        svg_png_path=None,
        
        # 评审
        scores={},
        overall_score=0.0,
        critiques=[],
        improvements=[],
        refine_count=0,
        
        # 历史
        svg_history=[],
        
        # 流程
        phase="init",
        iteration=0,
        max_iterations=2,
        _validation_count=0,
        
        # 日志
        decision_log=[],
        
        # 元数据
        active_agents=[],
        start_time=time.time(),
        last_modified=time.time(),
        
        # 输出
        output_dir=None,
        sample_id=None,
    )


def create_state_from_video_request(
    topic: str,
    timestamp: float,
    context: Optional[Dict] = None,
    style: str = "educational"
) -> SVGState:
    """
    从视频增强系统的请求创建状态
    
    这是视频系统调用SVG Agent的主要接口
    
    Args:
        topic: 主题描述
        timestamp: 视频时间戳
        context: 上下文信息
        style: 风格类型
    """
    return create_initial_state(
        input_text=topic,
        context=style,
        video_timestamp=timestamp,
        video_context=context or {}
    )
