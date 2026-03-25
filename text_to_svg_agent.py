"""
Text-to-SVG Agent
=================

将文字增强和机制链增强统一生成成“纯文本可视化”SVG。
重点是排版、层次、节奏与轻动画，不做实体节点图、不做流程框图模板。
"""

import os
import re
import sys
from typing import Dict, Any
import json

CURRENT_DIR = os.path.dirname(__file__)
SVG_SIMPLE_DIR = os.path.join(CURRENT_DIR, "svg_simple")
if SVG_SIMPLE_DIR not in sys.path:
    sys.path.insert(0, SVG_SIMPLE_DIR)

from custom_chat_model import CustomChatModel  # type: ignore
from svg_validator import validate_and_fix  # type: ignore
from langchain_core.messages import HumanMessage, SystemMessage


CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class TextToSVGAgent:
    """专门负责将文字/机制链转成纯文本可视化 SVG。"""

    def __init__(self, llm_type: str):
        self.llm_type = llm_type
        self.llm = CustomChatModel(llm_type=llm_type, temperature=0.45)

    def generate_text_svg(
        self,
        transcript: str,
        scene_info: Dict[str, Any],
        layout_info: Dict[str, Any],
        mode: str = "text",
        payload: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        payload = payload or {}
        width = int(layout_info.get("width", CANVAS_WIDTH))
        height = int(layout_info.get("height", CANVAS_HEIGHT))
        copy_pack = self._prepare_copy(transcript, payload, mode)

        try:
            svg = self._compose_typographic_svg(
                scene_info=scene_info,
                width=width,
                height=height,
                mode=mode,
                payload=payload,
                copy_pack=copy_pack,
            )
            svg, validation = validate_and_fix(svg)
            return {
                "svg_content": svg,
                "validation": validation,
                "title": copy_pack.get("headline") or self._derive_title(transcript, payload, mode),
                "subtitle": copy_pack.get("support") or self._derive_subtitle(transcript, payload, mode),
            }
        except Exception as e:
            print(f"      TextToSVGAgent compose failed: {e}")
            fallback = self._fallback_svg(transcript, scene_info, width, height, mode, payload)
            fallback, validation = validate_and_fix(fallback)
            return {
                "svg_content": fallback,
                "validation": validation,
                "title": copy_pack.get("headline") or self._derive_title(transcript, payload, mode),
                "subtitle": copy_pack.get("support") or self._derive_subtitle(transcript, payload, mode),
            }

    def _build_system_prompt(
        self,
        mode: str,
        scene_info: Dict[str, Any],
        width: int,
        height: int,
    ) -> str:
        design = scene_info.get("design_guide", {})
        primary = design.get("recommended_accent", "#4f7cac")
        secondary = design.get("recommended_secondary", "#9fc2e4")
        text_color = design.get("recommended_text", "#f7fbff")
        bg_color = design.get("recommended_bg", "#122238")
        border_color = design.get("recommended_border", bg_color)
        bg_opacity = design.get("svg_bg_opacity", 0.86)
        bg_color = design.get("recommended_bg", "#122238")
        border_color = design.get("recommended_border", bg_color)
        bg_opacity = design.get("svg_bg_opacity", 0.86)

        role_line = (
            "Create a mechanism-oriented typographic SVG."
            if mode == "mechanism"
            else "Create a knowledge-note typographic SVG."
        )

        return f"""You are an expert SVG typographic designer for video overlays.
Canvas: {width}x{height}.
Output RAW SVG code only.

{role_line}

Hard requirements:
1. This SVG must stay text-first. The content inside the SVG should be coherent text blocks, not isolated words.
2. Do NOT turn the text into node graphs, flowchart boxes, entity diagrams, icon maps, fake dashboards, or scattered decorative labels.
3. Do NOT invent entities, categories, slogans, or condensed phrases that are not grounded in the transcript.
4. First summarize the transcript into one clear takeaway, then express it as a strong headline plus one or two complete supporting sentences.
5. The wording must be semantically complete and easy to understand at a glance. Avoid fragmentary subtitles like "PLAY -> UNDERSTAND" or mysterious one-word labels.
6. Typography must be LARGE and video-legible. Make the main headline dominant, the support line clearly readable, and avoid tiny annotation text.
7. The primary text should occupy a substantial part of the canvas. Prefer fewer text blocks with larger font sizes over many small lines.
8. Keep animation very restrained: gentle fade-in, underline reveal, or subtle emphasis only. No blinking dots, no floating particles, no unrelated ornaments.
9. If you draw an underline or divider, its length must align cleanly with the associated text block. Do not use broken or mismatched underline lengths.
10. Draw a visible background plate behind the typography. The background must not be transparent.
11. Draw a clearly visible border so the overlay edge is separated from the video.
12. For text/mechanism overlays, use a solid, non-transparent background and a visible border in the same color family.
13. Use this palette:
   - background: {bg_color} (opacity {bg_opacity})
   - border: {border_color}
   - primary accent: {primary}
   - secondary accent: {secondary}
   - text: {text_color}
14. Make the SVG elegant and legible. Favor 2-3 textual regions max.
15. Avoid poster-like category labels such as INSIGHT, NOTE, OBSERVATION unless they are absolutely necessary. Usually omit them.
16. Use short complete sentences and clear meaning instead of dense paragraphs.
17. Prefer a conclusion-and-explanation layout:
   - one dominant conclusion line
   - one supporting explanation sentence
   - optional one secondary line
18. For mechanism mode, use a clear title followed by 2-4 aligned textual stage rows. Do not create abstract slogans.

Avoid:
- generic box-and-arrow diagrams
- random isolated words
- cryptic slogans
- blinking decorative dots
- broken underline segments
- huge empty white panels
- massive decorative frames that detach the SVG from the video

Return raw SVG only, starting with <svg> and ending with </svg>."""

    def _build_prompt(
        self,
        transcript: str,
        scene_info: Dict[str, Any],
        layout_info: Dict[str, Any],
        mode: str,
        payload: Dict[str, Any],
        width: int,
        height: int,
        copy_pack: Dict[str, str],
    ) -> str:
        region_context = layout_info.get("region_context", {})
        style_hint = scene_info.get("design_guide", {}).get("svg_prompt", "")
        position = layout_info.get("position", "center")

        if mode == "mechanism":
            title_hint = payload.get("chain_title", "")
            stages = payload.get("stages", [])
            support = " | ".join(str(s) for s in stages[:4])
            mode_brief = (
                "Present the mechanism as a staged textual explanation. "
                "Use a clear title and then 2-4 aligned stage rows, each with complete wording. "
                "Keep it elegant and text-first. Use motion only for subtle reveal."
            )
        else:
            title_hint = ""
            support = ""
            mode_brief = (
                "Present the idea as a concise explanatory note. "
                "Favor one clear conclusion line, one readable explanation sentence, and at most one secondary sentence."
            )

        return f"""Transcript:
{transcript}

Prepared copy:
- headline: {copy_pack.get("headline", "")}
- support: {copy_pack.get("support", "")}
- secondary: {copy_pack.get("secondary", "")}

Optional title hint:
{title_hint}

Optional support content:
{support}

Layout constraints:
- preferred position: {position}
- target area: {width}x{height}
- region context: {region_context}

Scene/style hint:
{style_hint}

Task:
Create a polished SVG overlay that visualizes this content using text composition rather than diagrams.
{mode_brief}

Guidance:
- Keep the wording faithful to the transcript, but compress it into a clearer takeaway.
- Extract the central meaning first, instead of copying broken subtitle fragments.
- Use 2-3 textual regions max.
- Prefer 1 strong title + 1 complete supporting sentence + 1 optional secondary sentence. Use the prepared copy as the semantic source of truth.
- The title should feel bold and oversized on screen.
- Let text occupy more of the canvas; avoid leaving too much empty space around tiny typography.
- Use calm academic composition, not slogan-like poster language.
- Omit category tags like INSIGHT / NOTE unless absolutely necessary.
- Add only subtle animation: fade-in, underline reveal, or soft emphasis.
- Any underline must be aligned to the text width and should not appear broken or detached.
- Do not add unrelated dots or tiny decorative marks.
- Make it suitable as a video overlay, using the provided background and border colors instead of a transparent plate.

Return raw SVG only."""

    def _extract_svg(self, text: str) -> str:
        if "```svg" in text:
            start = text.find("```svg") + 6
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        start = text.find("<svg")
        end = text.rfind("</svg>")
        if start != -1 and end != -1:
            return text[start:end + 6].strip()
        return text.strip()

    def _compose_typographic_svg(
        self,
        scene_info: Dict[str, Any],
        width: int,
        height: int,
        mode: str,
        payload: Dict[str, Any],
        copy_pack: Dict[str, str],
    ) -> str:
        design = scene_info.get("design_guide", {})
        primary = design.get("recommended_accent", "#4f7cac")
        secondary = design.get("recommended_secondary", "#9fc2e4")
        text_color = design.get("recommended_text", "#f7fbff")
        bg_color = design.get("recommended_bg", "#122238")
        border_color = design.get("recommended_border", bg_color)

        title = copy_pack.get("headline", "")
        support = copy_pack.get("support", "")
        secondary_copy = copy_pack.get("secondary", "")
        stages = []
        if mode == "mechanism":
            stages = [str(s).strip() for s in (payload.get("stages") or []) if str(s).strip()][:3]

        compact = width < 560 or height < 320
        plate_x = 0
        plate_y = 0
        plate_w = width
        plate_h = height
        corner_radius = max(20, int(min(width, height) * 0.09))
        inset_x = max(8, int(width * 0.018))
        inset_y = max(8, int(height * 0.03))
        pad_x = max(28, int(plate_w * (0.10 if compact else 0.08)))
        pad_top = max(28, int(plate_h * (0.16 if compact else 0.14)))
        pad_bottom = max(24, int(plate_h * (0.14 if compact else 0.12)))

        x = plate_x + pad_x
        top = plate_y + pad_top
        title_max_width = max(160, plate_w - 2 * pad_x)
        support_max_width = title_max_width

        title_fs = max(22, min(64, int(width * (0.105 if compact else 0.070))))
        max_title_lines = 4 if compact else 3
        title_lines = self._wrap_text(title, title_max_width, title_fs, max_lines=max_title_lines)
        while (len(title_lines) > max_title_lines or self._estimate_block_height(title_fs, len(title_lines)) > int(plate_h * 0.40)) and title_fs > 20:
            title_fs -= 3
            title_lines = self._wrap_text(title, title_max_width, title_fs, max_lines=max_title_lines)

        support_fs = max(14, min(28, int(width * (0.048 if compact else 0.030))))
        support_lines = self._wrap_text(support, support_max_width, support_fs, max_lines=3)

        secondary_fs = max(12, min(20, int(width * (0.038 if compact else 0.022))))
        secondary_lines = self._wrap_text(secondary_copy, support_max_width, secondary_fs, max_lines=2) if secondary_copy else []

        stage_fs = max(16, min(24, int(width * 0.040)))
        title_w = min(title_max_width, int(max(len(line) for line in title_lines or [title]) * max(16, title_fs * 0.52)))
        title_line_h = int(title_fs * 1.07)
        support_line_h = int(support_fs * 1.34)
        secondary_line_h = int(secondary_fs * 1.30)
        title_gap = max(20, int(height * 0.055))
        line_gap = max(18, int(height * 0.05))
        support_gap = max(16, int(height * 0.04))

        def _fit_text_mode():
            nonlocal title_fs, support_fs, secondary_fs, title_lines, support_lines, secondary_lines
            available = plate_h - pad_top - pad_bottom
            while title_fs > 18:
                title_lines = self._wrap_text(title, title_max_width, title_fs, max_lines=max_title_lines)
                support_lines = self._wrap_text(support, support_max_width, support_fs, max_lines=3) if support else []
                secondary_lines = self._wrap_text(secondary_copy, support_max_width, secondary_fs, max_lines=2) if secondary_copy else []
                total = (
                    len(title_lines) * int(title_fs * 1.04) +
                    title_gap +
                    len(support_lines) * int(support_fs * 1.20) +
                    (support_gap if secondary_lines else 0) +
                    len(secondary_lines) * int(secondary_fs * 1.20)
                )
                if total <= available:
                    break
                title_fs -= 3
                support_fs = max(14, support_fs - 2)
                secondary_fs = max(12, secondary_fs - 2)
            if title_fs <= 18 and secondary_lines:
                secondary_lines = []

        def _fit_mechanism_mode():
            nonlocal title_fs, stage_fs, title_lines
            available = plate_h - pad_top - pad_bottom
            row_h = max(40, int(plate_h * 0.17))
            while title_fs > 18:
                title_lines = self._wrap_text(title, title_max_width, title_fs, max_lines=max_title_lines)
                total = len(title_lines) * int(title_fs * 1.04) + title_gap + len(stages) * row_h + (support_gap if secondary_copy or support else 0) + 2 * int(secondary_fs * 1.20)
                if total <= available:
                    return row_h
                title_fs -= 3
                stage_fs = max(15, stage_fs - 1)
                row_h = max(42, row_h - 6)
            return row_h

        if mode == "mechanism" and stages:
            row_h = _fit_mechanism_mode()
            title_line_h = int(title_fs * 1.04)
            title_block_height = title_line_h * max(1, len(title_lines))
            divider_y = top + title_block_height + title_gap
            stage_y = divider_y + line_gap + 12
            stage_items = []
            for i, stage in enumerate(stages):
                row_y = stage_y + i * row_h
                stage_text_y = row_y + 8
                stage_items.append(
                    f'<g class="fade-in" style="animation-delay:{0.18 * i:.2f}s">'
                    f'<rect x="{x}" y="{row_y - 28}" width="{width - 2*x}" height="{max(44, row_h - 6)}" rx="16" fill="none" stroke="{border_color}" stroke-opacity="0.62" stroke-width="2.2"/>'
                    f'<circle cx="{x + 24}" cy="{row_y - 2}" r="8" fill="{primary}" opacity="0.95"/>'
                    f'<text x="{x + 44}" y="{stage_text_y}" font-size="{stage_fs}" font-weight="620" fill="{text_color}" class="body-text">{self._escape_xml(self._clean_copy(stage, 74))}</text>'
                    f'</g>'
                )
            support_block = "".join(stage_items)
            secondary_block = (
                self._build_multiline_text(
                    x,
                    stage_y + len(stages) * row_h + support_gap,
                    secondary_fs,
                    secondary_line_h,
                    secondary_lines or self._wrap_text(secondary_copy or support, support_max_width, secondary_fs, max_lines=2),
                    secondary,
                    '500',
                    extra='opacity="0.92" class="fade-in body-text" style="animation-delay:0.55s"'
                )
                if (secondary_copy or support)
                else ""
            )
        else:
            _fit_text_mode()
            title_line_h = int(title_fs * 1.04)
            support_line_h = int(support_fs * 1.22)
            secondary_line_h = int(secondary_fs * 1.22)
            title_w = min(title_max_width, int(max(len(line) for line in title_lines or [title]) * max(16, title_fs * 0.52)))
            title_block_height = title_line_h * max(1, len(title_lines))
            divider_y = top + title_block_height + title_gap
            support_y = divider_y + line_gap + 2
            support_block = self._build_multiline_text(
                x,
                support_y,
                support_fs,
                support_line_h,
                support_lines,
                text_color,
                '600',
                extra='opacity="0.96" class="fade-in body-text" style="animation-delay:0.18s"'
            ) if support_lines else ""
            secondary_y = support_y + support_line_h * max(1, len(support_lines)) + support_gap
            secondary_block = self._build_multiline_text(
                x,
                secondary_y,
                secondary_fs,
                secondary_line_h,
                secondary_lines,
                secondary,
                '500',
                extra='opacity="0.92" class="fade-in body-text secondary-text" style="animation-delay:0.32s"'
            ) if secondary_lines else ""

        divider_w = max(72, min(title_max_width, int(title_w * 0.72)))

        return f"""<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
      @keyframes drawLine {{ from {{ stroke-dashoffset: {divider_w}; }} to {{ stroke-dashoffset: 0; }} }}
      .fade-in {{ opacity: 0; animation: fadeIn 0.6s ease-out forwards; }}
      .sweep-line {{ stroke-dasharray: {divider_w}; stroke-dashoffset: {divider_w}; animation: drawLine 0.75s ease-out forwards 0.15s; }}
      .title-text {{ font-family: Georgia, 'Times New Roman', serif; letter-spacing: -0.01em; }}
      .body-text {{ font-family: 'Trebuchet MS', 'Helvetica Neue', Arial, sans-serif; letter-spacing: 0.005em; }}
      .secondary-text {{ letter-spacing: 0.01em; }}
    </style>
  </defs>
  <g>
    <rect x="{plate_x}" y="{plate_y}" width="{plate_w}" height="{plate_h}" rx="{corner_radius}" fill="{bg_color}" fill-opacity="1" stroke="{border_color}" stroke-width="6" />
    <rect x="{inset_x}" y="{inset_y}" width="{max(0, width - inset_x * 2)}" height="{max(0, height - inset_y * 2)}" rx="{max(14, corner_radius - 10)}" fill="none" stroke="{primary}" stroke-opacity="0.22" stroke-width="1.6" />
    {self._build_multiline_text(x, top + 24, title_fs, title_line_h, title_lines, text_color, '800', extra='class="fade-in title-text"')}
    <line x1="{x}" y1="{divider_y}" x2="{x + divider_w}" y2="{divider_y}" stroke="{primary}" stroke-width="2.6" stroke-linecap="round" class="sweep-line" />
    {support_block}
    {secondary_block}
  </g>
</svg>"""

    def _wrap_text(self, text: str, max_width: int, font_size: int, max_lines: int = 2) -> list[str]:
        text = str(text or "").strip()
        if not text:
            return []
        words = text.split()
        if not words:
            return [text]
        lines: list[str] = []
        current = words[0]
        char_px = max(10.0, font_size * 0.56)
        capacity = max(8, int(max_width / char_px))
        for word in words[1:]:
            candidate = f"{current} {word}"
            if len(candidate) <= capacity:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) == max_lines - 1:
                    break
        remainder_words = words[len(" ".join(lines + [current]).split()):]
        if remainder_words:
            tail = f"{current} {' '.join(remainder_words)}".strip()
            current = tail
        lines.append(current)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        if len(lines) == max_lines and len(" ".join(lines).split()) < len(words):
            last = lines[-1]
            lines[-1] = (last[: max(0, capacity - 3)].rstrip() + "...") if len(last) > capacity - 3 else last
        return lines

    def _build_multiline_text(
        self,
        x: int,
        start_y: int,
        font_size: int,
        line_height: int,
        lines: list[str],
        color: str,
        weight: str,
        extra: str = "",
    ) -> str:
        if not lines:
            return ""
        parts = [f'<text x="{x}" y="{start_y}" font-size="{font_size}" font-weight="{weight}" fill="{color}" {extra}>']
        for idx, line in enumerate(lines):
            dy = 0 if idx == 0 else line_height
            parts.append(f'<tspan x="{x}" dy="{dy}">{self._escape_xml(line)}</tspan>')
        parts.append('</text>')
        return "".join(parts)

    def _prepare_copy(self, transcript: str, payload: Dict[str, Any], mode: str) -> Dict[str, str]:
        fallback = self._fallback_copy(transcript, payload, mode)
        try:
            if mode == "mechanism":
                extra = f"Mechanism title hint: {payload.get('chain_title', '')}\nStages: {payload.get('stages', [])}"
            else:
                extra = ''
            prompt = f"""Extract a clean semantic summary for a video overlay.
Return JSON only with keys headline, support, secondary.
Requirements:
- headline: one clear takeaway, 3-10 words, complete and understandable
- support: one complete explanation sentence, <= 18 words
- secondary: optional second complete sentence, <= 14 words
- keep the meaning faithful to the transcript
- do not invent entities, slogans, taglines, or cryptic labels
- avoid fragments like 'PLAY -> UNDERSTAND'
- avoid category words like INSIGHT, NOTE, OBSERVATION
- prefer conclusion-plus-explanation wording over decorative poster wording

Transcript:
{transcript}

{extra}
"""
            result = self.llm._generate([SystemMessage(content='Return JSON only.'), HumanMessage(content=prompt)])
            raw = result.generations[0].message.content
            data = self.llm.parse_json_response(raw)
            if isinstance(data, dict):
                headline = str(data.get('headline', '')).strip()
                support = str(data.get('support', '')).strip()
                secondary = str(data.get('secondary', '')).strip()
                if headline and support:
                    return {
                        'headline': self._clean_copy(headline, 64),
                        'support': self._clean_copy(support, 120),
                        'secondary': self._clean_copy(secondary, 100),
                    }
        except Exception as e:
            print(f'      TextToSVGAgent copy extraction failed: {e}')
        return fallback

    def _fallback_copy(self, transcript: str, payload: Dict[str, Any], mode: str) -> Dict[str, str]:
        if mode == 'mechanism':
            headline = str(payload.get('chain_title') or self._derive_title(transcript, payload, mode)).strip()
            stages = [str(s).strip() for s in (payload.get('stages') or []) if str(s).strip()]
            support = self._clean_copy(stages[0], 120) if stages else self._derive_subtitle(transcript, payload, mode)
            secondary = ''
            return {'headline': self._clean_copy(headline, 64), 'support': self._clean_copy(support, 120), 'secondary': secondary}
        headline = self._derive_title(transcript, payload, mode)
        support = self._derive_subtitle(transcript, payload, mode)
        secondary = ''
        return {'headline': self._clean_copy(headline, 64), 'support': self._clean_copy(support, 120), 'secondary': secondary}

    def _clean_copy(self, text: str, limit: int) -> str:
        text = re.sub(r'\s+', ' ', str(text)).strip()
        text = re.sub(r'^[\-–—:;,.\s]+', '', text)
        text = re.sub(r'[\-–—:;,.\s]+$', '', text)
        if len(text) <= limit:
            return text
        cut = text[:limit].rsplit(' ', 1)[0].strip()
        return (cut or text[:limit]).strip()

    def _derive_title(self, transcript: str, payload: Dict[str, Any], mode: str) -> str:
        if mode == "mechanism" and payload.get("chain_title"):
            return str(payload["chain_title"]).strip()
        text = re.sub(r"\s+", " ", transcript).strip()
        if len(text) <= 64:
            return text
        cut = text[:64].rsplit(" ", 1)[0].strip()
        return (cut or text[:64]).strip()

    def _derive_subtitle(self, transcript: str, payload: Dict[str, Any], mode: str) -> str:
        if mode == "mechanism":
            stages = payload.get("stages", [])
            if stages:
                stage = str(stages[0]).strip()
                if stage:
                    return self._clean_copy(stage, 120)
        text = re.sub(r"\s+", " ", transcript).strip()
        if len(text) <= 110:
            return text
        cut = text[:110].rsplit(" ", 1)[0].strip()
        return (cut or text[:110]).strip()

    def _estimate_block_height(self, font_size: int, line_count: int) -> int:
        return int(font_size * 1.08 * max(1, line_count))

    def _fallback_svg(
        self,
        transcript: str,
        scene_info: Dict[str, Any],
        width: int,
        height: int,
        mode: str,
        payload: Dict[str, Any],
    ) -> str:
        design = scene_info.get("design_guide", {})
        primary = design.get("recommended_accent", "#4f7cac")
        secondary = design.get("recommended_secondary", "#9fc2e4")
        text_color = design.get("recommended_text", "#f7fbff")
        bg_color = design.get("recommended_bg", "#122238")
        border_color = design.get("recommended_border", bg_color)
        bg_opacity = design.get("svg_bg_opacity", 0.86)
        bg_color = design.get("recommended_bg", "#122238")
        border_color = design.get("recommended_border", bg_color)
        bg_opacity = design.get("svg_bg_opacity", 0.86)
        copy_pack = self._fallback_copy(transcript, payload, mode)
        title = copy_pack.get("headline") or self._derive_title(transcript, payload, mode)
        subtitle = copy_pack.get("support") or self._derive_subtitle(transcript, payload, mode)

        inset = max(12, int(min(width, height) * 0.035))
        pad_x = max(56, int(width * 0.09))
        title_w = max(180, min(width - 2 * pad_x, int(len(title) * max(22, width // 36))))
        subtitle_fs = max(24, min(46, width // 24))
        title_fs = max(44, min(98, width // 16))
        title_y = max(110, int(height * 0.34))
        divider_y = title_y + max(22, int(title_fs * 0.28))
        subtitle_y = divider_y + max(44, int(height * 0.16))
        return f"""<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .fade-in {{ opacity: 0; animation: fadeIn 0.7s ease-out forwards; }}
      .sweep-line {{ stroke-dasharray: {title_w}; stroke-dashoffset: {title_w}; animation: drawLine 0.9s ease-out forwards 0.25s; }}
      @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
      @keyframes drawLine {{ from {{ stroke-dashoffset: {title_w}; }} to {{ stroke-dashoffset: 0; }} }}
      .title-text {{ font-family: Georgia, 'Times New Roman', serif; letter-spacing: -0.01em; }}
      .body-text {{ font-family: 'Trebuchet MS', 'Helvetica Neue', Arial, sans-serif; }}
    </style>
  </defs>
  <g>
    <rect x="0" y="0" width="{width}" height="{height}" rx="{max(20, int(min(width, height) * 0.09))}" fill="{bg_color}" fill-opacity="1" stroke="{border_color}" stroke-width="6" />
    <rect x="{inset}" y="{inset}" width="{max(0, width - inset * 2)}" height="{max(0, height - inset * 2)}" rx="{max(14, int(min(width, height) * 0.07))}" fill="none" stroke="{primary}" stroke-opacity="0.22" stroke-width="1.6" />
    <text x="{pad_x}" y="{title_y}" font-size="{title_fs}" font-weight="800" fill="{text_color}" class="fade-in title-text">{self._escape_xml(title)}</text>
    <line x1="{pad_x}" y1="{divider_y}" x2="{pad_x + int(title_w * 0.72)}" y2="{divider_y}" stroke="{primary}" stroke-width="2.8" stroke-linecap="round" class="sweep-line" />
    <text x="{pad_x}" y="{subtitle_y}" font-size="{subtitle_fs}" font-weight="600" fill="{text_color}" opacity="0.94" class="fade-in body-text">{self._escape_xml(subtitle)}</text>
  </g>
</svg>"""

    def _escape_xml(self, text: str) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
