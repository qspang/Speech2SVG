"""
SVG Common Main Entry (Normal Mode)
====================================

Pipeline:
VisualStrategy → SVGGenerator → SVGValidator → VisualCritic → (optional) SVGRefiner → SVGValidator
"""

import os
from typing import Dict, Any, Optional

from visual_strategy import VisualStrategy
from svg_generator import SVGGenerator
import svg_validator
from visual_critic import VisualCritic
from svg_refine import SVGRefiner


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
        enable_complex_mode:  Ignored (always simple in svg_simple)
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
    print(f"\n  [svg_simple] Generating SVG (Simple Mode)")
    print(f"  [svg_simple] Topic: {text_input[:60]}...")

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
    print(f"  [Step 2/5] SVG Generator — creating SVG code")
    generator = SVGGenerator(llm_type=llm_type)
    max_generation_attempts = 3
    render_test = {"renders_successfully": False, "error": "not_run"}
    svg_content = ""
    geometry_check = {"flagged": False, "reason": None}

    for attempt in range(1, max_generation_attempts + 1):
        print(f"    [Generator] Attempt {attempt}/{max_generation_attempts}")
        svg_content = generator.generate(design_brief)
        print(f"    ✓ SVG generated: {len(svg_content)} chars")
        render_test = svg_validator.simple_render_test(
            svg_content,
            {"svg_path": None, "sample_id": sample_id, "attempt": attempt},
        )
        if render_test.get("renders_successfully"):
            geometry_check = svg_validator.detect_top_left_cluster(svg_content)
            if not geometry_check.get("flagged"):
                break
            render_test = {
                "renders_successfully": False,
                "error": f"geometry_cluster:{geometry_check.get('reason')}",
                "geometry_check": geometry_check,
            }
            print("    [Generator] Geometry check failed: suspicious top-left cluster detected")
        print(f"    [Generator] Render test failed, regenerating: {render_test.get('error')}")

    if not render_test.get("renders_successfully"):
        print("    [Generator] All render-test attempts failed, using fallback SVG")
        svg_content = generator._fallback_svg(design_brief)
        render_test = {"renders_successfully": True, "error": "fallback_svg_used"}

    # ── Step 3: Validation + Fix ────────────────────────────────
    print(f"  [Step 3/5] Validator — checking + fixing CSS bugs")
    print(f"    [Validator] Input SVG size: {len(svg_content)} chars")
    svg_content, validation = svg_validator.validate_and_fix(svg_content)
    print(f"    ✓ Valid: {validation['valid']}")
    if validation["issues"]:
        print(f"    [Validator] Issues: {validation['issues']}")
    if validation["fixes_applied"]:
        for fix in validation["fixes_applied"]:
            print(f"    ✓ Fix: {fix}")
    print(f"    [Validator] Output SVG size: {len(svg_content)} chars")

    # ── Step 4: Visual Critic ─────────────────────────────────────
    print(f"  [Step 4/5] Visual Critic — scoring rendered SVG")
    visual_critic = VisualCritic(vision_llm_type or llm_type)
    critic_report = visual_critic.evaluate(
        svg_content=svg_content,
        subtitle_text=text_input,
        design_brief=design_brief,
        sample_id=sample_id,
    )
    critic_average = float(critic_report.get("average_score", 0.0) or 0.0)
    print(f"    ✓ Critic average: {critic_average:.2f}/10")
    if critic_report.get("improvement_suggestions"):
        print(f"    ✓ Critic suggestions: {len(critic_report.get('improvement_suggestions', []))}")

    refine_applied = False
    refine_validation = None
    refine_render_test = None

    # ── Step 5: Refine if needed ──────────────────────────────────
    if critic_report.get("ok") and critic_average <= 8.5:
        print(f"  [Step 5/5] SVG Refiner — critic score <= 8.5, refining")
        refiner = SVGRefiner(llm_type=llm_type)
        try:
            refined_svg = refiner.refine(
                svg_content=svg_content,
                design_brief=design_brief,
                critic_report=critic_report,
            )
            refine_render_test = svg_validator.simple_render_test(
                refined_svg,
                {"svg_path": None, "sample_id": f"{sample_id}_refined"},
            )
            if refine_render_test.get("renders_successfully"):
                refined_geometry_check = svg_validator.detect_top_left_cluster(refined_svg)
                if refined_geometry_check.get("flagged"):
                    print("    [Refiner] Geometry check failed after refine, keeping pre-refine SVG")
                    refine_render_test = {
                        "renders_successfully": False,
                        "error": f"geometry_cluster:{refined_geometry_check.get('reason')}",
                        "geometry_check": refined_geometry_check,
                    }

            if refine_render_test.get("renders_successfully"):
                svg_content, refine_validation = svg_validator.validate_and_fix(refined_svg)
                refine_applied = True
                print("    ✓ Refine accepted and revalidated")
            else:
                print(f"    [Refiner] Render/geometry failed after refine: {refine_render_test.get('error')}")
        except Exception as e:
            print(f"    [Refiner] Failed: {e}")
    else:
        print(f"  [Step 5/5] SVG Refiner — skipped")

    # ── Save ────────────────────────────────────────────────────
    svg_path = None
    if save_file and output_dir:
        print(f"    [Validator] Saving SVG to output dir: {output_dir}")
        svg_path = svg_validator.save_svg(svg_content, output_dir, sample_id)

    # ── Result ──────────────────────────────────────────────────
    return {
        "svg_content": svg_content,
        "svg_path": svg_path,
        "overall_score": critic_average if critic_report.get("ok") else (7.0 if validation["valid"] else 4.0),
        "workflow_mode": "normal",
        "iteration": 1,
        "design_brief": design_brief,
        "validation": validation,
        "render_test": render_test,
        "geometry_check": geometry_check,
        "critic_report": critic_report,
        "refine_applied": refine_applied,
        "refine_validation": refine_validation,
        "refine_render_test": refine_render_test,
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
