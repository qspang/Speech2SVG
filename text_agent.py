"""
Text Agent
==========

视觉笔记设计师 - 知识结构化卡片生成
"""

import os
import re
from typing import Dict, List


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
                'hero_text': self._compact_text(structured['hero_text'], max_words=10, max_chars=52),
                'explanation': self._compact_text(structured['explanation'], max_words=18, max_chars=110),
                'layout': 'vertical',
                'style': style,
                'use_glassmorphism': True # Always use glassmorphism for new design
            }
            
        except Exception as e:
            print(f"      Text card generation failed: {e}")
            return self._fallback_text_card(transcript, scene_info)

    def generate_misconception_card(
        self,
        transcript: str,
        scene_info: Dict,
        payload: Dict,
        layout_info: Dict = None
    ) -> Dict:
        if layout_info is None:
            layout_info = {}
        style = self._get_card_style('misconception', scene_info, layout_info.get('region_context', {}))
        style['accent_color'] = '#f59e0b'
        display = self._build_misconception_display_payload(transcript, payload, layout_info)
        return {
            'type': 'misconception',
            'label': payload.get('display_label', '[ ⚠ Misconception Alert ]'),
            'hero_text': display['wrong_summary'],
            'explanation': display['correct_summary'],
            'why_confusing': display['why_summary'],
            'wrong_detail': payload.get('likely_misconception', transcript[:160]),
            'correct_detail': payload.get('correct_understanding', transcript),
            'variant': display['variant'],
            'style': style,
            'use_glassmorphism': True,
        }

    def generate_mechanism_chain_card(
        self,
        transcript: str,
        scene_info: Dict,
        payload: Dict,
        layout_info: Dict = None
    ) -> Dict:
        if layout_info is None:
            layout_info = {}
        style = self._get_card_style('mechanism', scene_info, layout_info.get('region_context', {}))
        style['accent_color'] = style.get('accent_color', '#00f3ff')
        display = self._build_mechanism_display_payload(transcript, payload, layout_info)
        return {
            'type': 'mechanism_chain',
            'chain_title': display['title'],
            'stages': display['stages'],
            'links': payload.get('links', []),
            'current_focus_stage': payload.get('current_focus_stage', 0),
            'visual_hint': payload.get('visual_hint', ''),
            'variant': display['variant'],
            'style': style,
            'use_glassmorphism': True,
        }

    def _build_misconception_display_payload(self, transcript: str, payload: Dict, layout_info: Dict) -> Dict:
        width = layout_info.get('width', 350)
        wrong = payload.get('likely_misconception', transcript)
        correct = payload.get('correct_understanding', transcript)
        why = payload.get('why_confusing', '')
        variant = 'compare'
        if width < 420:
            variant = 'stacked'

        compact = self._llm_compact_misconception(wrong, correct, why)
        if not compact:
            compact = {
                'wrong_summary': self._compact_text(wrong, max_words=8, max_chars=42),
                'correct_summary': self._compact_text(correct, max_words=10, max_chars=56),
                'why_summary': self._compact_text(why or transcript, max_words=14, max_chars=88),
            }

        return {
            'wrong_summary': compact['wrong_summary'],
            'correct_summary': compact['correct_summary'],
            'why_summary': compact['why_summary'],
            'variant': variant,
        }

    def _build_mechanism_display_payload(self, transcript: str, payload: Dict, layout_info: Dict) -> Dict:
        width = layout_info.get('width', 640)
        variant = 'path'
        if width < 560:
            variant = 'stacked'

        stages = payload.get('stages', []) or [transcript]
        title = payload.get('chain_title', transcript[:60])
        compact = self._llm_compact_mechanism(title, stages)
        if compact:
            title = compact.get('title', title)
            stages = compact.get('stages', stages)
        else:
            title = self._compact_text(title, max_words=7, max_chars=42)
            stages = [self._compact_text(stage, max_words=4, max_chars=26) for stage in stages[:4]]

        if variant == 'stacked':
            stages = [self._compact_text(stage, max_words=6, max_chars=34) for stage in stages[:4]]

        return {
            'title': title,
            'stages': stages[:4],
            'variant': variant,
        }

    def _llm_compact_misconception(self, wrong: str, correct: str, why: str) -> Dict:
        if max(len(wrong), len(correct), len(why or "")) < 100:
            return {}
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'svg_agent'))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = CustomChatModel(llm_type=self.llm_type, temperature=0.2)
            system_prompt = """You compress misconception overlays for narrow video cards.

Return JSON:
{
  "wrong_summary": "2-8 words",
  "correct_summary": "3-10 words",
  "why_summary": "one short sentence, max 16 words"
}

Rules:
- Keep the original meaning.
- No filler.
- Must be easy to scan on a narrow on-video overlay.
"""
            prompt = f"""Wrong understanding:
{wrong}

Correct understanding:
{correct}

Why confusing:
{why}

Return JSON only."""
            result = llm._generate([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
            parsed = llm.parse_json_response(result.generations[0].message.content)
            return {
                'wrong_summary': self._compact_text(parsed.get('wrong_summary', wrong), max_words=8, max_chars=42),
                'correct_summary': self._compact_text(parsed.get('correct_summary', correct), max_words=10, max_chars=56),
                'why_summary': self._compact_text(parsed.get('why_summary', why), max_words=16, max_chars=88),
            }
        except Exception:
            return {}

    def _llm_compact_mechanism(self, title: str, stages: List[str]) -> Dict:
        joined = " | ".join(stages)
        if max(len(title), len(joined)) < 90:
            return {}
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'svg_agent'))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = CustomChatModel(llm_type=self.llm_type, temperature=0.2)
            system_prompt = """You compress mechanism-chain overlays for narrow video cards.

Return JSON:
{
  "title": "max 6 words",
  "stages": ["max 4 words", "max 4 words", "max 4 words"]
}

Rules:
- Preserve the process logic.
- Prefer nouns + verbs over long clauses.
- Keep it readable on a narrow overlay.
"""
            prompt = f"""Title:
{title}

Stages:
{joined}

Return JSON only."""
            result = llm._generate([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
            parsed = llm.parse_json_response(result.generations[0].message.content)
            stages_out = [self._compact_text(item, max_words=4, max_chars=26) for item in parsed.get('stages', []) if str(item).strip()]
            return {
                'title': self._compact_text(parsed.get('title', title), max_words=6, max_chars=38),
                'stages': stages_out or [self._compact_text(stage, max_words=4, max_chars=26) for stage in stages[:4]],
            }
        except Exception:
            return {}

    def _compact_text(self, text: str, max_words: int, max_chars: int) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        if not cleaned:
            return ""
        words = cleaned.split()
        compact = " ".join(words[:max_words])
        if len(compact) > max_chars:
            compact = compact[:max_chars].rsplit(" ", 1)[0]
        return compact.rstrip(" ,.;:-") + ("..." if len(cleaned) > len(compact) and compact else "")
    
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
            'explanation': self._compact_text(transcript, max_words=20, max_chars=120),
            'layout': 'vertical',
            'style': self._get_card_style('insight', scene_info),
            'use_glassmorphism': True
        }
