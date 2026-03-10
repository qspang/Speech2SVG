"""
Shared Context for SVG Agent System
====================================

SVG生成过程中的共享视觉上下文
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import time


@dataclass
class SharedVisualContext:
    """共享视觉上下文"""
    
    # ========== 输入信息 ==========
    input_text: str
    context_type: str
    
    # ========== 概念理解 ==========
    main_concept: str = ""
    sub_concepts: List[str] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    
    # ========== 视觉元素 ==========
    visual_elements: List[Dict[str, Any]] = field(default_factory=list)
    color_scheme: Dict[str, Any] = field(default_factory=dict)
    style_guidelines: Dict[str, Any] = field(default_factory=dict)
    
    # ========== 布局信息 ==========
    layout_structure: Dict[str, Any] = field(default_factory=dict)
    element_positions: List[Dict[str, Any]] = field(default_factory=list)
    
    # ========== 动画信息 ==========
    animations: List[Dict[str, Any]] = field(default_factory=list)
    timeline: Dict[str, Any] = field(default_factory=dict)
    
    # ========== 决策记录 ==========
    design_decisions: List[Dict[str, Any]] = field(default_factory=list)
    contributing_agents: List[str] = field(default_factory=list)
    
    # ========== 约束条件 ==========
    constraints: Dict[str, Any] = field(default_factory=dict)
    requirements: Dict[str, Any] = field(default_factory=dict)
    
    # ========== 元数据 ==========
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    
    def update_timestamp(self):
        """更新时间戳"""
        self.last_updated = time.time()
    
    def add_concept(self, concept: str, is_main: bool = False):
        """添加概念"""
        if is_main:
            self.main_concept = concept
        else:
            if concept not in self.sub_concepts:
                self.sub_concepts.append(concept)
        self.update_timestamp()
    
    def add_visual_element(self, element: Dict[str, Any]):
        """添加视觉元素"""
        self.visual_elements.append({
            **element,
            'timestamp': time.time()
        })
        self.update_timestamp()
    
    def record_decision(
        self,
        agent_id: str,
        category: str,
        decision: str,
        reasoning: str,
        confidence: float = 0.8
    ) -> str:
        """记录设计决策"""
        decision_id = f"{agent_id}_{category}_{len(self.design_decisions)}"
        
        self.design_decisions.append({
            'id': decision_id,
            'agent_id': agent_id,
            'category': category,
            'decision': decision,
            'reasoning': reasoning,
            'confidence': confidence,
            'timestamp': time.time()
        })
        
        if agent_id not in self.contributing_agents:
            self.contributing_agents.append(agent_id)
        
        self.update_timestamp()
        return decision_id
    
    def set_color_scheme(self, scheme: Dict[str, Any]):
        """设置色彩方案"""
        self.color_scheme = scheme
        self.update_timestamp()
    
    def set_layout(self, layout: Dict[str, Any]):
        """设置布局"""
        self.layout_structure = layout
        self.update_timestamp()
    
    def add_animation(self, animation: Dict[str, Any]):
        """添加动画"""
        self.animations.append({
            **animation,
            'timestamp': time.time()
        })
        self.update_timestamp()
    
    def to_design_brief(self) -> str:
        """生成设计简报"""
        brief = f"""
=== SVG Design Brief ===

Input: {self.input_text}
Context: {self.context_type}

Main Concept: {self.main_concept}
Sub-concepts: {', '.join(self.sub_concepts)}

Visual Elements: {len(self.visual_elements)} elements defined
Animations: {len(self.animations)} animations planned
Design Decisions: {len(self.design_decisions)} decisions made
Contributing Agents: {', '.join(self.contributing_agents)}

Color Scheme: {self.color_scheme.get('name', 'Not set')}
Layout: {self.layout_structure.get('type', 'Not set')}

========================
"""
        return brief
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要信息"""
        return {
            'main_concept': self.main_concept,
            'sub_concepts_count': len(self.sub_concepts),
            'visual_elements_count': len(self.visual_elements),
            'animations_count': len(self.animations),
            'decisions_count': len(self.design_decisions),
            'agents_count': len(self.contributing_agents),
            'has_color_scheme': bool(self.color_scheme),
            'has_layout': bool(self.layout_structure)
        }


def create_initial_context(input_text: str, context_type: str) -> SharedVisualContext:
    """
    创建初始共享上下文
    
    Args:
        input_text: 输入文本
        context_type: 上下文类型
    """
    return SharedVisualContext(
        input_text=input_text,
        context_type=context_type,
        constraints={
            'max_elements': 15,
            'max_colors': 6,
            'animation_duration': 5.0
        },
        requirements={
            'educational': True,
            'accessible': True,
            'responsive': False
        }
    )
