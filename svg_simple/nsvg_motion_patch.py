"""
NSVG Motion Patch
=================

Batch post-process existing SVG overlays with a vision-capable Gemini model.

Workflow for each existing SVG:
1. Render SVG to PNG preview
2. Ask Gemini to inspect BOTH the rendered image and the SVG source code
3. Score the current motion quality
4. If average score >= threshold:
   - keep the original SVG (after validator checks)
   - save to assets/nsvg/<same_name>.svg
5. If average score < threshold:
   - ask Gemini to MODIFY the original SVG instead of rewriting from scratch
   - validate the refined SVG
   - retry refinement if validation fails

Outputs:
- temp_analysis/assets/nsvg/*.svg
- temp_analysis/assets/nsvg/*.png (rendered by svg_validator.save_svg)
- temp_analysis/nsvg_patch_records.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

if __package__ in (None, ""):
    sys.path.append("/home/ubuntu/sysu/svgagent/video_enhance/video_sys/svg_simple")
    import svg_validator
    from custom_chat_model import CustomChatModel
else:
    from . import svg_validator
    from .custom_chat_model import CustomChatModel


PROJECT_ROOT = Path("/home/ubuntu/sysu/svgagent")
ENHANCED_ROOT = PROJECT_ROOT / "video_enhance" / "enhanced_videos"
DEFAULT_VIDEO_IDS = [str(i) for i in range(1, 11)]
PRINT_LOCK = threading.Lock()
MAX_LLM_RETRIES = 3
RETRY_WAIT_SECONDS = 10


def log(message: str) -> None:
    with PRINT_LOCK:
        print(message, flush=True)


def extract_svg(text: str) -> str:
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


def render_svg_preview(svg_content: str, sample_id: str) -> Dict[str, Any]:
    try:
        import cairosvg

        with tempfile.NamedTemporaryFile(suffix=f"_{sample_id}.png", delete=False) as f:
            png_path = f.name
        cairosvg.svg2png(bytestring=svg_content.encode("utf-8"), write_to=png_path)
        return {"ok": True, "image_path": png_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_with_retry(fn, step_name: str, video_id: str, filename: str):
    last_error = None
    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            log(
                f"      retry {attempt}/{MAX_LLM_RETRIES} failed for {step_name} "
                f"(video={video_id}, file={filename}): {exc}"
            )
            if attempt < MAX_LLM_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS)
    raise last_error


class MotionPatchAgent:
    def __init__(self, llm_type: str = "gemini-3.1-pro-high", min_score: float = 7.0):
        self.llm_type = llm_type
        self.min_score = min_score
        self.llm = CustomChatModel(llm_type=self.llm_type, temperature=0.35)

    def evaluate(self, svg_content: str, image_path: str, video_id: str, filename: str) -> Dict[str, Any]:
        if not self.llm.supports_vision():
            raise RuntimeError(f"{self.llm_type} does not support vision input")

        system_prompt = self._build_eval_system_prompt()
        user_prompt = self._build_eval_user_prompt(svg_content, video_id, filename)
        messages = [
            SystemMessage(content=system_prompt),
            self.llm.create_vision_message(user_prompt, image_path),
        ]
        result = self.llm._generate(messages)
        content = result.generations[0].message.content
        parsed = self.llm.parse_json_response(content)
        return self._normalize_eval(parsed, raw_response=str(content))

    def refine(
        self,
        svg_content: str,
        image_path: str,
        critic_report: Dict[str, Any],
        video_id: str,
        filename: str,
    ) -> str:
        system_prompt = self._build_refine_system_prompt()
        user_prompt = self._build_refine_user_prompt(svg_content, critic_report, video_id, filename)
        messages = [
            SystemMessage(content=system_prompt),
            self.llm.create_vision_message(user_prompt, image_path),
        ]
        result = self.llm._generate(messages)
        content = result.generations[0].message.content
        refined = extract_svg(str(content))
        if "<svg" not in refined.lower() or "</svg>" not in refined.lower():
            raise ValueError("Gemini did not return valid SVG")
        return refined

    def _build_eval_system_prompt(self) -> str:
        return """You are a strict visual animation critic for educational SVG overlays.

You must inspect:
1. the rendered SVG image
2. the raw SVG source code

The project goal is animated SVG overlays for videos. Focus especially on whether
the motion feels meaningful, alive, and integrated with the existing icons/entities.

Score from 0.0 to 10.0 on exactly these five dimensions:
1. motion_liveliness
2. semantic_motion_fit
3. readability_preservation
4. entity_icon_animation_quality
5. overall_dynamic_polish

Definitions:
- motion_liveliness: whether the SVG already has enough visible motion rather than feeling static
- semantic_motion_fit: whether the motion supports the meaning instead of being decorative noise
- readability_preservation: whether animation keeps labels/text/icon relationships understandable
- entity_icon_animation_quality: whether icons, entities, nodes, connections, or focal objects have meaningful motion potential or execution
- overall_dynamic_polish: overall animation quality, balance, timing, and coherence

Rules:
- Be strict.
- Even if the score is high, still give improvement suggestions.
- If the current motion is already good enough, say so clearly.
- Return JSON only.

JSON schema:
{
  "scores": {
    "motion_liveliness": 0.0,
    "semantic_motion_fit": 0.0,
    "readability_preservation": 0.0,
    "entity_icon_animation_quality": 0.0,
    "overall_dynamic_polish": 0.0
  },
  "average_score": 0.0,
  "keep_original": true,
  "strengths": ["..."],
  "issues": ["..."],
  "improvement_suggestions": ["..."],
  "summary": "..."
}"""

    def _build_eval_user_prompt(self, svg_content: str, video_id: str, filename: str) -> str:
        return (
            "Evaluate this existing animated SVG overlay.\n"
            "Important: do NOT suggest rewriting it from scratch. Judge how good the current motion is, "
            "and whether it should be kept as-is or enhanced.\n\n"
            f"Video ID: {video_id}\n"
            f"Filename: {filename}\n\n"
            "Raw SVG source code:\n"
            f"{svg_content}"
        )

    def _build_refine_system_prompt(self) -> str:
        return """You are improving an existing educational animated SVG overlay.

You must inspect BOTH:
1. the rendered SVG image
2. the raw SVG source code

Your task is NOT to redesign from scratch.
You must MODIFY the existing SVG on top of its current structure.

Primary goal:
- make the animation more alive, meaningful, and engaging
- especially improve motion on icons, entities, nodes, connectors, focal objects, halos, pulses, reveals, oscillations, rotations, and relationship flows where appropriate

Important rules:
- Output RAW SVG only
- Preserve the original topic and composition unless small changes are necessary
- Keep the background transparent
- Keep text readable
- Prefer adding or strengthening simple, tasteful animation rather than adding clutter
- You may adjust positions, timing, grouping, opacity, strokes, glow, and motion details if needed
- Do not replace the whole SVG with a completely different concept
- Work by editing the current SVG, not inventing a new unrelated one
- Avoid unsafe translate animations that break overlay positioning
- Keep the result suitable for a small video overlay
"""

    def _build_refine_user_prompt(
        self,
        svg_content: str,
        critic_report: Dict[str, Any],
        video_id: str,
        filename: str,
    ) -> str:
        payload = {
            "video_id": video_id,
            "filename": filename,
            "critic_report": {
                "scores": critic_report.get("scores", {}),
                "average_score": critic_report.get("average_score", 0.0),
                "issues": critic_report.get("issues", []),
                "improvement_suggestions": critic_report.get("improvement_suggestions", []),
                "summary": critic_report.get("summary", ""),
            },
        }
        return (
            "Please improve the current SVG motion quality while preserving the original design intent.\n"
            "Look for places where icons, entities, nodes, connectors, or central objects can gain more meaningful motion.\n"
            "Subtle structural changes are allowed if they help the motion read better, but stay close to the original.\n\n"
            f"Context JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"Original SVG source:\n{svg_content}"
        )

    def _normalize_eval(self, parsed: Any, raw_response: str = "") -> Dict[str, Any]:
        dims = [
            "motion_liveliness",
            "semantic_motion_fit",
            "readability_preservation",
            "entity_icon_animation_quality",
            "overall_dynamic_polish",
        ]
        if not isinstance(parsed, dict):
            return {
                "ok": False,
                "scores": {dim: 0.0 for dim in dims},
                "average_score": 0.0,
                "keep_original": False,
                "strengths": [],
                "issues": ["invalid_json"],
                "improvement_suggestions": ["Add more meaningful motion while preserving readability."],
                "summary": "invalid_json",
                "raw_response": raw_response,
            }

        scores = parsed.get("scores", {}) if isinstance(parsed.get("scores"), dict) else {}
        normalized_scores: Dict[str, float] = {}
        for dim in dims:
            try:
                value = float(scores.get(dim, 0.0))
            except Exception:
                value = 0.0
            normalized_scores[dim] = round(max(0.0, min(10.0, value)), 2)
        average_score = round(sum(normalized_scores.values()) / len(dims), 2)

        def _coerce_list(value: Any) -> List[str]:
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            return []

        keep_original = bool(parsed.get("keep_original", average_score >= self.min_score))
        return {
            "ok": True,
            "scores": normalized_scores,
            "average_score": average_score,
            "keep_original": keep_original,
            "strengths": _coerce_list(parsed.get("strengths")),
            "issues": _coerce_list(parsed.get("issues")),
            "improvement_suggestions": _coerce_list(parsed.get("improvement_suggestions")),
            "summary": str(parsed.get("summary", "")).strip(),
            "raw_response": raw_response,
        }


def validate_candidate(svg_content: str, sample_id: str) -> Dict[str, Any]:
    render_test = svg_validator.simple_render_test(svg_content, {"sample_id": sample_id, "svg_path": None})
    if not render_test.get("renders_successfully"):
        return {
            "ok": False,
            "stage": "simple_render_test",
            "error": render_test.get("error"),
            "render_test": render_test,
        }

    geometry_check = svg_validator.detect_top_left_cluster(svg_content)
    if geometry_check.get("flagged"):
        return {
            "ok": False,
            "stage": "geometry_check",
            "error": geometry_check.get("reason"),
            "render_test": render_test,
            "geometry_check": geometry_check,
        }

    fixed_svg, validation = svg_validator.validate_and_fix(svg_content)
    post_render_test = svg_validator.simple_render_test(fixed_svg, {"sample_id": f"{sample_id}_fixed", "svg_path": None})
    if not post_render_test.get("renders_successfully"):
        return {
            "ok": False,
            "stage": "post_fix_render_test",
            "error": post_render_test.get("error"),
            "render_test": render_test,
            "validation": validation,
            "post_render_test": post_render_test,
        }

    post_geometry_check = svg_validator.detect_top_left_cluster(fixed_svg)
    if post_geometry_check.get("flagged"):
        return {
            "ok": False,
            "stage": "post_fix_geometry_check",
            "error": post_geometry_check.get("reason"),
            "render_test": render_test,
            "validation": validation,
            "post_render_test": post_render_test,
            "geometry_check": post_geometry_check,
            "post_geometry_check": post_geometry_check,
        }

    return {
        "ok": True,
        "svg_content": fixed_svg,
        "render_test": render_test,
        "validation": validation,
        "post_render_test": post_render_test,
        "geometry_check": geometry_check,
        "post_geometry_check": post_geometry_check,
    }


def process_svg_file(
    svg_path: Path,
    output_dir: Path,
    video_id: str,
    min_score: float,
    llm_type: str,
    max_refine_attempts: int,
    force: bool,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_svg_path = output_dir / svg_path.name
    output_png_path = output_dir / f"{svg_path.stem}.png"

    if not force and output_svg_path.exists():
        log(f"    skip existing nsvg: {output_svg_path}")
        return {
            "video_id": video_id,
            "filename": svg_path.name,
            "status": "skipped_existing",
            "output_svg_path": str(output_svg_path),
            "output_png_path": str(output_png_path) if output_png_path.exists() else None,
        }

    original_svg = svg_path.read_text(encoding="utf-8", errors="ignore")
    preview = render_svg_preview(original_svg, f"{video_id}_{svg_path.stem}")
    if not preview.get("ok"):
        log(f"    failed preview render: {svg_path.name} -> {preview.get('error')}")
        return {
            "video_id": video_id,
            "filename": svg_path.name,
            "status": "preview_render_failed",
            "error": preview.get("error"),
        }

    preview_path = preview["image_path"]
    agent = MotionPatchAgent(llm_type=llm_type, min_score=min_score)

    try:
        critic_report = run_with_retry(
            lambda: agent.evaluate(original_svg, preview_path, video_id, svg_path.name),
            "critic_evaluate",
            video_id,
            svg_path.name,
        )
        average = float(critic_report.get("average_score", 0.0) or 0.0)
        log(f"    critic {svg_path.name}: avg={average:.2f}/10")

        original_validation = validate_candidate(original_svg, f"{video_id}_{svg_path.stem}_original")
        if average >= min_score and original_validation.get("ok"):
            svg_validator.save_svg(original_validation["svg_content"], str(output_dir), svg_path.stem)
            log(f"    kept original -> {output_svg_path}")
            return {
                "video_id": video_id,
                "filename": svg_path.name,
                "status": "kept_original",
                "average_score": average,
                "critic_report": critic_report,
                "output_svg_path": str(output_svg_path),
                "output_png_path": str(output_png_path) if output_png_path.exists() else None,
            }

        best_error = None
        for attempt in range(1, max_refine_attempts + 1):
            log(f"    refine attempt {attempt}/{max_refine_attempts}: {svg_path.name}")
            refined_svg = run_with_retry(
                lambda: agent.refine(original_svg, preview_path, critic_report, video_id, svg_path.name),
                "critic_refine",
                video_id,
                svg_path.name,
            )
            refined_validation = validate_candidate(refined_svg, f"{video_id}_{svg_path.stem}_refined_{attempt}")
            if refined_validation.get("ok"):
                svg_validator.save_svg(refined_validation["svg_content"], str(output_dir), svg_path.stem)
                log(f"    refined and saved -> {output_svg_path}")
                return {
                    "video_id": video_id,
                    "filename": svg_path.name,
                    "status": "refined",
                    "average_score": average,
                    "critic_report": critic_report,
                    "output_svg_path": str(output_svg_path),
                    "output_png_path": str(output_png_path) if output_png_path.exists() else None,
                }
            best_error = {
                "attempt": attempt,
                "stage": refined_validation.get("stage"),
                "error": refined_validation.get("error"),
            }
            log(
                f"      refined candidate failed validator: {svg_path.name} "
                f"stage={refined_validation.get('stage')} error={refined_validation.get('error')}"
            )

        if original_validation.get("ok"):
            svg_validator.save_svg(original_validation["svg_content"], str(output_dir), svg_path.stem)
            log(f"    refine failed, fallback to original -> {output_svg_path}")
            return {
                "video_id": video_id,
                "filename": svg_path.name,
                "status": "fallback_original_after_failed_refine",
                "average_score": average,
                "critic_report": critic_report,
                "last_refine_error": best_error,
                "output_svg_path": str(output_svg_path),
                "output_png_path": str(output_png_path) if output_png_path.exists() else None,
            }

        return {
            "video_id": video_id,
            "filename": svg_path.name,
            "status": "failed",
            "average_score": average,
            "critic_report": critic_report,
            "original_validation_error": {
                "stage": original_validation.get("stage"),
                "error": original_validation.get("error"),
            },
            "last_refine_error": best_error,
        }
    finally:
        if preview_path and os.path.exists(preview_path):
            os.remove(preview_path)


def process_video(
    video_id: str,
    workers: int,
    min_score: float,
    llm_type: str,
    max_refine_attempts: int,
    force: bool,
) -> Dict[str, Any]:
    svg_dir = ENHANCED_ROOT / video_id / "temp_analysis" / "assets" / "svg"
    nsvg_dir = ENHANCED_ROOT / video_id / "temp_analysis" / "assets" / "nsvg"
    record_path = ENHANCED_ROOT / video_id / "temp_analysis" / "nsvg_patch_records.json"

    if not svg_dir.exists():
        log(f"  video {video_id}: svg dir missing -> {svg_dir}")
        return {"video_id": video_id, "status": "missing_svg_dir", "count": 0}

    svg_files = sorted(svg_dir.glob("*.svg"))
    log(f"  video {video_id}: found {len(svg_files)} svg files")
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {
            executor.submit(
                process_svg_file,
                svg_path,
                nsvg_dir,
                video_id,
                min_score,
                llm_type,
                max_refine_attempts,
                force,
            ): svg_path.name
            for svg_path in svg_files
        }
        for future in as_completed(future_map):
            filename = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                log(f"    fatal error: {filename} -> {exc}")
                results.append({
                    "video_id": video_id,
                    "filename": filename,
                    "status": "exception",
                    "error": str(exc),
                })

    results.sort(key=lambda item: item.get("filename", ""))
    record_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    kept = sum(1 for item in results if item.get("status") == "kept_original")
    refined = sum(1 for item in results if item.get("status") == "refined")
    skipped = sum(1 for item in results if item.get("status") == "skipped_existing")
    failed = sum(1 for item in results if item.get("status") in {"failed", "exception"})
    return {
        "video_id": video_id,
        "status": "done",
        "count": len(results),
        "kept_original": kept,
        "refined": refined,
        "skipped_existing": skipped,
        "failed": failed,
        "record_path": str(record_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch existing SVG overlays into more lively animated NSVG variants.")
    parser.add_argument("--video-ids", nargs="+", default=DEFAULT_VIDEO_IDS, help="Video IDs to process, default 1-10.")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers per video.")
    parser.add_argument("--video-workers", type=int, default=2, help="How many videos to process in parallel.")
    parser.add_argument("--llm-type", default="gemini-3.1-pro-high", help="Vision-capable LLM used for critic + refine.")
    parser.add_argument("--min-score", type=float, default=7.0, help="If average score >= this threshold and validation passes, keep original.")
    parser.add_argument("--max-refine-attempts", type=int, default=3, help="Max refine attempts if the original score is below threshold.")
    parser.add_argument("--force", action="store_true", help="Regenerate even if assets/nsvg already contains the target file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log(
        f"Starting nsvg motion patch for {len(args.video_ids)} videos "
        f"(video_workers={max(1, args.video_workers)}, workers={max(1, args.workers)}, "
        f"llm={args.llm_type}, min_score={args.min_score})"
    )

    summaries: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.video_workers)) as executor:
        future_map = {
            executor.submit(
                process_video,
                video_id,
                args.workers,
                args.min_score,
                args.llm_type,
                args.max_refine_attempts,
                args.force,
            ): video_id
            for video_id in args.video_ids
        }
        for future in as_completed(future_map):
            video_id = future_map[future]
            try:
                result = future.result()
                summaries.append(result)
                log(
                    f"done video {video_id}: count={result.get('count', 0)} "
                    f"kept={result.get('kept_original', 0)} refined={result.get('refined', 0)} "
                    f"skipped={result.get('skipped_existing', 0)} failed={result.get('failed', 0)}"
                )
            except Exception as exc:
                log(f"video {video_id} failed: {exc}")
                summaries.append({"video_id": video_id, "status": "exception", "error": str(exc)})

    summaries.sort(key=lambda item: str(item.get("video_id")))
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
