"""
SVG Common Main Entry (Normal Mode)
====================================

Pipeline:  VisualStrategy → SVGGenerator → SVGValidator
LLM calls: 2 (strategy + generation)

Interface is identical to svg_agent/main.py for seamless mode switching.
"""

import os
from typing import Dict, Any, Optional

from visual_strategy import VisualStrategy
from svg_generator import SVGGenerator
import svg_validator


def generate_svg_from_text(
    text_input: str,
    output_dir: str = None,
    save_file: bool = True,
    llm_type: str = "claude-sonnet-4-5-20250929",
    vision_llm_type: str = None,
    layout_context: Optional[Dict] = None,
    scene_context: Optional[Dict] = None,
    motion_context: Optional[Dict] = None,
    enable_complex_mode: bool = False,
    sample_id: str = "svg_output",
    visual_description: str = "",
) -> Dict[str, Any]:
    """
    Generate SVG animation from text (Normal Mode).

    Interface is identical to svg_agent/main.py.

    Pipeline:
        1. VisualStrategy — distill context + align content (LLM ×1)
        2. SVGGenerator  — generate SVG code (LLM ×1)
        3. SVGValidator   — local validation + CSS fix (no LLM)

    Args:
        text_input:           Subtitle text / topic description
        output_dir:           Output directory for SVG files
        save_file:            Whether to save to disk
        llm_type:             LLM type for text processing
        vision_llm_type:      Vision LLM type (unused in normal mode)
        layout_context:       Layout context from video system
        scene_context:        Scene context from video system
        enable_complex_mode:  Ignored (always normal in svg_common)
        sample_id:            Sample ID for file naming

    Returns:
        {
            "svg_content":    SVG string,
            "svg_path":       file path (if saved),
            "overall_score":  quality score,
            "workflow_mode":  "normal",
            "design_brief":   strategy output,
            ...
        }
    """
    print(f"\n  [svg_common] Generating SVG (Normal Mode)")
    print(f"  [svg_common] Topic: {text_input[:60]}...")

    # Output dir
    if save_file and output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # ── Step 1: Visual Strategy ─────────────────────────────────
    print(f"  [Step 1/3] Visual Strategy — context distillation + alignment")
    strategy = VisualStrategy(llm_type=llm_type)
    design_brief = strategy.create_design_brief(
        text_input=text_input,
        layout_context=layout_context,
        scene_context=scene_context,
        motion_context=motion_context,
        visual_description=visual_description,
    )
    print(f"    ✓ Topic: {design_brief.get('core_topic', 'N/A')}")
    print(f"    ✓ Visual type: {design_brief.get('visual_type', 'N/A')}")
    print(f"    ✓ Entities: {len(design_brief.get('entities', []))}")
    print(f"    ✓ Scene: {design_brief.get('scene_alignment', 'N/A')[:60]}")

    # ── Step 2: SVG Generation ──────────────────────────────────
    print(f"  [Step 2/3] SVG Generator — creating SVG code")
    generator = SVGGenerator(llm_type=llm_type)
    svg_content = generator.generate(design_brief)
    print(f"    ✓ SVG generated: {len(svg_content)} chars")

    # ── Step 3: Validation + Fix ────────────────────────────────
    print(f"  [Step 3/3] Validator — checking + fixing CSS bugs")
    svg_content, validation = svg_validator.validate_and_fix(svg_content)
    print(f"    ✓ Valid: {validation['valid']}")
    if validation["fixes_applied"]:
        for fix in validation["fixes_applied"]:
            print(f"    ✓ Fix: {fix}")

    # ── Save ────────────────────────────────────────────────────
    svg_path = None
    if save_file and output_dir:
        svg_path = svg_validator.save_svg(svg_content, output_dir, sample_id)

    # ── Result ──────────────────────────────────────────────────
    return {
        "svg_content": svg_content,
        "svg_path": svg_path,
        "overall_score": 7.0 if validation["valid"] else 4.0,
        "workflow_mode": "normal",
        "iteration": 1,
        "design_brief": design_brief,
        "validation": validation,
    }


def main():
    """CLI entry"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate SVG animation (Normal Mode)"
    )
    parser.add_argument("text", help="Input text to visualize")
    parser.add_argument(
        "--output", "-o", default="./svg_output", help="Output directory"
    )
    parser.add_argument(
        "--llm", default="claude-sonnet-4-5-20250929", help="LLM type"
    )
    parser.add_argument("--vision-llm", help="Vision LLM type (unused)")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"SVG Common — Normal Mode Generation")
    print(f"{'='*60}\n")

    result = generate_svg_from_text(
        text_input=args.text,
        output_dir=args.output,
        save_file=True,
        llm_type=args.llm,
        vision_llm_type=args.vision_llm,
    )

    print(f"\n{'='*60}")
    print(f"✓ Generation complete!")
    print(f"  SVG path: {result.get('svg_path', 'N/A')}")
    print(f"  Mode: {result.get('workflow_mode', 'N/A')}")
    print(f"  Score: {result.get('overall_score', 0)}/10")
    print(f"  Topic: {result.get('design_brief', {}).get('core_topic', 'N/A')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
