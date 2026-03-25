"""
Overlay Style Agent
===================

Per-overlay background / border / text color planning.
Each point is evaluated independently using local region colors and scene design hints.
"""

import json
import os
import sys
from typing import Any, Dict

CURRENT_DIR = os.path.dirname(__file__)
SVG_SIMPLE_DIR = os.path.join(CURRENT_DIR, "svg_simple")
if SVG_SIMPLE_DIR not in sys.path:
    sys.path.insert(0, SVG_SIMPLE_DIR)

from custom_chat_model import CustomChatModel  # type: ignore
from langchain_core.messages import HumanMessage, SystemMessage


class OverlayStyleAgent:
    def __init__(self, llm_type: str):
        self.llm_type = llm_type
        self.llm = CustomChatModel(llm_type=llm_type, temperature=0.25)

    def plan_style(
        self,
        transcript: str,
        scene_info: Dict[str, Any],
        layout_info: Dict[str, Any],
        content_kind: str,
    ) -> Dict[str, Any]:
        region = layout_info.get("region_context", {}) or {}
        design = scene_info.get("design_guide", {}) or {}
        color_hierarchy = scene_info.get("color_hierarchy", {}) or {}
        color_metrics = scene_info.get("color_metrics", {}) or {}

        try:
            messages = [
                SystemMessage(content=self._system_prompt(content_kind)),
                HumanMessage(
                    content=self._user_prompt(
                        transcript=transcript,
                        design=design,
                        region=region,
                        color_hierarchy=color_hierarchy,
                        color_metrics=color_metrics,
                        content_kind=content_kind,
                    )
                ),
            ]
            response = self.llm.invoke(messages)
            text = response.content.strip().replace("```json", "").replace("```", "").strip()
            style = json.loads(text)
            return self._normalize(style, region, design, content_kind)
        except Exception as e:
            print(f"      OverlayStyleAgent failed: {e}, using fallback")
            return self._fallback(region, design, color_hierarchy, content_kind)

    def _system_prompt(self, content_kind: str) -> str:
        lock_rule = (
            "For text/mechanism typographic SVG, background and border MUST stay in the same color family, but the border still needs visible separation from the background and the video."
            if content_kind in ("t2svg_text", "t2svg_mechanism")
            else "For diagram/image SVG, background and border should be coordinated but not identical unless truly necessary."
        )
        return f"""You are a scholarly motion-graphics color director.
Return JSON only.

Choose a background color, border color, accent colors, and text color for ONE overlay.
The palette must be decided for this specific overlay position, using the local video region colors.
Use professional color principles: analogous harmony, complementary contrast, split-complementary balance, value contrast, local edge separation, and warm/cool temperature control.
You must explicitly decide which strategy best fits this overlay:
- analogous harmony
- complementary contrast
- split-complementary balance
- neutral depth + accent contrast
- warm/cool temperature rebalance

Do not choose colors arbitrarily. Base the decision on:
- local background color
- local brightness
- local edge density
- scene color hierarchy
- scene color temperature
- whether the overlay is text-first or diagram-first

{lock_rule}

JSON schema:
{{
  "scheme": "analogous | complementary | split_complementary | neutral_contrast | temperature_rebalance",
  "background": "#RRGGBB",
  "border": "#RRGGBB",
  "primary_accent": "#RRGGBB",
  "secondary_accent": "#RRGGBB",
  "text": "#RRGGBB",
  "bg_opacity": 1.0,
  "temperature_strategy": "short phrase",
  "rationale": "short reason"
}}
"""

    def _user_prompt(
        self,
        transcript: str,
        design: Dict[str, Any],
        region: Dict[str, Any],
        color_hierarchy: Dict[str, Any],
        color_metrics: Dict[str, Any],
        content_kind: str,
    ) -> str:
        return f"""Overlay content type: {content_kind}
Transcript/topic: {transcript}

Local overlay region:
- region_bg_color: {region.get('region_bg_color')}
- region_brightness: {region.get('region_brightness')}
- region_brightness_value: {region.get('region_brightness_value')}
- region_type: {region.get('region_type')}
- region_colors: {region.get('region_colors')}
- region_edge_density: {region.get('region_edge_density')}
- suggested base opacity: {region.get('recommended_svg_opacity')}

Scene palette:
- background: {color_hierarchy.get('background_color')}
- accent: {color_hierarchy.get('accent_color')}
- text: {color_hierarchy.get('text_color')}
- all_colors: {color_hierarchy.get('all_colors')}
- temperature: {color_metrics.get('temperature')}
- brightness_level: {color_metrics.get('brightness_level')}
- saturation_level: {color_metrics.get('saturation_level')}

Existing design guide:
- recommended_bg: {design.get('recommended_bg')}
- recommended_accent: {design.get('recommended_accent')}
- recommended_secondary: {design.get('recommended_secondary')}
- recommended_text: {design.get('recommended_text')}

Requirements:
- The overlay must be visually separated from the video by a visible border.
- The overlay background must not be transparent.
- First decide whether analogous harmony, complementary contrast, split-complementary balance, neutral contrast, or warm/cool rebalancing is best.
- Use colors that harmonize with the local region, but remain readable.
- If the local region is dark, consider deep cool plates or warm contrast accents only when they improve readability.
- If the local region is bright, consider softly tinted light backgrounds or slightly cooler contrasting plates with clear border separation.
- Border color must remain readable against both the overlay background and the underlying video region.
- Text color must strongly separate from the chosen background.
- Keep the style scholarly and elegant, not neon gimmick.
- Return only JSON.
"""

    def _normalize(self, style: Dict[str, Any], region: Dict[str, Any], design: Dict[str, Any], content_kind: str) -> Dict[str, Any]:
        fallback = self._fallback(region, design, {}, content_kind)
        out = {
            "scheme": style.get("scheme", ""),
            "background": style.get("background") or fallback["background"],
            "border": style.get("border") or fallback["border"],
            "primary_accent": style.get("primary_accent") or fallback["primary_accent"],
            "secondary_accent": style.get("secondary_accent") or fallback["secondary_accent"],
            "text": style.get("text") or fallback["text"],
            "bg_opacity": style.get("bg_opacity", fallback["bg_opacity"]),
            "temperature_strategy": style.get("temperature_strategy", ""),
            "rationale": style.get("rationale", ""),
        }
        out["bg_opacity"] = 1.0
        if content_kind in ("t2svg_text", "t2svg_mechanism"):
            out["border"] = self._ensure_visible_border(
                out["background"],
                out["border"],
                region.get("region_brightness", "dark"),
            )
        return out

    def _fallback(self, region: Dict[str, Any], design: Dict[str, Any], color_hierarchy: Dict[str, Any], content_kind: str) -> Dict[str, Any]:
        bg = region.get("region_bg_color") or design.get("recommended_bg") or color_hierarchy.get("background_color") or "#122238"
        accent = design.get("recommended_accent") or color_hierarchy.get("accent_color") or "#7aa7d8"
        secondary = design.get("recommended_secondary") or accent
        bright = str(region.get("region_brightness", "dark"))
        if bright == "bright":
            background = "#eef5fc"
            border = "#c4d8ee"
            text = "#18324d"
            opacity = 1.0
        elif bright == "medium":
            background = bg if bg.startswith("#") else "#1f334a"
            border = accent
            text = design.get("recommended_text", "#f6fbff")
            opacity = 1.0
        else:
            background = bg if bg.startswith("#") else "#132132"
            border = accent
            text = design.get("recommended_text", "#f8fbff")
            opacity = 1.0
        if content_kind in ("t2svg_text", "t2svg_mechanism"):
            border = self._ensure_visible_border(background, border, bright)
        return {
            "background": background,
            "border": border,
            "primary_accent": accent,
            "secondary_accent": secondary,
            "text": text,
            "bg_opacity": opacity,
            "rationale": "fallback",
        }

    def _ensure_visible_border(self, background: str, border: str, brightness: Any) -> str:
        bg = self._normalize_hex(background, "#122238")
        bd = self._normalize_hex(border, bg)
        if bg.lower() != bd.lower():
            return bd
        delta = 42 if str(brightness).lower() == "bright" else 58
        return self._shift_hex(bg, -delta if str(brightness).lower() == "bright" else delta)

    def _normalize_hex(self, value: Any, fallback: str) -> str:
        raw = str(value or "").strip()
        if len(raw) == 7 and raw.startswith("#"):
            return raw
        return fallback

    def _shift_hex(self, color: str, delta: int) -> str:
        raw = color.lstrip("#")
        try:
            channels = [int(raw[i:i + 2], 16) for i in (0, 2, 4)]
            shifted = [max(0, min(255, c + delta)) for c in channels]
            return "#{:02x}{:02x}{:02x}".format(*shifted)
        except Exception:
            return color
