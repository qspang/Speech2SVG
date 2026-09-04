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

import math
import re
import os
from typing import Any, Dict, List, Tuple

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


def simple_render_test(svg_content: str, state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """先做一次最直接的渲染测试，失败时上游应优先重生而不是继续修补。"""
    state = state or {}
    try:
        import cairosvg
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode="w", encoding="utf-8") as f:
            f.write(svg_content)
            temp_svg_path = f.name

        try:
            png_data = cairosvg.svg2png(url=temp_svg_path, write_to=None)
            if not png_data or len(png_data) < 10:
                return {"renders_successfully": False, "error": "Rendered PNG is empty"}
            print("  [Validator] Simple render test: passed")
            return {"renders_successfully": True, "error": None}
        finally:
            if os.path.exists(temp_svg_path):
                os.remove(temp_svg_path)

    except ImportError:
        print("  [Validator] cairosvg not installed/found")
        return {"renders_successfully": False, "error": "cairosvg not available", "fallback": True}
    except Exception as e:
        print(f"    [Validator DEBUG] Render failed for temp file {state.get('svg_path', 'unknown')}: {str(e)}")
        return {"renders_successfully": False, "error": str(e)}


def detect_top_left_cluster(svg_content: str) -> Dict[str, Any]:
    """做一个轻量 DOM 几何检查，重点抓左上角聚集和关键组缺少 translate。"""
    try:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(svg_content)
        suspicious_groups: List[Dict[str, Any]] = []

        for path, group, bbox, stats in _collect_group_geometry(root):
            if bbox is None:
                continue
            min_x, min_y, max_x, max_y = bbox
            width = max_x - min_x
            height = max_y - min_y
            center_x = (min_x + max_x) / 2.0
            center_y = (min_y + max_y) / 2.0
            shape_weight = stats["shape_count"] + stats["text_count"] * 2
            near_top_left = (
                min_x < CANVAS_WIDTH * 0.08
                and min_y < CANVAS_HEIGHT * 0.08
                and center_x < CANVAS_WIDTH * 0.22
                and center_y < CANVAS_HEIGHT * 0.24
            )
            significant = (
                shape_weight >= 4
                and width >= 120
                and height >= 120
            )
            missing_translate = (
                not stats["has_translate"]
                and min_x < 20
                and min_y < 20
                and max_x < CANVAS_WIDTH * 0.38
                and max_y < CANVAS_HEIGHT * 0.42
                and shape_weight >= 4
            )
            spans_origin = min_x < 40 and min_y < 40 and any(v < 0 for v in stats["raw_coords"]) and any(v > 0 for v in stats["raw_coords"])

            if near_top_left and significant and (missing_translate or spans_origin):
                suspicious_groups.append({
                    "path": path,
                    "bbox": {
                        "min_x": round(min_x, 1),
                        "min_y": round(min_y, 1),
                        "max_x": round(max_x, 1),
                        "max_y": round(max_y, 1),
                        "width": round(width, 1),
                        "height": round(height, 1),
                    },
                    "center": {
                        "x": round(center_x, 1),
                        "y": round(center_y, 1),
                    },
                    "shape_count": stats["shape_count"],
                    "text_count": stats["text_count"],
                    "has_translate": stats["has_translate"],
                    "reason": "missing_translate_top_left_cluster" if missing_translate else "origin_local_geometry_cluster",
                })

        flagged = len(suspicious_groups) > 0
        if flagged:
            print(f"  [Validator] Top-left geometry cluster detected: {len(suspicious_groups)} suspicious groups")
        return {
            "flagged": flagged,
            "suspicious_groups": suspicious_groups,
            "reason": "top_left_cluster_detected" if flagged else None,
        }
    except Exception as e:
        print(f"  [Validator] Top-left geometry check error: {e}")
        return {
            "flagged": False,
            "suspicious_groups": [],
            "reason": f"geometry_check_error: {e}",
        }


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
    print("  [Validator] validate_and_fix: start")

    # ── 1. Basic structure check ──────────────────────────────────
    if not svg_content or not svg_content.strip():
        print("  [Validator] Empty SVG content, using emergency fallback")
        return _emergency_fallback(), {
            "valid": False,
            "issues": ["Empty SVG content"],
            "fixes_applied": ["Generated emergency fallback"],
        }

    if "<svg" not in svg_content.lower():
        print("  [Validator] Missing <svg> tag, using emergency fallback")
        return _emergency_fallback(), {
            "valid": False,
            "issues": ["No <svg> tag found"],
            "fixes_applied": ["Generated emergency fallback"],
        }

    # ── 2. XML well-formedness ────────────────────────────────────
    print("  [Validator] XML parse: start")
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(svg_content)
        print("  [Validator] XML parse: ok")
    except ET.ParseError as e:
        print(f"  [Validator] XML parse: failed -> {e}")
        issues.append(f"XML parse error: {e}")
        # Try to fix common XML issues
        svg_content = _fix_xml_issues(svg_content)
        try:
            ET.fromstring(svg_content)
            fixes.append("Fixed XML structure")
            print("  [Validator] XML parse after fix: ok")
        except ET.ParseError:
            issues.append("Could not fix XML — returning as-is")
            print("  [Validator] XML parse after fix: still failed")

    # ── 3. viewBox check ──────────────────────────────────────────
    if "viewBox" not in svg_content:
        svg_content = svg_content.replace(
            "<svg",
            f'<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}"',
            1,
        )
        fixes.append("Added missing viewBox")
        print("  [Validator] Added missing viewBox")

    # ── 4. CSS bug fixes ──────────────────────────────────────────
    print("  [Validator] CSS fix: start")
    svg_content, css_fixes = _fix_css_bugs(svg_content)
    fixes.extend(css_fixes)
    print(f"  [Validator] CSS fix: done ({len(css_fixes)} fixes)")

    # ── 4.5. Remove accidental full-canvas background plates ─────
    svg_content, bg_fixes = _strip_full_canvas_backgrounds(svg_content)
    fixes.extend(bg_fixes)
    if bg_fixes:
        print(f"  [Validator] Background strip: done ({len(bg_fixes)} fixes)")

    # ── 5. Ensure xmlns ───────────────────────────────────────────
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_content:
        svg_content = svg_content.replace(
            "<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1
        )
        fixes.append("Added missing xmlns")
        print("  [Validator] Added missing xmlns")

    valid = len(issues) == 0 or len(fixes) > 0
    print(f"  [Validator] validate_and_fix: done (valid={valid}, issues={len(issues)}, fixes={len(fixes)})")
    return svg_content, {
        "valid": valid,
        "issues": issues,
        "fixes_applied": fixes,
    }


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_translate(transform: str | None) -> Tuple[float, float]:
    if not transform:
        return 0.0, 0.0
    match = re.search(r"translate\(\s*([-\d.]+)(?:[\s,]+([-\d.]+))?\s*\)", transform)
    if not match:
        return 0.0, 0.0
    tx = float(match.group(1))
    ty = float(match.group(2) or 0.0)
    return tx, ty


def _merge_bbox(a: Tuple[float, float, float, float] | None, b: Tuple[float, float, float, float] | None):
    if a is None:
        return b
    if b is None:
        return a
    return (
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3]),
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _extract_numbers(text: str | None) -> List[float]:
    if not text:
        return []
    return [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", text)]


def _estimate_element_bbox(element, tx: float, ty: float):
    tag = _strip_ns(element.tag)
    if tag in {"animate", "animateTransform", "defs", "filter", "linearGradient", "radialGradient", "stop", "feGaussianBlur", "feMerge", "feMergeNode"}:
        return None, []

    if tag == "circle":
        cx = _safe_float(element.get("cx")) + tx
        cy = _safe_float(element.get("cy")) + ty
        r = abs(_safe_float(element.get("r")))
        return (cx - r, cy - r, cx + r, cy + r), [cx - tx, cy - ty, r]

    if tag == "ellipse":
        cx = _safe_float(element.get("cx")) + tx
        cy = _safe_float(element.get("cy")) + ty
        rx = abs(_safe_float(element.get("rx")))
        ry = abs(_safe_float(element.get("ry")))
        return (cx - rx, cy - ry, cx + rx, cy + ry), [cx - tx, cy - ty, rx, ry]

    if tag == "rect":
        x = _safe_float(element.get("x")) + tx
        y = _safe_float(element.get("y")) + ty
        w = abs(_safe_float(element.get("width")))
        h = abs(_safe_float(element.get("height")))
        return (x, y, x + w, y + h), [x - tx, y - ty, w, h]

    if tag == "line":
        x1 = _safe_float(element.get("x1")) + tx
        y1 = _safe_float(element.get("y1")) + ty
        x2 = _safe_float(element.get("x2")) + tx
        y2 = _safe_float(element.get("y2")) + ty
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)), [x1 - tx, y1 - ty, x2 - tx, y2 - ty]

    if tag in {"polygon", "polyline"}:
        nums = _extract_numbers(element.get("points"))
        if len(nums) < 4:
            return None, nums
        xs = nums[0::2]
        ys = nums[1::2]
        return (min(xs) + tx, min(ys) + ty, max(xs) + tx, max(ys) + ty), nums

    if tag == "path":
        nums = _extract_numbers(element.get("d"))
        if len(nums) < 2:
            return None, nums
        xs = nums[0::2]
        ys = nums[1::2]
        if not ys:
            return None, nums
        return (min(xs) + tx, min(ys) + ty, max(xs) + tx, max(ys) + ty), nums

    if tag == "text":
        x = _safe_float(element.get("x")) + tx
        y = _safe_float(element.get("y")) + ty
        font_size = max(12.0, _safe_float(element.get("font-size"), 32.0))
        text = "".join(element.itertext()).strip()
        est_width = max(font_size * 0.8, len(text) * font_size * 0.55)
        est_height = font_size * 1.15
        anchor = (element.get("text-anchor") or "").strip()
        if anchor == "middle":
            min_x = x - est_width / 2.0
            max_x = x + est_width / 2.0
        elif anchor == "end":
            min_x = x - est_width
            max_x = x
        else:
            min_x = x
            max_x = x + est_width
        min_y = y - est_height
        max_y = y + font_size * 0.2
        return (min_x, min_y, max_x, max_y), [x - tx, y - ty, font_size]

    return None, []


def _compute_group_bbox(group, inherited_tx: float = 0.0, inherited_ty: float = 0.0):
    transform = group.get("transform")
    local_tx, local_ty = _parse_translate(transform)
    tx = inherited_tx + local_tx
    ty = inherited_ty + local_ty
    bbox = None
    stats = {
        "shape_count": 0,
        "text_count": 0,
        "has_translate": bool(transform and "translate" in transform),
        "raw_coords": [],
    }

    for child in list(group):
        tag = _strip_ns(child.tag)
        if tag == "g":
            child_bbox, child_stats = _compute_group_bbox(child, tx, ty)
            bbox = _merge_bbox(bbox, child_bbox)
            stats["shape_count"] += child_stats["shape_count"]
            stats["text_count"] += child_stats["text_count"]
            stats["has_translate"] = stats["has_translate"] or child_stats["has_translate"]
            stats["raw_coords"].extend(child_stats["raw_coords"])
            continue

        child_bbox, raw_values = _estimate_element_bbox(child, tx, ty)
        bbox = _merge_bbox(bbox, child_bbox)
        stats["raw_coords"].extend(raw_values)
        if child_bbox is not None:
            if tag == "text":
                stats["text_count"] += 1
            else:
                stats["shape_count"] += 1

    return bbox, stats


def _collect_group_geometry(root) -> List[Tuple[str, Any, Tuple[float, float, float, float] | None, Dict[str, Any]]]:
    groups = []

    def walk(node, path: str, tx: float, ty: float):
        transform = node.get("transform")
        local_tx, local_ty = _parse_translate(transform)
        current_tx = tx + local_tx
        current_ty = ty + local_ty
        for idx, child in enumerate(list(node)):
            if _strip_ns(child.tag) != "g":
                continue
            child_path = f"{path}/g[{idx}]"
            bbox, stats = _compute_group_bbox(child, tx, ty)
            groups.append((child_path, child, bbox, stats))
            walk(child, child_path, current_tx, current_ty)

    walk(root, "svg", 0.0, 0.0)
    return groups


def save_svg(svg_content: str, output_dir: str, sample_id: str) -> str:
    """Save SVG to file and optionally render PNG."""
    os.makedirs(output_dir, exist_ok=True)
    svg_path = os.path.join(output_dir, f"{sample_id}.svg")
    print(f"  [Validator] Writing SVG file: {svg_path}")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print("  [Validator] SVG file write: done")

    # Try to render PNG for visual review
    print("  [Validator] PNG render: start")
    png_path = _render_png(svg_path)
    print("  [Validator] PNG render: done")

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

    # ── Fix 0.2: Allow safe animateTransform but strip translate ──
    if "animateTransform" in svg_content:
        cleaned_svg = re.sub(
            r"<animateTransform([^>]*?)type\s*=\s*['\"]translate['\"]([^>]*?)(?:/>|>.*?</animateTransform>)",
            "",
            svg_content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if cleaned_svg != svg_content:
            svg_content = cleaned_svg
            fixes.append("Removed animateTransform translate (unsafe for overlay positioning)")

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


def _strip_full_canvas_backgrounds(svg_content: str) -> Tuple[str, list]:
    """Remove full-canvas background rects so overlay SVGs stay transparent."""
    fixes = []
    rect_pattern = re.compile(r"<rect\b[^>]*>", re.IGNORECASE)

    def should_strip(tag: str) -> bool:
        lower = tag.lower()
        if 'fill="none"' in lower or "fill='none'" in lower or 'fill-opacity="0"' in lower or "fill-opacity='0'" in lower:
            return False
        width_hit = any(token in lower for token in (
            'width="1920"', "width='1920'", 'width="100%"', "width='100%'",
            f'width="{CANVAS_WIDTH}"', f"width='{CANVAS_WIDTH}'"
        ))
        height_hit = any(token in lower for token in (
            'height="1080"', "height='1080'", 'height="100%"', "height='100%'",
            f'height="{CANVAS_HEIGHT}"', f"height='{CANVAS_HEIGHT}'"
        ))
        x_ok = ('x="0"' in lower or "x='0'" in lower or ' x=' not in lower)
        y_ok = ('y="0"' in lower or "y='0'" in lower or ' y=' not in lower)
        return width_hit and height_hit and x_ok and y_ok

    matches = rect_pattern.findall(svg_content)
    for tag in matches:
        if should_strip(tag):
            svg_content = svg_content.replace(tag, "", 1)
            fixes.append("Removed full-canvas background rect to preserve transparency")
            break

    return svg_content, fixes


# ====================================================================
#  PNG Rendering
# ====================================================================

def _render_png(svg_path: str) -> str:
    """Render SVG to PNG if cairosvg is available."""
    try:
        import cairosvg
        png_path = svg_path.replace(".svg", ".png")
        print(f"  [Validator] cairosvg render -> {png_path}")
        cairosvg.svg2png(
            url=svg_path,
            write_to=png_path,
            output_width=CANVAS_WIDTH,
            output_height=CANVAS_HEIGHT,
        )
        print("  [Validator] cairosvg render: success")
        return png_path
    except ImportError:
        print("  [Validator] cairosvg not installed, skip PNG render")
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
  <text x="960" y="540" font-family="sans-serif" font-size="36"
        fill="#64ffda" text-anchor="middle">
    [SVG Generation Failed — Fallback]
  </text>
</svg>'''
