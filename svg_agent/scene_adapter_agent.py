"""
Scene Adapter Agent
====================

纯算法Agent — 将视频帧的场景分析结果转为SVG配色策略
不使用LLM，快速执行

输入: state["scene_context"] (来自上游 SceneAgent)
输出: state["color_scheme"] (供 VisualStrategist / SVGCreator 使用)
"""

from typing import Dict, Tuple
from base_agent import BaseAgent
from state import SVGState


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """#ffffff -> (255, 255, 255)"""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (128, 128, 128)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _luminance(hex_color: str) -> float:
    """计算相对亮度 [0-255]"""
    r, g, b = _hex_to_rgb(hex_color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _contrast_ratio(c1: str, c2: str) -> float:
    """WCAG对比度 (简化版)"""
    l1 = (_luminance(c1) + 0.05) / 255
    l2 = (_luminance(c2) + 0.05) / 255
    if l1 > l2:
        return l1 / l2
    return l2 / l1


def _darken(hex_color: str, factor: float = 0.3) -> str:
    """加深颜色"""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(
        max(0, int(r * (1 - factor))),
        max(0, int(g * (1 - factor))),
        max(0, int(b * (1 - factor)))
    )


def _lighten(hex_color: str, factor: float = 0.3) -> str:
    """提亮颜色"""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(
        min(255, int(r + (255 - r) * factor)),
        min(255, int(g + (255 - g) * factor)),
        min(255, int(b + (255 - b) * factor))
    )


def _complementary(hex_color: str) -> str:
    """互补色"""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(255 - r, 255 - g, 255 - b)


class SceneAdapterAgent(BaseAgent):
    """场景适配Agent — 视频帧→SVG配色方案（纯算法，无LLM）"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("scene_adapter", llm_type)
        self.role_description = "Adapt SVG colors to video scene"
        self.capabilities = ["color_adaptation"]
    
    def execute(self, state: SVGState) -> SVGState:
        """根据scene_context生成color_scheme"""
        self._log("Scene Adaptation...")
        
        scene_ctx = state.get("scene_context", {})
        input_text = state.get("input_text", "")
        
        if not scene_ctx:
            self._log("  No scene_context — using content-adaptive default")
            state["color_scheme"] = self._default_scheme(input_text)
        else:
            scheme = self._adapt_to_scene(scene_ctx)
            state["color_scheme"] = scheme
            self._log(f"  Background: {scheme['background']} | Mode: {scheme['mode']}")
        
        self.record_decision(
            state, "scene_adaptation",
            f"Color scheme: {state['color_scheme'].get('mode', 'unknown')}",
            f"BG: {state['color_scheme'].get('background', 'N/A')}"
        )
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "scene_adaptation":
            return True, 0.95
        return False, 0.0
    
    def _adapt_to_scene(self, scene_ctx: Dict) -> Dict:
        """
        核心适配逻辑
        
        根据视频帧的亮度/颜色决定SVG配色策略:
        - bright → 浅色/透明背景 + 深色文字
        - dark → 深色背景 + 亮色文字
        - medium → 半透明 + 对比文字
        """
        # 提取场景信息
        color_hierarchy = scene_ctx.get("color_hierarchy", {})
        color_metrics = scene_ctx.get("color_metrics", {})
        design_guide = scene_ctx.get("design_guide", {})
        
        # 视频帧背景色
        video_bg = color_hierarchy.get("background_color", "#1a1a1a")
        video_accent = color_hierarchy.get("accent_color", "#64ffda")
        video_text = color_hierarchy.get("text_color", "#ffffff")
        all_colors = color_hierarchy.get("all_colors", [])
        
        # 亮度等级
        brightness = color_metrics.get("brightness_level", "dark")
        brightness_val = color_metrics.get("brightness", 80)
        saturation = color_metrics.get("saturation_level", "moderate")
        temperature = color_metrics.get("temperature", "neutral")
        
        # 设计指南推荐色
        rec_bg = design_guide.get("recommended_bg", "")
        rec_accent = design_guide.get("recommended_accent", "")
        rec_secondary = design_guide.get("recommended_secondary", "")
        
        # === 决策逻辑 ===
        
        if brightness == "bright" or brightness_val > 160:
            # 视频画面明亮 → SVG用浅色/半透明背景
            return self._bright_scene_scheme(
                video_bg, video_accent, rec_bg, rec_accent, rec_secondary,
                all_colors, temperature
            )
        elif brightness == "dark" or brightness_val < 80:
            # 视频画面暗 → SVG用深色背景（但不一定是纯黑）
            return self._dark_scene_scheme(
                video_bg, video_accent, rec_bg, rec_accent, rec_secondary,
                all_colors, temperature
            )
        else:
            # 中等亮度 → 半透明策略
            return self._medium_scene_scheme(
                video_bg, video_accent, rec_bg, rec_accent, rec_secondary,
                all_colors, temperature
            )
    
    def _bright_scene_scheme(self, video_bg, video_accent, rec_bg, rec_accent,
                              rec_secondary, all_colors, temperature) -> Dict:
        """明亮场景：浅色/半透明背景 + 深色内容"""
        # 背景：使用视频背景色轻微调深，或半透明白
        bg = rec_bg or _darken(video_bg, 0.1)
        bg_lum = _luminance(bg)
        
        # 确保背景不是太暗（是明亮场景）
        if bg_lum < 150:
            bg = _lighten(video_bg, 0.2)
        
        # 文字：深色
        text = "#1a1a2e" if bg_lum > 128 else "#f0f6fc"
        
        # 强调色
        accent_1 = rec_accent or video_accent
        # 确保强调色与浅背景有对比
        if _contrast_ratio(accent_1, bg) < 2.0:
            accent_1 = _darken(accent_1, 0.3)
        
        accent_2 = rec_secondary or _complementary(accent_1)
        accent_3 = _darken(accent_1, 0.2)
        
        return {
            "mode": "bright",
            "background": bg,
            "background_opacity": 0.85,
            "text": text,
            "accent_1": accent_1,
            "accent_2": accent_2,
            "accent_3": accent_3,
            "overlay_style": "light-glass",
            "temperature": temperature,
        }
    
    def _dark_scene_scheme(self, video_bg, video_accent, rec_bg, rec_accent,
                            rec_secondary, all_colors, temperature) -> Dict:
        """暗色场景：深色背景 + 亮色内容"""
        # 背景：使用视频背景色或推荐色
        bg = rec_bg or video_bg
        bg_lum = _luminance(bg)
        
        # 确保背景是暗的
        if bg_lum > 80:
            bg = _darken(bg, 0.4)
        
        # 文字：亮色
        text = "#f0f6fc"
        
        # 强调色：使用鲜艳色
        accent_1 = rec_accent or video_accent
        if _luminance(accent_1) < 80:
            accent_1 = _lighten(accent_1, 0.4)
        
        accent_2 = rec_secondary or _lighten(_complementary(accent_1), 0.2)
        accent_3 = _lighten(accent_1, 0.3)
        
        return {
            "mode": "dark",
            "background": bg,
            "background_opacity": 0.92,
            "text": text,
            "accent_1": accent_1,
            "accent_2": accent_2,
            "accent_3": accent_3,
            "overlay_style": "dark-solid",
            "temperature": temperature,
        }
    
    def _medium_scene_scheme(self, video_bg, video_accent, rec_bg, rec_accent,
                              rec_secondary, all_colors, temperature) -> Dict:
        """中等亮度：半透明 + 模糊"""
        bg = rec_bg or video_bg
        bg_lum = _luminance(bg)
        
        # 文字色由亮度决定
        text = "#f0f6fc" if bg_lum < 128 else "#1a1a2e"
        
        accent_1 = rec_accent or video_accent
        accent_2 = rec_secondary or _complementary(accent_1)
        accent_3 = _lighten(accent_1, 0.15) if bg_lum < 128 else _darken(accent_1, 0.15)
        
        return {
            "mode": "medium",
            "background": bg,
            "background_opacity": 0.75,
            "text": text,
            "accent_1": accent_1,
            "accent_2": accent_2,
            "accent_3": accent_3,
            "overlay_style": "glass-blur",
            "temperature": temperature,
        }
    
    def _default_scheme(self, input_text: str = "") -> Dict:
        """无scene_context时 — 根据内容hash选择多样配色，避免千篇一律"""
        # 6套多样化配色方案，覆盖不同风格
        palettes = [
            {   # 深蓝科技
                "background": "#0a192f", "text": "#ccd6f6",
                "accent_1": "#64ffda", "accent_2": "#f07178", "accent_3": "#c3e88d",
                "overlay_style": "dark-solid", "temperature": "cool",
            },
            {   # 暖棕典雅
                "background": "#1a1209", "text": "#e8dcc8",
                "accent_1": "#f5a623", "accent_2": "#e74c3c", "accent_3": "#2ecc71",
                "overlay_style": "dark-solid", "temperature": "warm",
            },
            {   # 森林绿
                "background": "#0b1d0b", "text": "#d4edda",
                "accent_1": "#00e676", "accent_2": "#ff9800", "accent_3": "#29b6f6",
                "overlay_style": "dark-solid", "temperature": "neutral",
            },
            {   # 紫色梦幻
                "background": "#1a0a2e", "text": "#e8d5f5",
                "accent_1": "#bb86fc", "accent_2": "#03dac6", "accent_3": "#ff6e6e",
                "overlay_style": "dark-solid", "temperature": "cool",
            },
            {   # 深青蓝
                "background": "#001f2b", "text": "#b2dfdb",
                "accent_1": "#00bcd4", "accent_2": "#ff7043", "accent_3": "#c6ff00",
                "overlay_style": "dark-solid", "temperature": "cool",
            },
            {   # 石板灰
                "background": "#1e272e", "text": "#dfe6e9",
                "accent_1": "#e17055", "accent_2": "#00cec9", "accent_3": "#ffeaa7",
                "overlay_style": "dark-solid", "temperature": "neutral",
            },
        ]
        
        # 用内容hash选择配色，确保同一话题一致、不同话题不同
        idx = hash(input_text) % len(palettes) if input_text else 0
        chosen = palettes[idx]
        
        return {
            "mode": "default",
            "background": chosen["background"],
            "background_opacity": 0.90,
            "text": chosen["text"],
            "accent_1": chosen["accent_1"],
            "accent_2": chosen["accent_2"],
            "accent_3": chosen["accent_3"],
            "overlay_style": chosen["overlay_style"],
            "temperature": chosen["temperature"],
        }
