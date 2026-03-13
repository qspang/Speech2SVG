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
            结构化卡片 {label, hero_text, explanation, style, ...}
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
            
            # 根据卡片内容获取样式（含局部区域上下文）
            style = self._get_card_style(
                structured.get('label', 'insight'),
                scene_info,
                region_context
            )
            
            return {
                'type': 'text',
                'label': structured['label'],
                'hero_text': structured['hero_text'],
                'explanation': structured['explanation'],
                'layout': 'vertical',
                'style': style,
                'use_glassmorphism': True # Always use glassmorphism for new design
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
            
            system_prompt = """You are a Visual Copywriting Director and Cognitive Scientist specializing in video enhancements.
Mission: Transform verbose transcripts into profound, highly-scannable "Golden Sentences" or "Deep Decoder" annotations.

Core Principle: **ELEVATE AND EXPLAIN, DO NOT JUST SUMMARIZE.**
Your goal is to extract the absolute essence of what is being said, making it emotionally resonant or cerebrally clear.

Context Types:
1. **Hardcore Concepts (Deep Decoding)**
   If the speaker mentions a complex term (e.g., "Markov Chain", "First Principles"):
   - Label: [ 🧠 Noun / Concept ]
   - Hero Text: The exact concept name (very short, 2-5 words).
   - Explanation: A beautiful, extremely simple analogy or layman's explanation of that concept.

2. **Philosophical/Emotional (Golden Sentence)**
   If the speaker is giving advice, insight, or emotional narrative:
   - Label: [ ✨ Key Insight ]
   - Hero Text: The absolute most striking phrase or "punchline" from the text (max 15 words).
   - Explanation: The profound rule or truth behind that sentence.

Rule of Thumb:
- **hero_text** MUST be treated like a massive poster headline. Never write a paragraph here. Max 15 words.
- **explanation** is the director's commentary. Keep it under 30 words. Extremely sharp.
- NEVER literally repeat the transcript. Synthesize it.

Output Format (JSON):
{
  "label": "Tiny category tag with an emoji, e.g., [ 💡 Core Mechanism ] or [ ⚠️ Key Pitfall ]",
  "hero_text": "Massive, striking punchline or concept name (2-15 words)",
  "explanation": "Simple, penetrating explanation of the hero text (max 30 words)"
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
                'label': parsed.get('label', '[ ✨ Insight ]'),
                'hero_text': parsed.get('hero_text', ' '.join(transcript.split()[:5])),
                'explanation': parsed.get('explanation', ' '.join(transcript.split()[:20]))
            }
            
        except Exception as e:
            print(f"        LLM structuring failed: {e}")
            # Fallback: 将完整的字幕文字全放在 explanation 保护原始语意，不强行切割大字号。
            return {
                'label': '[ 💬 Note ]',
                'hero_text': '',
                'explanation': transcript
            }
    
    def _get_card_style(self, card_type: str, scene_info: Dict, region_context: Dict = None) -> Dict:
        """Strip solid backgrounds and borders; defer to HTML CSS for glassmorphism."""
        guide = scene_info.get('design_guide', {})
        # We only pass essential accent colors to HTML, avoiding overwriting the glass filter.
        accent = guide.get('recommended_accent', '#00f3ff')
        
        return {
            'accent_color': accent
        }
    
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
            'label': '[ 💬 Note ]',
            'hero_text': '',
            'explanation': transcript,
            'layout': 'vertical',
            'style': self._get_card_style('insight', scene_info),
            'use_glassmorphism': True
        }
