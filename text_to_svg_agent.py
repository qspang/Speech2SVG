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
        target_width = int(layout_info.get("width", CANVAS_WIDTH))
        target_height = int(layout_info.get("height", CANVAS_HEIGHT))
        width, height = self._resolve_render_canvas(target_width, target_height)
        copy_pack = self._prepare_copy(transcript, payload, mode)
        title = copy_pack.get("headline") or self._derive_title(transcript, payload, mode)
        subtitle = copy_pack.get("support") or self._derive_subtitle(transcript, payload, mode)

        try:
            system_prompt = self._build_system_prompt(mode, scene_info, width, height)
            user_prompt = self._build_prompt(
                transcript=transcript,
                scene_info=scene_info,
                layout_info=layout_info,
                mode=mode,
                payload=payload,
                width=width,
                height=height,
                target_width=target_width,
                target_height=target_height,
                copy_pack=copy_pack,
            )
            result = self.llm._generate(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            raw = result.generations[0].message.content
            svg = self._extract_svg(raw)
            if "<svg" not in svg or "</svg>" not in svg:
                raise ValueError("LLM did not return valid SVG markup")
            svg, validation = validate_and_fix(svg)
            return {
                "svg_content": svg,
                "validation": validation,
                "title": title,
                "subtitle": subtitle,
            }
        except Exception as e:
            print(f"      TextToSVGAgent llm layout failed: {e}")
            fallback = self._fallback_svg(transcript, scene_info, width, height, mode, payload)
            fallback, validation = validate_and_fix(fallback)
            return {
                "svg_content": fallback,
                "validation": validation,
                "title": title,
                "subtitle": subtitle,
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
        bg_color = design.get("recommended_bg", "none")
        border_color = design.get("recommended_border", "none")
        bg_opacity = design.get("svg_bg_opacity", 0.0)
        bg_color = design.get("recommended_bg", "none")
        border_color = design.get("recommended_border", "none")
        bg_opacity = design.get("svg_bg_opacity", 0.0)

        role_line = (
            "Create a mechanism-oriented typographic SVG."
            if mode == "mechanism"
            else "Create a knowledge-note typographic SVG."
        )

        min_title = max(34, min(92, int(width * 0.064)))
        min_support = max(28, min(52, int(width * 0.038)))
        min_secondary = max(24, min(44, int(width * 0.032)))

        return f"""You are an expert SVG typographic designer for video overlays.
Canvas: {width}x{height}.
Output RAW SVG code only.

{role_line}

Hard requirements:
1. This SVG must stay text-first. The content inside the SVG should be coherent text blocks, not isolated words.
2. Do NOT turn the text into node graphs, flowchart boxes, entity diagrams, icon maps, fake dashboards, or scattered decorative labels.
3. Do NOT invent entities, categories, slogans, or condensed phrases that are not grounded in the transcript.
4. First summarize the transcript into one clear takeaway, then express it as a strong headline plus exactly one complete supporting sentence for normal text mode.
5. The wording must be semantically complete and easy to understand at a glance. Avoid fragmentary subtitles like "PLAY -> UNDERSTAND" or mysterious one-word labels.
6. Typography must be LARGE and video-legible. Decide the font sizes first, then design the composition around them.
7. Minimum font sizes:
   - headline: at least {min_title}px
   - support: at least {min_support}px
   - secondary: at least {min_secondary}px if used
8. The primary text should occupy a substantial part of the canvas. Prefer fewer text blocks with larger font sizes over many small lines.
9. Use the available width intentionally. Do not compress all text into a narrow left column when the right side has space.
10. Balance the whitespace above, below, left, and right. Avoid huge empty right margins or a subtitle stuck to the bottom border.
8. Keep animation very restrained: gentle fade-in, underline reveal, or subtle emphasis only. No blinking dots, no floating particles, no unrelated ornaments.
9. If you draw an underline or divider, its length must align cleanly with the associated text block. Do not use broken or mismatched underline lengths.
10. The overall panel background must stay transparent so the video remains visible.
11. Choose text and accent colors that remain clearly readable on the local video region.
12. Do not make the text, underline, or any key decorative mark blend into the underlying local region. If uncertain, prefer white or near-white text.
13. Use this palette:
   - background: transparent
   - border: none unless absolutely necessary
   - primary accent: {primary}
   - secondary accent: {secondary}
   - text: {text_color}
14. Make the SVG elegant and legible. For normal text mode, use exactly 1 or 2 text regions only. Never create 3 separate text regions.
15. Avoid poster-like category labels such as INSIGHT, NOTE, OBSERVATION unless they are absolutely necessary. Usually omit them.
16. Use short complete sentences and clear meaning instead of dense paragraphs.
17. Prefer a conclusion-and-explanation layout:
   - one dominant conclusion line
   - one supporting explanation sentence
   - no third paragraph unless absolutely unavoidable
18. For mechanism mode, use a clear title followed by 2-4 aligned textual stage rows. Do not create abstract slogans.
19. If you use color emphasis, highlight only one short key phrase (usually 1-3 words) with the provided accent color. Keep the rest of the text in the main text color.
20. For normal text mode, never create split columns, left/right mini paragraphs, footer notes, side notes, or a third bottom text band.

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
        target_width: int,
        target_height: int,
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
                "Use one headline and one supporting sentence only. No third text block, no split columns, and no footer note."
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
- target area on video: {target_width}x{target_height}
- generate on an enlarged internal canvas: {width}x{height}
- region context: {region_context}

Scene/style hint:
{style_hint}

Task:
Create a polished SVG overlay that visualizes this content using text composition rather than diagrams.
{mode_brief}

Guidance:
- Highest priority: every prepared text block must be fully visible inside the SVG. No truncation, no clipping, no text outside the canvas, and no hidden last words.
- Use the prepared copy completely. Do not omit the end of the headline or silently drop words from support/secondary.
- Keep the wording faithful to the transcript, but compress it into a clearer takeaway.
- Extract the central meaning first, instead of copying broken subtitle fragments.
- Prefer 1 text block or 2 text blocks max.
- Prefer exactly 1 strong title + 1 complete supporting sentence for normal text mode. Do not add a third paragraph.
- The title should feel bold and oversized on screen.
- Before placing elements, decide workable font sizes for headline/support/secondary and keep them large enough for video playback.
- If two font sizes are used, keep them relatively close. The smaller text should still feel large on screen, not tiny caption text.
- If the title is long, reduce the font size moderately and add lines rather than clipping the text.
- Keep safe inner margins on all four sides so thick glyphs are not cut off by the viewBox boundary.
- Let text occupy more of the canvas; avoid leaving too much empty space around tiny typography.
- Use the full composition width when appropriate. If a line can safely be longer, do not force it into a narrow column.
- Make the text block proportions feel balanced inside the given canvas, with no giant empty right side and no text pressed against the bottom border.
- Use calm academic composition, not slogan-like poster language.
- Omit category tags like INSIGHT / NOTE unless absolutely necessary.
- Add only subtle animation: fade-in, underline reveal, or soft emphasis.
- Any underline must be aligned to the text width and should not appear broken or detached.
- Do not add unrelated dots or tiny decorative marks.
- Make it suitable as a video overlay with a transparent background. Use the provided text and accent colors so the typography stays visible over the local video region.
- Use the accent color sparingly on one short emphasis phrase when it strengthens the meaning, instead of making every word white.
- Never place two small paragraphs side by side at the bottom. Do not create bottom-left and bottom-right text groups.
- Never add footer notes, micro annotations, or a third explanatory line in normal text mode.

Return raw SVG only."""

    def _resolve_render_canvas(self, target_width: int, target_height: int) -> tuple[int, int]:
        target_width = max(320, int(target_width))
        target_height = max(180, int(target_height))
        scale = max(1.0, 1400.0 / target_width, 800.0 / target_height)
        render_width = int(round(target_width * scale))
        render_height = int(round(target_height * scale))
        return render_width, render_height

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
        bg_color = design.get("recommended_bg", "none")
        border_color = design.get("recommended_border", "none")

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
        pad_x = max(20, int(plate_w * (0.072 if compact else 0.062)))
        pad_top_min = max(20, int(plate_h * (0.09 if compact else 0.08)))
        pad_bottom_min = max(22, int(plate_h * (0.10 if compact else 0.09)))

        x = plate_x + pad_x
        top = plate_y + pad_top_min
        title_max_width = max(160, plate_w - 2 * pad_x)
        support_max_width = title_max_width

        title_fs = max(20, min(58, int(width * (0.095 if compact else 0.064))))
        max_title_lines = 4
        title_lines = self._wrap_text(title, title_max_width, title_fs, max_lines=max_title_lines)
        while (len(title_lines) > max_title_lines or self._estimate_block_height(title_fs, len(title_lines)) > int(plate_h * 0.40)) and title_fs > 20:
            title_fs -= 3
            title_lines = self._wrap_text(title, title_max_width, title_fs, max_lines=max_title_lines)

        support_fs = max(13, min(24, int(width * (0.043 if compact else 0.028))))
        support_lines = self._wrap_text(support, support_max_width, support_fs, max_lines=4)

        secondary_fs = max(11, min(18, int(width * (0.034 if compact else 0.020))))
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
            available = plate_h - pad_top_min - pad_bottom_min
            while title_fs > 16:
                title_lines = self._wrap_text(title, title_max_width, title_fs, max_lines=max_title_lines)
                support_lines = self._wrap_text(support, support_max_width, support_fs, max_lines=4) if support else []
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
                title_fs -= 2
                support_fs = max(12, support_fs - 1)
                secondary_fs = max(10, secondary_fs - 1)
            if title_fs <= 16 and secondary_lines:
                secondary_lines = []

        def _fit_mechanism_mode():
            nonlocal title_fs, stage_fs, title_lines
            available = plate_h - pad_top_min - pad_bottom_min
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
            text_block_total = (
                title_line_h * max(1, len(title_lines)) +
                title_gap +
                (line_gap + 2 if support_lines else 0) +
                support_line_h * max(1, len(support_lines)) +
                (support_gap if secondary_lines else 0) +
                secondary_line_h * max(1, len(secondary_lines))
            )
            available_top = max(
                pad_top_min,
                min(
                    plate_h - pad_bottom_min - text_block_total,
                    int((plate_h - text_block_total) * 0.42)
                )
            )
            top = available_top
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

        divider_w = max(72, min(title_max_width, int(title_w * 0.68)))

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
        char_px = max(8.5, font_size * 0.525)
        line_limit_px = max_width

        from functools import lru_cache

        def line_width(candidate_words: list[str]) -> float:
            candidate = " ".join(candidate_words)
            return max(1.0, len(candidate) * char_px)

        @lru_cache(maxsize=None)
        def solve(index: int, lines_left: int):
            if index >= len(words):
                return 0.0, []
            if lines_left <= 1:
                tail_words = list(words[index:])
                tail = " ".join(tail_words)
                width_px = line_width(tail_words)
                overflow = max(0.0, width_px - line_limit_px)
                fill_ratio = min(1.25, width_px / max(1.0, line_limit_px))
                penalty = overflow * 1000.0 + abs(0.92 - fill_ratio) * 120.0
                return penalty, [tail]

            best_score = float("inf")
            best_lines: list[str] = []
            current_words: list[str] = []

            for end in range(index, len(words)):
                current_words.append(words[end])
                width_px = line_width(current_words)
                overflow = max(0.0, width_px - line_limit_px)
                if overflow > char_px * 2.5:
                    break
                fill_ratio = min(1.25, width_px / max(1.0, line_limit_px))
                short_penalty = abs(0.90 - fill_ratio) * 85.0
                if fill_ratio < 0.58:
                    short_penalty += (0.58 - fill_ratio) * 170.0
                if end == index:
                    short_penalty += 14.0

                next_score, next_lines = solve(end + 1, lines_left - 1)
                score = short_penalty + overflow * 1000.0 + next_score
                if score < best_score:
                    best_score = score
                    best_lines = [" ".join(current_words)] + next_lines

            return best_score, best_lines

        _, lines = solve(0, max_lines)
        lines = [line.strip() for line in lines if line.strip()]
        if not lines:
            return [text]
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        total_words_in_lines = len(" ".join(lines).split())
        if len(lines) == max_lines and total_words_in_lines < len(words):
            remainder = words[total_words_in_lines:]
            if remainder:
                merged = f"{lines[-1]} {' '.join(remainder)}".strip()
                max_chars = max(8, int(line_limit_px / max(1.0, char_px)))
                lines[-1] = (merged[: max(0, max_chars - 3)].rstrip() + "...") if len(merged) > max_chars else merged
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
- support: one complete explanation sentence, <= 16 words
- secondary: always empty for normal text overlays
- keep the meaning faithful to the transcript
- do not invent entities, slogans, taglines, or cryptic labels
- avoid fragments like 'PLAY -> UNDERSTAND'
- avoid category words like INSIGHT, NOTE, OBSERVATION
- prefer conclusion-plus-explanation wording over decorative poster wording
- prefer exactly 2 textual layers only: headline + support
- do not create extra notes, follow-up lines, or alternative phrasings

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
                    if mode != "mechanism":
                        secondary = ""
                        support = self._clean_copy(support, 90)
                    return {
                        'headline': self._clean_copy(headline, 64),
                        'support': self._clean_copy(support, 90),
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
        bg_color = design.get("recommended_bg", "none")
        border_color = design.get("recommended_border", "none")
        bg_opacity = design.get("svg_bg_opacity", 0.0)
        bg_color = design.get("recommended_bg", "none")
        border_color = design.get("recommended_border", "none")
        bg_opacity = design.get("svg_bg_opacity", 0.0)
        copy_pack = self._fallback_copy(transcript, payload, mode)
        title = copy_pack.get("headline") or self._derive_title(transcript, payload, mode)
        subtitle = copy_pack.get("support") or self._derive_subtitle(transcript, payload, mode)

        pad_x = max(44, int(width * 0.10))
        title_fs = max(30, min(72, width // 18))
        subtitle_fs = max(18, min(32, width // 30))
        title_lines = self._wrap_text(title, width - 2 * pad_x, title_fs, max_lines=4)
        subtitle_lines = self._wrap_text(subtitle, width - 2 * pad_x, subtitle_fs, max_lines=4)
        while title_fs > 20:
            title_lines = self._wrap_text(title, width - 2 * pad_x, title_fs, max_lines=4)
            subtitle_lines = self._wrap_text(subtitle, width - 2 * pad_x, subtitle_fs, max_lines=4)
            total_height = (
                len(title_lines) * int(title_fs * 1.05) +
                max(24, int(height * 0.08)) +
                len(subtitle_lines) * int(subtitle_fs * 1.24)
            )
            if total_height <= int(height * 0.72):
                break
            title_fs -= 2
            subtitle_fs = max(16, subtitle_fs - 1)
        title_line_h = int(title_fs * 1.05)
        subtitle_line_h = int(subtitle_fs * 1.24)
        title_y = max(92, int(height * 0.24))
        divider_y = title_y + title_line_h * max(1, len(title_lines)) + max(18, int(height * 0.06))
        subtitle_y = divider_y + max(34, int(height * 0.12))
        title_w = max(120, min(width - 2 * pad_x, int(max(len(line) for line in title_lines or [title]) * max(18, title_fs * 0.56))))
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
    {self._build_multiline_text(pad_x, title_y, title_fs, title_line_h, title_lines, text_color, '800', extra='class="fade-in title-text"')}
    <line x1="{pad_x}" y1="{divider_y}" x2="{pad_x + int(title_w * 0.72)}" y2="{divider_y}" stroke="{primary}" stroke-width="2.8" stroke-linecap="round" class="sweep-line" />
    {self._build_multiline_text(pad_x, subtitle_y, subtitle_fs, subtitle_line_h, subtitle_lines, text_color, '600', extra='opacity="0.94" class="fade-in body-text"')}
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
