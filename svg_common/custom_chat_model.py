"""
Custom ChatModel for LangGraph
兼容base_agent的LLM调用方式 + Vision能力

支持的模型:
- claude-sonnet-4-5-20250929
- deepseek-v3
- deepseek-chat
- glm-4.6
- glm-4.6v (视觉模型)
- glm-4.7
- qwen系列
- gpt4-o
"""
import re
from typing import Any, Dict, Iterator, List, Optional, Union
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun
from pydantic import Field
from openai import OpenAI
import os
import json
import base64


class CustomChatModel(BaseChatModel):
    """
    自定义ChatModel，支持多种LLM后端
    """
    llm_type: str = "deepseek-v3"
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 8000
    glm_max_tokens: int = 20000
    claude_max_tokens: int = 16000
    streaming: bool = False
    client: Any = Field(default=None, exclude=True)
    use_developer_role: bool = False 

    def __init__(self, llm_type: str = "deepseek-v3", temperature: float = 0.7, **kwargs):
        super().__init__(**kwargs)
        self.llm_type = llm_type
        self.temperature = temperature
        self.streaming = False
        self.use_developer_role = False
        
        # 默认超时时间（秒）
        DEFAULT_TIMEOUT = 600.0 
        
        if llm_type == "gpt4-o":
            self.client = OpenAI(
                timeout=DEFAULT_TIMEOUT
            )
        elif llm_type == "qwen3.5-plus":
            self.client = OpenAI(
                # api_key=os.getenv("PLAN_API_KEY"),
                # base_url="https://coding.dashscope.aliyuncs.com/v1",
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        # elif llm_type == "kimi-k2.5":
        #     self.client = OpenAI(
        #         api_key=os.getenv("PLAN_API_KEY"),
        #         base_url="https://coding.dashscope.aliyuncs.com/v1",
        #         timeout=DEFAULT_TIMEOUT
        #     )
        #     self.streaming = True
        elif llm_type == "kimi-k2.5":
            self.client = OpenAI(
                api_key=os.getenv("DY_API_KEY"),
                base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type == "Doubao-Seed-2.0-Code":
            self.client = OpenAI(
                api_key=os.getenv("DY_API_KEY"),
                base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type == "MiniMax-M2.5":
            self.client = OpenAI(
                api_key=os.getenv("PLAN_API_KEY"),
                base_url="https://coding.dashscope.aliyuncs.com/v1",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type == "deepseek-chat":
            self.client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY_DS"),
                base_url="https://api.deepseek.com/v1",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type == "deepseek-v3":
            self.client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type in ["gemini-3.1-pro-high", "claude-sonnet-4-6", "claude-opus-4-6-thinking", "gpt-5.3-codex", "gemini-3.1-pro-low"]:
            self.client = OpenAI(
                api_key=os.getenv("XIAOCHI_API_KEY"),
                base_url="https://llm.xiaochisaas.com/v1",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type == "claude-sonnet-4-5-20250929":
            self.client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY_YI"),
                base_url="http://api.apiyi.com/v1",
                timeout=DEFAULT_TIMEOUT
            )
        elif llm_type == "glm-5":
            self.client = OpenAI(
                # api_key=os.getenv("PLAN_API_KEY"),
                # base_url="https://coding.dashscope.aliyuncs.com/v1",
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type == "glm-4.6":
            self.client = OpenAI(
                api_key=os.getenv("ZHIPUAI_API_KEY"),
                base_url="https://open.bigmodel.cn/api/paas/v4",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type == "glm-4.6v":
            self.client = OpenAI(
                api_key=os.getenv("ZHIPUAI_API_KEY"),
                base_url="https://open.bigmodel.cn/api/paas/v4",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif llm_type == "glm-4.7":
            self.client = OpenAI(
                api_key=os.getenv("ZHIPUAI_API_KEY"),
                base_url="https://open.bigmodel.cn/api/paas/v4",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif "glm" in llm_type:
            self.client = OpenAI(
                api_key=os.getenv("ZHIPUAI_API_KEY"),
                base_url="https://open.bigmodel.cn/api/paas/v4",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        elif "qwen" in llm_type:
            self.client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
        else:
            self.client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY_YI"),
                base_url="http://api.apiyi.com/v1",
                timeout=DEFAULT_TIMEOUT
            )
            self.streaming = True
            self.use_developer_role = True

    @property
    def _llm_type(self) -> str:
        return self.llm_type

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict]:
        """转换消息格式为OpenAI API格式"""
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                role = "developer" if self.use_developer_role else "system"
                converted.append({"role": role, "content": msg.content})
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                converted.append({"role": "assistant", "content": msg.content})
        return converted

    def _convert_vision_messages_glm4v(self, messages: List[BaseMessage]) -> List[Dict]:
        """
        专门为GLM-4.6V转换多模态消息的格式
        """
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                role = "developer" if self.use_developer_role else "system"
                converted.append({"role": role, "content": msg.content})
            elif isinstance(msg, HumanMessage):
                if isinstance(msg.content, list):
                    text_parts = []
                    image_parts = []
                    for part in msg.content:
                        if part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                        elif part.get("type") == "image_url":
                            image_url = part.get("image_url", {}).get("url", "")
                            if image_url.startswith("data:image/"):
                                image_parts.append(image_url)
                    
                    if image_parts:
                        content_list = []
                        for image in image_parts:
                            content_list.append({
                                "type": "image_url",
                                "image_url": {"url": image}
                            })
                        for text in text_parts:
                            if text.strip():
                                content_list.append({"type": "text", "text": text})
                        converted.append({"role": "user", "content": content_list})
                    else:
                        combined_text = "\n".join(text_parts)
                        converted.append({"role": "user", "content": combined_text})
                else:
                    converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                converted.append({"role": "assistant", "content": msg.content})
        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """生成响应"""
        # 检查是否包含多模态消息
        has_vision_content = any(
            isinstance(msg.content, list) and any(
                item.get("type") == "image_url" for item in msg.content if isinstance(item, dict)
            )
            for msg in messages if isinstance(msg, HumanMessage)
        )
        
        # 根据模型类型选择消息转换方式
        if self.llm_type == "glm-4.6v" and has_vision_content:
            input_messages = self._convert_vision_messages_glm4v(messages)
        else:
            input_messages = self._convert_messages(messages)

        content = self._call_api(input_messages)
        
        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    def _call_api(self, input_messages: List[Dict]) -> str:
        """调用API并返回内容"""
        
        if self.llm_type == "gpt4-o":
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=input_messages,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            return response.choices[0].message.content
        
        elif self.llm_type == "glm-5":
            response = self.client.chat.completions.create(
                model=self.llm_type,
                messages=input_messages,
                top_p=self.top_p,
                max_tokens=self.claude_max_tokens
            )
            return response.choices[0].message.content
        
        elif self.llm_type == "qwen3.5-plus":
            response = self.client.chat.completions.create(
                model=self.llm_type,
                messages=input_messages,
                top_p=self.top_p,
                max_tokens=self.claude_max_tokens
            )
            return response.choices[0].message.content

        elif self.llm_type == "glm-4.6v":
            if not self.streaming:
                response = self.client.chat.completions.create(
                    model="glm-4.6v",
                    messages=input_messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.glm_max_tokens,
                )
                return response.choices[0].message.content
            else:
                return self._stream_response("glm-4.6v", input_messages, self.glm_max_tokens)
        
        elif self.llm_type == "glm-4.6":
            if not self.streaming:
                response = self.client.chat.completions.create(
                    model="glm-4.6",
                    messages=input_messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.glm_max_tokens
                )
                return response.choices[0].message.content
            else:
                return self._stream_response("glm-4.6", input_messages, self.glm_max_tokens)
        
        elif self.llm_type == "glm-4.7":
            if not self.streaming:
                response = self.client.chat.completions.create(
                    model="glm-4.7",
                    messages=input_messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.glm_max_tokens
                )
                return response.choices[0].message.content
            else:
                return self._stream_response("glm-4.7", input_messages, self.glm_max_tokens)
        
        elif "glm" in self.llm_type:
            if not self.streaming:
                response = self.client.chat.completions.create(
                    model=self.llm_type,
                    messages=input_messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.glm_max_tokens
                )
                return response.choices[0].message.content
            else:
                return self._stream_response(self.llm_type, input_messages, self.glm_max_tokens)
        
        elif self.llm_type in ["deepseek-chat", "deepseek-v3", "gemini-3.1-pro-high", "claude-sonnet-4-6", "claude-opus-4-6-thinking", "gpt-5.3-codex", "gemini-3.1-pro-low"]:
            if not self.streaming:
                response = self.client.chat.completions.create(
                    model=self.llm_type,
                    messages=input_messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                )
                return response.choices[0].message.content
            else:
                return self._stream_response(self.llm_type, input_messages)

        elif self.llm_type == "claude-sonnet-4-5-20250929":
            response = self.client.chat.completions.create(
                model=self.llm_type,
                messages=input_messages,
                top_p=self.top_p,
                max_tokens=self.claude_max_tokens
            )
            return response.choices[0].message.content
        
        elif "qwen" in self.llm_type:
            if not self.streaming:
                response = self.client.chat.completions.create(
                    model=self.llm_type,
                    messages=input_messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.max_tokens
                )
                return response.choices[0].message.content
            else:
                return self._stream_response(self.llm_type, input_messages, self.max_tokens)
        
        else:
            response = self.client.chat.completions.create(
                model=self.llm_type,
                messages=input_messages,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.claude_max_tokens
            )
            return response.choices[0].message.content

    def _stream_response(self, model: str, messages: List[Dict], max_tokens: int = None) -> str:
        """流式响应处理"""
        answer_content = ""
        kwargs = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
            
        completion = self.client.chat.completions.create(**kwargs)
        
        for chunk in completion:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    answer_content += delta.content
        
        return answer_content

    def parse_json_response(self, content: Any) -> Union[Dict, list]:
        """
        鲁棒的 JSON 解析逻辑
        """
        if hasattr(content, 'content'):
            content = content.content
        if not content:
            return {}
        
        content_str = str(content).strip()

        # 策略 1: 直接解析
        try:
            return json.loads(content_str)
        except json.JSONDecodeError:
            pass

        # 策略 2: 正则提取 Markdown 代码块
        patterns = [
            r'```(?:json)?\s*\n?(.*?)\n?```',
            r'`(.*?)`',
        ]
        for pattern in patterns:
            match = re.search(pattern, content_str, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except:
                    continue

        # 策略 3: 括号平衡法
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            try:
                start_idx = content_str.find(start_char)
                if start_idx != -1:
                    count = 0
                    for i in range(start_idx, len(content_str)):
                        if content_str[i] == start_char: count += 1
                        elif content_str[i] == end_char: count -= 1
                        if count == 0:
                            return json.loads(content_str[start_idx:i+1])
            except:
                pass

        # 策略 4: 贪婪匹配法
        try:
            first_brace = content_str.find('{')
            last_brace = content_str.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                potential_json = content_str[first_brace:last_brace+1]
                try:
                    return json.loads(potential_json)
                except:
                    pass
            
            first_bracket = content_str.find('[')
            last_bracket = content_str.rfind(']')
            if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
                potential_list = content_str[first_bracket:last_bracket+1]
                try:
                    return json.loads(potential_list)
                except:
                    pass
        except:
            pass

        # 策略 5: 暴力清理
        try:
            cleaned = re.sub(r'^.*?(?=[{\[])', '', content_str, flags=re.DOTALL)
            cleaned = re.sub(r'(?<=[}\]]). *$', '', cleaned, flags=re.DOTALL)
            return json.loads(cleaned)
        except:
            pass

        print(f"❌ JSON Parse Failed. Raw content sample:\n{content_str[:200]}...")
        return {}

    def create_vision_message(self, prompt_text: str, image_path: Optional[str]) -> HumanMessage:
        """
        构建多模态消息，根据模型类型选择合适的格式
        """
        # 如果是GLM-4.6V，使用专门的方法
        if self.llm_type == "glm-4.6v":
            return self.create_vision_message_glm4v(prompt_text, image_path)
        
        # 其他模型使用通用格式
        return self._create_vision_message_standard(prompt_text, image_path)

    def _create_vision_message_standard(self, prompt_text: str, image_path: Optional[str]) -> HumanMessage:
        """
        构建标准多模态消息，适配 Qwen-VL 和 GPT-4o 等
        """
        try:
            if not image_path or not os.path.exists(image_path):
                print("⚠️ [Vision] No image found, falling back to text only.")
                return HumanMessage(content=prompt_text)
            
            with open(image_path, "rb") as image_file:
                b64_img = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 确定媒体类型
            media_type = self._get_media_type(image_path)
            
            return HumanMessage(content=[
                {"type": "text", "text": prompt_text},
                {
                    "type": "image_url", 
                    "image_url": {
                        "url": f"data:{media_type};base64,{b64_img}"
                    }
                }
            ])
        except Exception as e:
            print(f"⚠️ [Vision] Error constructing message: {e}")
            return HumanMessage(content=f"Error analyzing image: {str(e)}. Prompt: {prompt_text}")

    def create_vision_message_glm4v(self, prompt_text: str, image_path: Optional[str]) -> HumanMessage:
        """
        专门为GLM-4.6V构建多模态消息
        """
        try:
            if not image_path or not os.path.exists(image_path):
                print("⚠️ [GLM-4.6V Vision] No image found, falling back to text only.")
                return HumanMessage(content=prompt_text)
            
            with open(image_path, "rb") as image_file:
                b64_img = base64.b64encode(image_file.read()).decode('utf-8')
            
            # GLM-4.6V特定格式：图像在前，文本在后
            return HumanMessage(content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_img}"
                    }
                },
                {
                    "type": "text",
                    "text": prompt_text
                }
            ])
        except Exception as e:
            print(f"⚠️ [GLM-4.6V Vision] Error constructing message: {e}")
            return HumanMessage(content=f"Error analyzing image: {str(e)}. Prompt: {prompt_text}")

    def _get_media_type(self, image_path: str) -> str:
        """根据文件扩展名获取媒体类型"""
        ext = image_path.lower().split('.')[-1]
        media_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp'
        }
        return media_types.get(ext, 'image/png')

    def supports_vision(self) -> bool:
        """检查当前模型是否支持视觉能力"""
        vision_models = [
            "glm-4.6v",
            "gpt4-o",
            "qwen-vl-plus",
            "qwen-vl-max",
            "claude-sonnet-4-5-20250929"
        ]
        return any(vm in self.llm_type.lower() for vm in vision_models)
