"""
Base Agent for Multi-Agent Infographic System (v2 Simplified)
=============================================================

Simplified base agent for direct SVG generation workflow.
"""

from typing import Dict, List, Any, Optional, Tuple
from abc import ABC, abstractmethod
import time
import json

from state import SVGState, AgentMessage
from shared_context import SharedVisualContext


class BaseAgent(ABC):
    """
    Base Agent class (v2 Simplified)
    """
    
    def __init__(
        self, 
        agent_id: str, 
        llm_type: str = "claude-sonnet-4-5-20250929",
        temperature: float = 0.7
    ):
        self.agent_id = agent_id
        self.llm_type = llm_type
        self.temperature = temperature
        self.llm = None
        
        self.role_description = ""
        self.capabilities: List[str] = []
    
    def _ensure_llm(self):
        """Lazy initialize LLM"""
        if self.llm is None:
            from custom_chat_model import CustomChatModel
            self.llm = CustomChatModel(
                llm_type=self.llm_type, 
                temperature=self.temperature
            )
    
    # ========== Core Methods ==========
    
    @abstractmethod
    def execute(self, state: SVGState) -> SVGState:
        """Execute agent's main task"""
        pass
    
    @abstractmethod
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        """Check if agent can contribute in current phase"""
        pass
    
    # ========== Context Access ==========
    
    def get_context(self, state: SVGState) -> SharedVisualContext:
        """Get shared visual context"""
        return state["shared_context"]
    
    def get_design_brief(self, state: SVGState) -> str:
        """Get complete design brief"""
        ctx = self.get_context(state)
        return ctx.to_design_brief()
    
    # ========== Context Updates ==========
    
    def record_decision(
        self,
        state: SVGState,
        category: str,
        decision: str,
        reasoning: str,
        confidence: float = 0.8
    ) -> str:
        """Record a design decision"""
        ctx = self.get_context(state)
        decision_id = ctx.record_decision(
            agent_id=self.agent_id,
            category=category,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence
        )
        
        state["decision_log"].append({
            "agent_id": self.agent_id,
            "timestamp": time.time(),
            "category": category,
            "decision": decision,
            "phase": state["phase"]
        })
        
        return decision_id
    
    # ========== Communication ==========
    
    def send_message(
        self,
        state: SVGState,
        content: str,
        message_type: str = "contribution",
        target_agent: str = None
    ):
        """Send message to other agents"""
        message = AgentMessage(
            agent_id=self.agent_id,
            content=content,
            timestamp=time.time(),
            message_type=message_type,
            target_agent=target_agent
        )
        state["messages"].append(message)
    
    def get_messages_for_me(self, state: SVGState) -> List[AgentMessage]:
        """Get messages directed to this agent"""
        return [
            m for m in state["messages"] 
            if m["target_agent"] == self.agent_id or m["target_agent"] is None
        ]
    
    # ========== LLM Calls ==========
    
    def invoke_llm(self, prompt: str, system_prompt: str = "") -> str:
        """Call LLM"""
        self._ensure_llm()
        
        from langchain_core.messages import SystemMessage, HumanMessage
        
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        result = self.llm._generate(messages)
        return result.generations[0].message.content
    
    def invoke_llm_json(self, prompt: str, system_prompt: str = "", max_retries: int = 3) -> Dict:
        """Call LLM and parse JSON response"""
        self._ensure_llm()
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                content = self.invoke_llm(prompt, system_prompt)
                result = self.llm.parse_json_response(content)
                return result
            except Exception as e:
                last_error = e
                self._log(f"JSON parsing failed (attempt {attempt + 1}/{max_retries}): {e}", "warning")
        
        raise Exception(f"Failed to parse JSON after {max_retries} attempts: {last_error}")
    
    def invoke_llm_with_image(
        self, 
        prompt: str, 
        image_path: str, 
        system_prompt: str = ""
    ) -> str:
        """Call LLM with vision capability"""
        self._ensure_llm()
        
        from langchain_core.messages import SystemMessage
        
        if self.llm_type == "glm-4.6v":
            vision_message = self.llm.create_vision_message_glm4v(prompt, image_path)
        else:
            vision_message = self.llm.create_vision_message(prompt, image_path)
        
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(vision_message)
        
        response = self.llm._generate(messages)
        return response.generations[0].message.content
    
    def invoke_llm_image_json(
        self,
        prompt: str,
        image_path: str,
        system_prompt: str = "",
        max_retries: int = 3
    ) -> Dict:
        """Call LLM with image and parse JSON"""
        self._ensure_llm()
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                content = self.invoke_llm_with_image(prompt, image_path, system_prompt)
                result = self.llm.parse_json_response(content)
                return result
            except Exception as e:
                last_error = e
                self._log(f"Vision JSON parsing failed (attempt {attempt + 1}/{max_retries}): {e}", "warning")
        
        raise Exception(f"Failed to parse vision JSON after {max_retries} attempts: {last_error}")
    
    # ========== Utility ==========
    
    def _log(self, message: str, level: str = "info"):
        """Log output"""
        prefix = {
            "info": "ℹ️",
            "success": "✓",
            "warning": "⚠️",
            "error": "✗"
        }.get(level, "")
        
        print(f"[{self.agent_id}] {prefix} {message}")
