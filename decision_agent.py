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

        # Post-processing: rhythm enforcement (relaxed)
        decisions = self._enforce_rhythm(decisions)

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

{full_text[:8000]}

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

            system_prompt = """You are an imaginative Visual Director for educational video infographics.

Your mission: Find opportunities to enhance a video using dynamic SVG diagrams or Text cards.
You are reviewing individual subtitle segments, with CONTEXT from surrounding segments and a video summary.

Core Philosophy:
Don't just look for literal objects. Look for relationships, flows, structures, and abstract concepts
that can be mapped to VISUAL METAPHORS. Think like a designer — if you can sketch it, it's worth an SVG.

═══ Classification Criteria ═══

1. Assign "svg" (Visual & Structural) if the [CURRENT TARGET], aided by context, describes:
   • Architecture / Structure — systems, layers, modules, networks, nodes
   • Flows / Processes — timelines, steps, pipelines, data transfer, cause→effect
   • Comparisons — A vs B, pros/cons, before/after, tradeoffs
   • Hierarchies — categories, taxonomies, levels, parent-child
   • Cycles — feedback loops, iterative processes, circular dependencies
   • Visual Metaphors — "bottleneck" → funnel, "foundation" → pillars, "bridge" → connector
   
   Requirement: You should be able to describe a layout with at least 2 interacting visual elements.

2. Assign "text" (High-Density Information) if the text contains:
   • Key definitions, formulas, or golden rules worth remembering
   • Specific numbers, metrics, or data points
   • Critical warnings or best practices
   • Important terminology the audience should memorize

3. Assign "none" ONLY IF:
   • It is purely conversational filler ("let's move on", "as you can see", "right?")
   • It is too fragmented to extract ANY concrete meaning, even with context
   • It is a greeting, farewell, or pure meta-commentary about the presentation itself

═══ Important Notes ═══
• Use the [Previous] and [Following] context to understand what pronouns refer to
  (e.g., "it uses three layers" — context tells you "it" = "neural network")
• Use the video summary to understand the overall topic and field
• When in doubt between svg and text, prefer svg — visual explanations are more engaging
• When in doubt between text and none, prefer text — information reinforcement helps learning

═══ Output Format (JSON only) ═══
{
  "type": "svg" | "text" | "none",
  "visual_description": "If svg: vividly describe the visual layout with specific elements and their arrangement. If text: what key information to display. If none: 'N/A'",
  "information_density": "high" | "medium" | "low",
  "reason": "Brief explanation based on content and context"
}"""

            prompt = f"""Analyze the [CURRENT TARGET] segment. Use context to understand its full meaning.

═══ Video Summary ═══
{global_summary[:1500]}

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
            conf = {"high": 0.85, "medium": 0.65, "low": 0.4}.get(density, 0.5)

            return {
                **segment,
                "enhancement_type": parsed.get("type", "none"),
                "visual_description": parsed.get("visual_description", "N/A"),
                "information_density": density,
                "reason": parsed.get("reason", "llm_classified"),
                "confidence": conf,
            }

        except Exception as e:
            print(f"      LLM classification failed: {e}")
            return simple_classify_segment(segment)
