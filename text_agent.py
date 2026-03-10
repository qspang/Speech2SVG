"""
Text Agent
==========

视觉笔记设计师 - 知识结构化卡片生成
"""

import os
from typing import Dict


class TextAgent:
    """文字卡片Agent - 将字幕转为结构化知识卡片"""
    
    def __init__(self, llm_type: str):
        """初始化"""
        self.llm_type = llm_type
    
    def generate_knowledge_card(
        self,
        transcript: str,
        scene_info: Dict,
        duration: float,
        layout_info: Dict = None
    ) -> Dict:
        """
        生成知识卡片
        
        Args:
            transcript: 该时间段的完整原话（字幕）
            scene_info: 场景视觉信息
            duration: 持续时长
            layout_info: 布局信息（含局部区域上下文 region_context）
            
        Returns:
            结构化卡片 {title, body, card_type, style, ...}
        """
        if layout_info is None:
            layout_info = {}
        region_context = layout_info.get('region_context', {})
        
        try:
            # LLM知识结构化
            structured = self._llm_structure_knowledge(
                transcript,
                scene_info,
                duration
            )
            
            # 根据卡片类型获取样式（含局部区域上下文）
            style = self._get_card_style(
                structured['card_type'],
                scene_info,
                region_context
            )
            
            return {
                'type': 'text',
                'title': structured['title'],
                'body': structured['body'],
                'card_type': structured['card_type'],
                'layout': structured.get('layout', 'vertical'),
                'style': style,
                'use_glassmorphism': self._should_use_glass(scene_info, region_context)
            }
            
        except Exception as e:
            print(f"      Text card generation failed: {e}")
            return self._fallback_text_card(transcript, scene_info)
    
    def _llm_structure_knowledge(
        self,
        transcript: str,
        scene_info: Dict,
        duration: float
    ) -> Dict:
        """
        LLM知识结构化
        
        核心任务：从字幕提取结构化知识，而非金句
        """
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'svg_agent'))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import SystemMessage, HumanMessage
            
            llm = CustomChatModel(llm_type=self.llm_type, temperature=0.7)
            
            design_context = scene_info.get('design_guide', {}).get('text_prompt', '')
            
            system_prompt = """You are a Visual Knowledge Architect specializing in educational content cards.

Mission: Transform verbose speech transcripts into structured, scannable knowledge cards.

Core Principle: **EXPLAIN, DON'T JUST EXTRACT**
- Your goal is to help viewers UNDERSTAND complex concepts
- Go beyond finding "good quotes" - structure the underlying knowledge
- Prioritize clarity and insight over verbatim reproduction

Card Types (Choose based on content):

1. **definition** - What is X?
   When: Explaining a concept/term/principle
   Title: The concept name (2-4 words)
   Body: Clear definition + key traits (20-40 words)
   Example: 
   Title: "First Principles Thinking"
   Body: "Breaking complex problems into fundamental truths, then reasoning up from scratch. Avoids assumptions. Core method: question everything until only irrefutable facts remain."

2. **process** - How does X work?
   When: Explaining mechanisms/algorithms/workflows
   Title: Process name (2-4 words)
   Body: Step-by-step with clear progression (30-50 words)
   Example:
   Title: "TCP 3-Way Handshake"
   Body: "1) Client sends SYN packet 2) Server responds SYN-ACK 3) Client confirms with ACK. Result: reliable connection established. Purpose: ensure both sides ready before data transfer."

3. **comparison** - X vs Y
   When: Contrasting options/approaches
   Title: "A vs B" format (3-5 words)
   Body: Key differences + when to use each (25-40 words)
   Example:
   Title: "Stack vs Heap Memory"
   Body: "Stack: Fast, fixed-size, automatic cleanup. Heap: Flexible size, manual management, slower. Use stack for local variables, heap for dynamic allocations."

4. **insight** - Key takeaway
   When: Important conclusions/lessons/principles
   Title: The insight (2-5 words)
   Body: Explanation + implications (20-35 words)
   Example:
   Title: "Premature Optimization Evil"
   Body: "Optimizing before profiling wastes time. Profile first, identify real bottlenecks, then optimize. Remember: 80% time spent in 20% code."

5. **warning** - Critical caveat
   When: Common mistakes/pitfalls/gotchas
   Title: "⚠️ [Issue]" (2-4 words)
   Body: What to avoid + why dangerous (25-40 words)
   Example:
   Title: "⚠️ SQL Injection Risk"
   Body: "Never concatenate user input into queries. Attackers inject malicious SQL. Always use parameterized queries or ORMs. One vulnerability compromises entire database."

6. **example** - Concrete illustration
   When: Abstract concept needs real-world grounding
   Title: "Example: [Topic]" (3-5 words)
   Body: Specific scenario demonstrating concept (25-45 words)
   Example:
   Title: "Example: MapReduce in Action"
   Body: "Counting word frequency: Map splits text into (word, 1) pairs across machines. Reduce aggregates counts per word. Processes terabytes in parallel. Google search index built this way."

Design Rules:
- Title must be scannable (viewer gets it in 1 second)
- Body must explain, not just list
- Use active voice and concrete language
- Avoid meta-commentary ("It's important to note that...")
- Number steps explicitly when describing processes
- Compare/contrast directly when showing differences

Output Format (JSON):
{
  "card_type": "definition/process/comparison/insight/warning/example",
  "title": "Concise, memorable title (2-5 words)",
  "body": "Clear explanation with structure (20-50 words)",
  "layout": "vertical/horizontal"
}"""
            
            prompt = f"""Design a knowledge card from this transcript:

Transcript: "{transcript}"

Duration: {duration:.1f}s
Visual Context: {design_context}

Analyze the core knowledge being conveyed. Structure it into a clear, visual-friendly card.
Focus on UNDERSTANDING the concept, not just extracting text.

Return JSON only."""
            
            messages = [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
            result = llm._generate(messages)
            content = result.generations[0].message.content
            
            parsed = llm.parse_json_response(content)
            
            return {
                'card_type': parsed.get('card_type', 'insight'),
                'title': parsed.get('title', ' '.join(transcript.split()[:4])),
                'body': parsed.get('body', ' '.join(transcript.split()[:25])),
                'layout': parsed.get('layout', 'vertical')
            }
            
        except Exception as e:
            print(f"        LLM structuring failed: {e}")
            # Fallback: 简单提取
            words = transcript.split()
            return {
                'card_type': 'insight',
                'title': ' '.join(words[:4]),
                'body': ' '.join(words[:25]),
                'layout': 'vertical'
            }
    
    def _get_card_style(self, card_type: str, scene_info: Dict, region_context: Dict = None) -> Dict:
        """根据卡片类型、场景和位置区域生成样式"""
        if region_context is None:
            region_context = {}
        
        guide = scene_info.get('design_guide', {})
        
        # Priority: region_context (local) > design_guide (global) > defaults
        if region_context.get('region_bg_color'):
            bg = region_context['region_bg_color']
            text = region_context.get('contrast_text_color', '#ffffff')
        else:
            bg = guide.get('recommended_bg', '#1a1a1a')
            text = guide.get('recommended_text', '#ffffff')
        
        accent = guide.get('recommended_accent', '#00f3ff')
        
        # Adjust opacity based on region complexity
        region_type = region_context.get('region_type', 'solid')
        if region_type == 'complex':
            bg_opacity = 'ee'  # More opaque on busy backgrounds
        elif region_type == 'gradient':
            bg_opacity = 'dd'
        else:
            bg_opacity = 'cc'  # More transparent on clean backgrounds
        
        base = {
            'padding': '24px',
            'border_radius': '12px',
            'font_family': 'system-ui, -apple-system, sans-serif'
        }
        
        styles = {
            'definition': {
                **base,
                'background': f'linear-gradient(135deg, {bg}{bg_opacity}, {bg}dd)',
                'border_left': f'4px solid #3498db',
                'title_size': '22px',
                'body_size': '16px',
                'title_color': '#3498db',
                'body_color': text
            },
            'process': {
                **base,
                'background': f'{bg}{bg_opacity}',
                'border': f'2px solid #2ecc71',
                'title_size': '20px',
                'body_size': '15px',
                'title_color': '#2ecc71',
                'body_color': text,
                'body_line_height': '1.8'
            },
            'warning': {
                **base,
                'background': 'rgba(231, 76, 60, 0.15)',
                'border': '2px solid #e74c3c',
                'title_size': '20px',
                'body_size': '15px',
                'title_color': '#e74c3c',
                'body_color': text
            },
            'comparison': {
                **base,
                'background': f'{bg}{bg_opacity}',
                'border': f'1px solid #9b59b680',
                'title_size': '19px',
                'body_size': '15px',
                'title_color': '#9b59b6',
                'body_color': text
            },
            'example': {
                **base,
                'background': f'{bg}{bg_opacity}',
                'border': f'2px dashed #f39c1260',
                'title_size': '18px',
                'body_size': '15px',
                'title_color': '#f39c12',
                'body_color': text
            },
            'insight': {
                **base,
                'background': f'{bg}{bg_opacity}',
                'border': f'1px solid {text}40',
                'title_size': '21px',
                'body_size': '16px',
                'title_color': accent,
                'body_color': text
            }
        }
        
        return styles.get(card_type, styles['insight'])
    
    def _should_use_glass(self, scene_info: Dict, region_context: Dict = None) -> bool:
        """Decide whether to use glassmorphism backdrop based on region complexity"""
        if region_context and region_context.get('region_type') in ('complex', 'gradient'):
            return True  # Busy background needs glass backdrop for readability
        return not scene_info.get('is_single_scene', True)
    
    def _fallback_text_card(self, transcript: str, scene_info: Dict) -> Dict:
        """降级卡片"""
        words = transcript.split()
        return {
            'type': 'text',
            'title': ' '.join(words[:4]),
            'body': ' '.join(words[:20]),
            'card_type': 'insight',
            'layout': 'vertical',
            'style': self._get_card_style('insight', scene_info),
            'use_glassmorphism': True
        }
