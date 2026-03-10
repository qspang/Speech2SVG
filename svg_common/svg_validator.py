"""
SVG Validator — Local Validation + CSS Bug Fix
================================================

Pure Python — no LLM calls.
Validates SVG structure and fixes common CSS bugs that cause
elements to be invisible or mispositioned.

Key fixes (ported from svg_agent/svg_creator_agent._fix_all_css_bugs):
1. opacity: 0 locked in CSS class (should only be in @keyframes from{})
2. CSS transform overriding SVG transform="translate()"
3. Missing viewBox or wrong dimensions
"""

import re
import os
from typing import Dict, Tuple

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


def validate_and_fix(svg_content: str) -> Tuple[str, Dict]:
    """
    Validate and fix SVG content.

    Args:
        svg_content: Raw SVG string

    Returns:
        (fixed_svg, report)
        report: {"valid": bool, "issues": [...], "fixes_applied": [...]}
    """
    issues = []
    fixes = []

    # ── 1. Basic structure check ──────────────────────────────────
    if not svg_content or not svg_content.strip():
        return _emergency_fallback(), {
            "valid": False,
            "issues": ["Empty SVG content"],
            "fixes_applied": ["Generated emergency fallback"],
        }

    if "<svg" not in svg_content.lower():
        return _emergency_fallback(), {
            "valid": False,
            "issues": ["No <svg> tag found"],
            "fixes_applied": ["Generated emergency fallback"],
        }

    # ── 2. XML well-formedness ────────────────────────────────────
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(svg_content)
    except ET.ParseError as e:
        issues.append(f"XML parse error: {e}")
        # Try to fix common XML issues
        svg_content = _fix_xml_issues(svg_content)
        try:
            ET.fromstring(svg_content)
            fixes.append("Fixed XML structure")
        except ET.ParseError:
            issues.append("Could not fix XML — returning as-is")

    # ── 3. viewBox check ──────────────────────────────────────────
    if "viewBox" not in svg_content:
        svg_content = svg_content.replace(
            "<svg",
            f'<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}"',
            1,
        )
        fixes.append("Added missing viewBox")

    # ── 4. CSS bug fixes ──────────────────────────────────────────
    svg_content, css_fixes = _fix_css_bugs(svg_content)
    fixes.extend(css_fixes)

    # ── 5. Ensure xmlns ───────────────────────────────────────────
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_content:
        svg_content = svg_content.replace(
            "<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1
        )
        fixes.append("Added missing xmlns")

    valid = len(issues) == 0 or len(fixes) > 0
    return svg_content, {
        "valid": valid,
        "issues": issues,
        "fixes_applied": fixes,
    }


def save_svg(svg_content: str, output_dir: str, sample_id: str) -> str:
    """Save SVG to file and optionally render PNG."""
    os.makedirs(output_dir, exist_ok=True)
    svg_path = os.path.join(output_dir, f"{sample_id}.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    # Try to render PNG for visual review
    png_path = _render_png(svg_path)

    print(f"  [Validator] Saved: {svg_path}")
    if png_path:
        print(f"  [Validator] PNG:   {png_path}")

    return svg_path


# ====================================================================
#  CSS Bug Fixes
# ====================================================================

def _fix_css_bugs(svg_content: str) -> Tuple[str, list]:
    """
    Fix the most common CSS bugs from LLM-generated SVG.
    Ported and enhanced from svg_agent/svg_creator_agent._fix_all_css_bugs()
    """
    fixes = []

    # ── Fix 0: Remove <animateMotion> (causes elements at 0,0) ────
    if "<animateMotion" in svg_content:
        svg_content = re.sub(
            r"<animateMotion[^>]*(?:/>|>[^<]*</animateMotion>)",
            "",
            svg_content,
        )
        fixes.append("Removed <animateMotion> (causes position conflicts)")

    # Find <style> blocks
    style_match = re.search(r"<style[^>]*>([\s\S]*?)</style>", svg_content)
    if style_match:
        style_content = style_match.group(1)
        original_style = style_content

        # ── Fix 0.5: Repair broken @keyframes (unclosed braces) ───
        # Count braces - if unbalanced, try to fix
        open_count = style_content.count("{")
        close_count = style_content.count("}")
        if open_count > close_count:
            style_content += "}" * (open_count - close_count)
            fixes.append("Fixed unclosed CSS braces")

        # Protect @keyframes blocks from opacity modification
        keyframes = {}
        kf_counter = [0]

        def save_kf(match):
            key = f"__KF_{kf_counter[0]}__"
            kf_counter[0] += 1
            keyframes[key] = match.group(0)
            return key

        style_no_kf = re.sub(
            r"@keyframes\s+\w+\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}",
            save_kf,
            style_content,
        )

        # ── Fix 1: opacity: 0 in class bodies ────────────────────
        if re.search(r"[^@].*opacity\s*:\s*0\s*;", style_no_kf):
            style_no_kf = re.sub(
                r"((?:^|\})[^{]*\{[^}]*?)opacity\s*:\s*0\s*;",
                r"\1opacity: 1;",
                style_no_kf,
            )
            fixes.append("Fixed opacity:0 locked in CSS class")

        # ── Fix 2: Remove transform:translate from class bodies ───
        if re.search(r"transform\s*:\s*translate", style_no_kf):
            style_no_kf = re.sub(
                r"transform\s*:\s*translate[^;]*;",
                "",
                style_no_kf,
            )
            fixes.append("Removed CSS transform:translate from class bodies")

        # Restore @keyframes
        for key, val in keyframes.items():
            style_no_kf = style_no_kf.replace(key, val)

        # ── Fix 2b: Remove transform:translate INSIDE @keyframes ──
        # This is the CRITICAL fix: CSS transform in keyframes
        # overrides SVG transform="translate()", causing elements
        # to snap to (0,0). We strip translate but keep scale/rotate.
        kf_transform_pattern = re.compile(
            r"(from|to|[0-9]+%)\s*\{([^}]*)\}",
            re.MULTILINE,
        )

        def clean_kf_transform(match):
            prefix = match.group(1)
            body = match.group(2)
            # Remove translateX, translateY, translate() from transform
            if re.search(r"transform\s*:", body):
                # Check if it's a pure translate (no scale/rotate mixed in)
                if re.search(r"transform\s*:\s*translate", body):
                    # Remove the entire transform property
                    body = re.sub(r"transform\s*:\s*[^;]*translate[^;]*;?\s*", "", body)
                    return f"{prefix} {{{body}}}"
            return match.group(0)

        cleaned = kf_transform_pattern.sub(clean_kf_transform, style_no_kf)
        if cleaned != style_no_kf:
            style_no_kf = cleaned
            fixes.append("Removed transform:translate from @keyframes (prevents position conflict)")

        if style_no_kf != original_style:
            svg_content = svg_content.replace(original_style, style_no_kf)

    # ── Fix 3: Inject safety rule ─────────────────────────────────
    safety_css = "\n    /* Safety: ensure groups are visible */\n    g { opacity: 1; }\n"
    if "g { opacity: 1" not in svg_content and "<style" in svg_content:
        svg_content = svg_content.replace("</style>", f"{safety_css}  </style>")
        fixes.append("Injected g opacity safety rule")

    return svg_content, fixes


# ====================================================================
#  XML Fixes
# ====================================================================

def _fix_xml_issues(svg_content: str) -> str:
    """Try to fix common XML issues."""
    # Fix unescaped ampersands in text (not in entities)
    svg_content = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", svg_content)

    # Fix unclosed tags — ensure </svg> exists
    if "</svg>" not in svg_content:
        svg_content += "\n</svg>"

    return svg_content


# ====================================================================
#  PNG Rendering
# ====================================================================

def _render_png(svg_path: str) -> str:
    """Render SVG to PNG if cairosvg is available."""
    try:
        import cairosvg
        png_path = svg_path.replace(".svg", ".png")
        cairosvg.svg2png(
            url=svg_path,
            write_to=png_path,
            output_width=CANVAS_WIDTH,
            output_height=CANVAS_HEIGHT,
        )
        return png_path
    except ImportError:
        return ""
    except Exception as e:
        print(f"  [Validator] PNG render failed (non-fatal): {e}")
        return ""


# ====================================================================
#  Emergency Fallback
# ====================================================================

def _emergency_fallback() -> str:
    """Minimal valid SVG when everything fails."""
    return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}"
     xmlns="http://www.w3.org/2000/svg">
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="#0d1117"/>
  <text x="960" y="540" font-family="sans-serif" font-size="36"
        fill="#64ffda" text-anchor="middle">
    [SVG Generation Failed — Fallback]
  </text>
</svg>'''
