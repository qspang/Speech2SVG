"""
Decision Agent
==============

Enhancement decision with:
  1. Global summary (cached) for full-video understanding
  2. Sliding context window (prev-3 / next-3) for local coherence
  3. Imaginative visual director prompt (vs. suppressive censor)
  4. Post-LLM rhythm control (relaxed)
"""

import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from multimodal_utils import save_decisions, load_decisions, simple_classify_segment


class DecisionAgent:
    """Decision Agent — imaginative visual director + context-aware classification"""

    def __init__(self, llm_type: str, vision_llm_type: str, output_dir: str):
        self.llm_type = llm_type
        self.vision_llm_type = vision_llm_type
        self.output_dir = output_dir
        self.decisions_path = os.path.join(output_dir, "enhancement_decisions.txt")
        self.summary_path = os.path.join(output_dir, "global_summary.txt")
        self.latest_global_summary = ""

    # ================================================================
    #  Main Entry
    # ================================================================

    def classify_segments(
        self,
        segments: List[Dict],
        force: bool = False,
        max_workers: int = 20,
        enhancement_points: List[Dict] = None,
    ) -> List[Dict]:
        """Classify semantic segments with context-aware visual direction."""
        if not force and os.path.exists(self.decisions_path):
            print(f"  > Loading cached decisions from {self.decisions_path}")
            return load_decisions(self.decisions_path)

        # ── Step 0: Generate / load global summary ──────────────────
        global_summary = self._get_global_summary(segments)
        self.latest_global_summary = global_summary
        print(f"  > Global summary ready ({len(global_summary)} chars)")

        print(f"  > Classifying with visual direction + context window (workers={max_workers})...")

        decisions = []

        # Multi-threaded — pass all_segments for context window
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_seg = {
                executor.submit(
                    self._classify_single_segment, seg, idx, segments, global_summary
                ): (seg, idx)
                for idx, seg in enumerate(segments)
            }

            completed = 0
            for future in as_completed(future_to_seg):
                seg, idx = future_to_seg[future]
                try:
                    result = future.result()
                    decisions.append(result)
                    completed += 1

                    if result["enhancement_type"] != "none":
                        visual_desc = result.get("visual_description", "N/A")
                        print(
                            f"    [{completed}/{len(segments)}] "
                            f"{result['enhancement_type']}: "
                            f"{seg['text'][:30]}... "
                            f"(visual: {visual_desc[:50]})"
                        )
                except Exception as e:
                    print(f"    ✗ Segment {idx} failed: {e}")
                    decisions.append({**seg, "enhancement_type": "none", "reason": "error"})

        # Sort by time
        decisions = sorted(decisions, key=lambda x: x["start"])

        # Post-processing: rhythm enforcement + density control
        decisions = self._enforce_rhythm(decisions)
        decisions = self._sparsify_decisions(decisions)
        decisions = self._densify_decisions(decisions)

        # Save
        save_decisions(decisions, self.decisions_path)

        # Stats
        svg_count = sum(1 for d in decisions if d["enhancement_type"] == "svg")
        text_count = sum(1 for d in decisions if d["enhancement_type"] == "text")
        none_count = len(decisions) - svg_count - text_count

        print(f"\n  ✓ Classification complete:")
        print(f"    SVG: {svg_count}, Text: {text_count}, None: {none_count}")
        print(f"    Enhancement rate: {(svg_count + text_count) / max(len(decisions), 1) * 100:.0f}%")

        return decisions

    # ================================================================
    #  Global Summary (cached)
    # ================================================================

    def _get_global_summary(self, segments: List[Dict]) -> str:
        """Generate or load a cached global summary of all subtitles."""
        # Check cache
        if os.path.exists(self.summary_path):
            with open(self.summary_path, "r", encoding="utf-8") as f:
                summary = f.read().strip()
            if summary:
                print(f"  > Loading cached global summary from {self.summary_path}")
                return summary

        # Generate via LLM
        print(f"  > Generating global summary for {len(segments)} segments...")
        full_text = "\n".join(seg["text"] for seg in segments)

        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "svg_agent"))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = CustomChatModel(llm_type=self.llm_type, temperature=0.2)

            system_prompt = """You are a content analyst. Given a full transcript of a video, produce a concise summary that captures:

1. **Main Topic**: What is this video about? (1 sentence)
2. **Key Concepts**: List the 5-10 most important concepts/terms discussed.
3. **Structure**: How is the content organized? (e.g., "explains concept A, then compares with B, then demos C")
4. **Visual Opportunities**: What parts of this content would benefit most from diagrams, charts, or infographics?
5. **Domain**: What field is this? (e.g., computer science, biology, business, etc.)

Keep the summary under 300 words. Be specific — mention actual terms and concepts from the transcript."""

            prompt = f"""Here is the full transcript of a video. Summarize it for a visual enhancement system:

{full_text}

Return a structured summary."""

            messages = [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
            result = llm._generate(messages)
            summary = result.generations[0].message.content

        except Exception as e:
            print(f"  > Summary generation failed: {e}, using fallback")
            summary = f"Video transcript with {len(segments)} segments. Content: {full_text[:500]}"

        # Cache to file
        os.makedirs(os.path.dirname(self.summary_path), exist_ok=True)
        with open(self.summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
        print(f"  > Saved global summary to {self.summary_path}")

        return summary

    # ================================================================
    #  Rhythm Control (relaxed)
    # ================================================================

    def _enforce_rhythm(self, decisions: List[Dict]) -> List[Dict]:
        """
        Post-LLM rhythm enforcement (relaxed):
        - No more than 3 consecutive same-type enhancements
        - Min 3s gap only for same-type (svg-svg or text-text)
        - Allow svg+text to be adjacent (they complement each other)
        """
        recent_types = []
        last_svg_end = -999.0
        last_text_end = -999.0

        for i, dec in enumerate(decisions):
            etype = dec["enhancement_type"]

            if etype == "none":
                recent_types = []
                continue

            # Rule 1: No 4+ consecutive same type
            if len(recent_types) >= 3 and all(t == etype for t in recent_types[-3:]):
                original = etype
                if etype == "svg":
                    dec["enhancement_type"] = "text"
                else:
                    dec["enhancement_type"] = "svg"
                dec["reason"] = f"rhythm_override: was {original}, switched to break 4+ streak"
                print(f"    [Rhythm] #{i}: {original} -> {dec['enhancement_type']} (break streak)")

            # Rule 2: Min 3s gap for SAME type only
            seg_start = dec.get("start", 0)
            if etype == "svg" and seg_start - last_svg_end < 3.0:
                if dec.get("confidence", 0.5) < 0.6:
                    dec["enhancement_type"] = "text"
                    dec["reason"] = "rhythm_override: svg too close, downgrade to text"
                    print(f"    [Rhythm] #{i}: svg -> text (gap < 3s)")
            elif etype == "text" and seg_start - last_text_end < 3.0:
                if dec.get("confidence", 0.5) < 0.6:
                    dec["enhancement_type"] = "none"
                    dec["reason"] = "rhythm_override: text too close"
                    print(f"    [Rhythm] #{i}: text -> none (gap < 3s)")

            # Track
            final_type = dec["enhancement_type"]
            if final_type != "none":
                recent_types.append(final_type)
                end_time = dec.get("end", seg_start + 5)
                if final_type == "svg":
                    last_svg_end = end_time
                elif final_type == "text":
                    last_text_end = end_time

        return decisions

    # ================================================================
    #  Single Segment Classification (with context window)
    # ================================================================

    def _classify_single_segment(
        self, segment: Dict, idx: int, all_segments: List[Dict], global_summary: str
    ) -> Dict:
        """
        Classify one segment with:
        - Sliding context window (prev 3 + next 3)
        - Global video summary
        - Imaginative visual director prompt
        """
        text = segment["text"]

        # ── Build context window (prev 3 + next 3) ─────────────────
        prev_texts = []
        for i in range(max(0, idx - 3), idx):
            prev_texts.append(all_segments[i]["text"])
        next_texts = []
        for i in range(idx + 1, min(len(all_segments), idx + 4)):
            next_texts.append(all_segments[i]["text"])

        context_block = ""
        if prev_texts:
            context_block += "[Previous context]:\n"
            for j, pt in enumerate(prev_texts):
                context_block += f"  ({idx - len(prev_texts) + j + 1}) {pt}\n"
        context_block += f"\n[CURRENT TARGET — classify this]:\n  ({idx + 1}) {text}\n"
        if next_texts:
            context_block += "\n[Following context]:\n"
            for j, nt in enumerate(next_texts):
                context_block += f"  ({idx + 2 + j}) {nt}\n"

        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "svg_agent"))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = CustomChatModel(llm_type=self.vision_llm_type, temperature=0.4)

            system_prompt = """You are a selective Visual Director for educational video infographics.

Your mission: Find opportunities to enhance a video using dynamic SVG diagrams or Text cards.
You are reviewing individual subtitle segments, with CONTEXT from surrounding segments and a video summary.

Core Philosophy:
Be selective, but do not under-enhance. Choose enhancements when they add structure, emphasis, or clarity beyond plain subtitles.
Avoid decorative or redundant enhancements, but do not miss clear educational opportunities.

═══ Classification Criteria ═══

1. Assign "svg" (Visual & Structural) if the [CURRENT TARGET], aided by context, describes:
   • Architecture / Structure — systems, layers, modules, networks, nodes
   • Flows / Processes — timelines, steps, pipelines, data transfer, cause→effect
   • Comparisons — A vs B, pros/cons, before/after, tradeoffs
   • Hierarchies — categories, taxonomies, levels, parent-child
   • Cycles — feedback loops, iterative processes, circular dependencies
   • Visual Metaphors — "bottleneck" → funnel, "foundation" → pillars, "bridge" → connector
   
   Requirement: You should be able to describe a layout with at least 3 meaningful interacting visual elements
   or a genuinely clarifying process/structure that subtitles alone do not convey well.
   IMPORTANT: whenever the SVG would explain change over time, movement, process, propagation, orbit, transformation,
   or comparison unfolding step by step, strongly prefer animated_svg over static_svg.

2. Assign "text" (High-Density Information) if the text contains:
   • Key definitions, formulas, or golden rules worth remembering
   • Specific numbers, metrics, or data points
   • Critical warnings or best practices
   • Important terminology the audience should memorize
   Requirement: the card should preserve information viewers are likely to miss without reinforcement.

3. Assign "none" ONLY IF:
   • It is purely conversational filler ("let's move on", "as you can see", "right?")
   • It is too fragmented to extract ANY concrete meaning, even with context
   • It is a greeting, farewell, or pure meta-commentary about the presentation itself
   • It is understandable enough from subtitles alone, even if it is somewhat informative

═══ Important Notes ═══
• Use the [Previous] and [Following] context to understand what pronouns refer to
  (e.g., "it uses three layers" — context tells you "it" = "neural network")
• Use the video summary to understand the overall topic and field
• When in doubt between svg and text, prefer the one that clarifies the idea more
• When in doubt between animated_svg and static_svg, prefer animated_svg if motion itself explains the concept
• When in doubt between text and none, prefer text if the segment contains a clear takeaway, terminology, or memorable claim
• Target a moderate enhancement policy, roughly 28%-40% of segments, not saturation

═══ Output Format (JSON only) ═══
{
  "type": "svg" | "text" | "none",
  "visual_description": "If svg: vividly describe the visual layout with specific elements and their arrangement. If text: what key information to display. If none: 'N/A'",
  "svg_mode_hint": "animated_svg" | "static_svg" | "none",
  "motion_worthiness": 0.0-1.0,
  "motion_grammar_hint": "flow" | "orbit" | "cycle" | "transform" | "compare" | "build" | "signal" | "field" | "none",
  "animation_reason": "If animated_svg, explain what dynamic relationship or process should be shown",
  "information_density": "high" | "medium" | "low",
  "reason": "Brief explanation based on content and context"
}"""

            prompt = f"""Analyze the [CURRENT TARGET] segment. Use context to understand its full meaning.

═══ Video Summary ═══
{global_summary}

═══ Subtitle Context ═══
{context_block}

Think like a visual designer: What is the best way to enhance the [CURRENT TARGET]?
Consider visual metaphors, structural relationships, and information density.

Return JSON only."""

            messages = [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
            result = llm._generate(messages)
            content = result.generations[0].message.content

            parsed = llm.parse_json_response(content)

            # Confidence based on density + type
            density = parsed.get("information_density", "low")
            conf = {"high": 0.86, "medium": 0.66, "low": 0.36}.get(density, 0.5)

            decision = {
                **segment,
                "enhancement_type": parsed.get("type", "none"),
                "visual_description": parsed.get("visual_description", "N/A"),
                "information_density": density,
                "reason": parsed.get("reason", "llm_classified"),
                "confidence": conf,
            }
            return self._augment_motion_fields(decision, parsed)

        except Exception as e:
            print(f"      LLM classification failed: {e}")
            return self._augment_motion_fields(simple_classify_segment(segment), {})

    def _sparsify_decisions(self, decisions: List[Dict]) -> List[Dict]:
        """Prune low-value enhancements to keep density reasonable."""
        enhanced = [d for d in decisions if d["enhancement_type"] != "none"]
        if not decisions:
            return decisions

        target_rate = 0.55
        current_rate = len(enhanced) / len(decisions)
        if current_rate <= target_rate:
            return decisions

        print(f"  > Sparsifying decisions: rate {current_rate:.2f} -> target {target_rate:.2f}")
        protected_keywords = (
            "definition", "means", "called", "important", "key", "warning",
            "process", "mechanism", "system", "architecture", "because", "therefore",
        )
        removable = []
        for idx, dec in enumerate(decisions):
            if dec["enhancement_type"] == "none":
                continue
            text_lower = dec.get("text", "").lower()
            protected = any(keyword in text_lower for keyword in protected_keywords)
            score = dec.get("confidence", 0.5)
            if dec["enhancement_type"] == "svg":
                score += 0.03
            if protected:
                score += 0.12
            removable.append((score, idx))

        removable.sort(key=lambda item: item[0])
        target_keep = int(len(decisions) * target_rate)
        to_remove = max(0, len(enhanced) - target_keep)
        removed = 0
        for _, idx in removable:
            if removed >= to_remove:
                break
            decisions[idx]["enhancement_type"] = "none"
            decisions[idx]["reason"] = "sparsify_override: low incremental value"
            removed += 1

        print(f"  > Sparsify removed {removed} low-value enhancements")
        return decisions

    def _densify_decisions(self, decisions: List[Dict]) -> List[Dict]:
        """Backfill useful enhancements if the pipeline becomes too sparse."""
        if not decisions:
            return decisions

        target_min_rate = 0.33
        enhanced_count = sum(1 for d in decisions if d["enhancement_type"] != "none")
        current_rate = enhanced_count / len(decisions)
        if current_rate >= target_min_rate:
            return decisions

        print(f"  > Densifying decisions: rate {current_rate:.2f} -> target {target_min_rate:.2f}")
        target_keep = int(round(len(decisions) * target_min_rate))
        needed = max(0, target_keep - enhanced_count)
        if needed == 0:
            return decisions

        candidates = []
        for idx, dec in enumerate(decisions):
            if dec["enhancement_type"] != "none":
                continue
            promoted_type, score = self._score_none_segment_for_backfill(dec)
            if promoted_type == "none" or score < 0.62:
                continue
            candidates.append((score, idx, promoted_type))

        candidates.sort(reverse=True)
        promoted = 0
        for score, idx, promoted_type in candidates:
            if promoted >= needed:
                break
            decisions[idx]["enhancement_type"] = promoted_type
            decisions[idx]["confidence"] = max(decisions[idx].get("confidence", 0.0), min(score, 0.9))
            decisions[idx]["reason"] = f"densify_override: promoted to {promoted_type}"
            if promoted_type == "svg":
                decisions[idx]["visual_description"] = "Show the structure, comparison, or flow in a clean explanatory diagram."
            else:
                decisions[idx]["visual_description"] = "Highlight the key takeaway in a concise text card."
            promoted += 1

        print(f"  > Densify promoted {promoted} useful segments")
        return decisions

    def _score_none_segment_for_backfill(self, decision: Dict):
        text = decision.get("text", "").lower()
        if not text:
            return "none", 0.0

        svg_markers = [
            "process", "mechanism", "system", "architecture", "pipeline", "workflow",
            "how it works", "because", "therefore", "leads to", "results in",
            "compare", "versus", "layers", "network", "model", "input", "output",
            "step", "first", "then", "finally",
        ]
        text_markers = [
            "means", "called", "is when", "defined", "important", "key", "remember",
            "rule", "principle", "idea", "concept", "term", "goal", "warning",
            "number", "percent", "times", "better", "worse",
        ]
        filler_markers = [
            "you know", "i think", "kind of", "sort of", "podcast", "conversation with",
            "honor", "pleasure", "really", "yeah",
        ]

        if sum(1 for marker in filler_markers if marker in text) >= 2:
            return "none", 0.0

        svg_score = sum(1 for marker in svg_markers if marker in text) * 0.14
        text_score = sum(1 for marker in text_markers if marker in text) * 0.14

        if any(token in text for token in ("%", "percent", " x ", " times", " ratio", "score")):
            text_score += 0.12
        if len(text.split()) >= 16:
            svg_score += 0.08
            text_score += 0.05

        if svg_score >= text_score and svg_score >= 0.62:
            return "svg", svg_score
        if text_score >= 0.62:
            return "text", text_score
        return "none", max(svg_score, text_score)

    def _augment_motion_fields(self, decision: Dict, parsed: Dict) -> Dict:
        """Attach motion-aware routing hints while preserving existing schema."""
        enhancement_type = decision.get("enhancement_type", "none")
        default_mode = "none" if enhancement_type != "svg" else "static_svg"
        svg_mode_hint = str(parsed.get("svg_mode_hint", default_mode)).strip() or default_mode
        motion_grammar_hint = self._normalize_motion_grammar(parsed.get("motion_grammar_hint", "none"))
        animation_reason = str(parsed.get("animation_reason", "")).strip()

        try:
            motion_worthiness = float(parsed.get("motion_worthiness", 0.0))
        except Exception:
            motion_worthiness = 0.0

        heuristic_mode, heuristic_motion_score, heuristic_grammar, heuristic_reason = self._infer_motion_from_text(
            decision.get("text", ""),
            decision.get("visual_description", ""),
            enhancement_type,
        )

        if enhancement_type != "svg":
            svg_mode_hint = "none"
            motion_grammar_hint = "none"
            motion_worthiness = 0.0
            animation_reason = ""
        else:
            if svg_mode_hint not in ("animated_svg", "static_svg"):
                svg_mode_hint = heuristic_mode
            motion_worthiness = max(motion_worthiness, heuristic_motion_score)
            if motion_grammar_hint == "none":
                motion_grammar_hint = heuristic_grammar
            if not animation_reason:
                animation_reason = heuristic_reason
            if motion_worthiness >= 0.56 and motion_grammar_hint != "none":
                svg_mode_hint = "animated_svg"
            elif svg_mode_hint != "animated_svg":
                svg_mode_hint = "static_svg"

        decision["svg_mode_hint"] = svg_mode_hint
        decision["motion_worthiness"] = round(max(0.0, min(1.0, motion_worthiness)), 3)
        decision["motion_grammar_hint"] = motion_grammar_hint
        decision["animation_reason"] = animation_reason
        return decision

    def _normalize_motion_grammar(self, value: str) -> str:
        grammar = str(value or "none").strip().lower().replace("-", "_").replace(" ", "_")
        valid = {"flow", "orbit", "cycle", "transform", "compare", "build", "signal", "field", "none"}
        if grammar not in valid:
            return "none"
        return grammar

    def _infer_motion_from_text(self, text: str, visual_description: str, enhancement_type: str):
        if enhancement_type != "svg":
            return "none", 0.0, "none", ""

        lowered = f"{text} {visual_description}".lower()
        grammar_markers = {
            "orbit": ["orbit", "around", "revolve", "satellite", "moon", "planet", "solar"],
            "flow": ["flow", "pipeline", "input", "output", "through", "step", "stage", "feeds", "passes"],
            "cycle": ["cycle", "loop", "feedback", "iterate", "iteration", "repeats", "circular"],
            "transform": ["transform", "convert", "encode", "decode", "turns into", "becomes", "mapped"],
            "compare": ["vs", "versus", "compare", "comparison", "before", "after", "tradeoff"],
            "build": ["layer", "hierarchy", "build", "stack", "compose", "expand", "grows"],
            "signal": ["signal", "transmit", "propagate", "send", "receive", "activation", "node"],
            "field": ["field", "wave", "diffusion", "spread", "fluid", "force", "particle"],
        }

        best_grammar = "none"
        best_score = 0.0
        for grammar, markers in grammar_markers.items():
            score = sum(1 for marker in markers if marker in lowered)
            if score > best_score:
                best_score = score
                best_grammar = grammar

        motion_score = min(0.9, 0.22 * best_score)
        if any(token in lowered for token in ("first", "then", "finally", "before", "after", "while")):
            motion_score += 0.14
        if any(token in lowered for token in ("cause", "effect", "leads to", "results in", "because")):
            motion_score += 0.12
        motion_score = max(0.0, min(1.0, motion_score))

        if best_grammar == "none" or motion_score < 0.38:
            return "static_svg", motion_score, "none", ""

        grammar_reasons = {
            "orbit": "Use orbital motion to explain a center-periphery or revolving relationship.",
            "flow": "Use directional flow to show how information or states move through stages.",
            "cycle": "Use looping motion to make repeated or feedback behavior explicit.",
            "transform": "Use transformation motion to show state or representation change over time.",
            "compare": "Use staged contrast to reveal differences across parallel entities.",
            "build": "Use progressive build-up to explain layered or hierarchical structure.",
            "signal": "Use signal propagation to show transmission or activation across entities.",
            "field": "Use field-like motion to show distributed dynamics such as waves or diffusion.",
        }
        return "animated_svg", motion_score, best_grammar, grammar_reasons.get(best_grammar, "")
