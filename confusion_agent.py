"""
Confusion Agent
===============

Detects segments that are likely to produce misconceptions and turns them into
correction-oriented enhancement payloads.
"""

import json
import os
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed


class ConfusionAgent:
    """Detect misconception-prone segments."""

    def __init__(self, llm_type: str, output_dir: str, max_workers: int = 1):
        self.llm_type = llm_type
        self.output_dir = output_dir
        self.max_workers = max(1, max_workers)
        self.cache_path = os.path.join(output_dir, "confusion_analysis.json")
        self.hit_threshold = 0.74

    def analyze_segments(
        self,
        segments: List[Dict],
        decisions: List[Dict],
        global_summary: str,
        force: bool = False,
    ) -> List[Dict]:
        if not force and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                print(f"    > Loading cached misconception analysis from {self.cache_path}")
                return self._merge_payloads(decisions, cached)
            except Exception:
                pass

        candidates = [idx for idx, decision in enumerate(decisions) if decision.get("enhancement_type") != "none"]
        total = len(candidates)
        hits = 0
        payloads = {}
        print(f"    > Misconception candidates: {total} (workers={self.max_workers})")

        if self.max_workers <= 1:
            for processed, idx in enumerate(candidates, start=1):
                payload = self._analyze_single_segment(segments[idx], idx, segments, global_summary)
                if payload.get("confusion_risk", 0.0) >= self.hit_threshold:
                    payloads[str(idx)] = payload
                    decisions[idx]["enhancement_type"] = "misconception"
                    decisions[idx]["misconception_payload"] = payload
                    decisions[idx]["confusion_risk"] = payload["confusion_risk"]
                    decisions[idx]["reason"] = f"{decisions[idx].get('reason', 'classified')} + misconception"
                    hits += 1
                    print(f"    > Misconception hit #{hits}: segment {idx + 1}, risk={payload['confusion_risk']:.2f}")
                if processed % 10 == 0 or processed == total:
                    self._save_checkpoint(payloads)
                    print(f"    > Misconception progress: {processed}/{total}, hits={hits}")
        else:
            completed = 0
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._analyze_single_segment, segments[idx], idx, segments, global_summary): idx
                    for idx in candidates
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    payload = future.result()
                    completed += 1
                    if payload.get("confusion_risk", 0.0) >= self.hit_threshold:
                        payloads[str(idx)] = payload
                        decisions[idx]["enhancement_type"] = "misconception"
                        decisions[idx]["misconception_payload"] = payload
                        decisions[idx]["confusion_risk"] = payload["confusion_risk"]
                        decisions[idx]["reason"] = f"{decisions[idx].get('reason', 'classified')} + misconception"
                        hits += 1
                        print(f"    > Misconception hit #{hits}: segment {idx + 1}, risk={payload['confusion_risk']:.2f}")
                    if completed % 10 == 0 or completed == total:
                        self._save_checkpoint(payloads)
                        print(f"    > Misconception progress: {completed}/{total}, hits={hits}")

        self._save_checkpoint(payloads)

        print(f"    > Misconception analysis complete: {hits} hits")
        return decisions

    def _merge_payloads(self, decisions: List[Dict], payloads: Dict) -> List[Dict]:
        for idx, decision in enumerate(decisions):
            payload = payloads.get(str(idx))
            if not payload:
                continue
            decision["enhancement_type"] = "misconception"
            decision["misconception_payload"] = payload
            decision["confusion_risk"] = payload.get("confusion_risk", 0.75)
        return decisions

    def _analyze_single_segment(
        self,
        segment: Dict,
        idx: int,
        all_segments: List[Dict],
        global_summary: str,
    ) -> Dict:
        prev_text = all_segments[idx - 1]["text"] if idx > 0 else ""
        next_text = all_segments[idx + 1]["text"] if idx + 1 < len(all_segments) else ""
        text = segment.get("text", "")

        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "svg_agent"))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = CustomChatModel(llm_type=self.llm_type, temperature=0.2)
            system_prompt = """You detect misunderstanding-prone educational segments that deserve correction-oriented overlays.

Return JSON:
{
  "confusion_risk": 0.0-1.0,
  "likely_misconception": "One common wrong understanding",
  "correct_understanding": "The corrected interpretation",
  "why_confusing": "Why this segment may mislead viewers",
  "display_label": "[ ⚠ Misconception Alert ]"
}

Be selective, but not extreme. Many segments should still score below 0.65.
Assign >= 0.74 when the CURRENT segment is meaningfully prone to misunderstanding and a correction card would genuinely help.
Assign >= 0.85 only for very strong misconception risk.

Elevate the score when at least two of these are true:
- uses abstract terminology without grounding
- compresses a causal chain into one sentence
- states an oversimplification that needs caveat
- uses pronouns or implicit references heavily
- sounds like a conclusion without the assumptions
- sounds more certain than the evidence presented nearby
- could easily be over-generalized by a viewer

Do NOT mark high risk just because the content is difficult or technical.
Do mark moderate-to-high risk when the segment is understandable at a surface level but likely to leave a subtly wrong mental model.
"""
            prompt = f"""Global summary:
{global_summary}

Previous: {prev_text}
Current: {text}
Next: {next_text}

Analyze whether the CURRENT segment is likely to cause misunderstanding. Return JSON only."""
            result = llm._generate([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
            parsed = llm.parse_json_response(result.generations[0].message.content)
            risk = float(parsed.get("confusion_risk", 0.0))
            return {
                "confusion_risk": max(0.0, min(1.0, risk)),
                "likely_misconception": parsed.get("likely_misconception", ""),
                "correct_understanding": parsed.get("correct_understanding", ""),
                "why_confusing": parsed.get("why_confusing", ""),
                "display_label": parsed.get("display_label", "[ ⚠ Misconception Alert ]"),
            }
        except Exception:
            return self._heuristic_payload(text, prev_text, next_text)

    def _heuristic_payload(self, text: str, prev_text: str, next_text: str) -> Dict:
        lowered = text.lower()
        abstract_markers = [
            "basically", "sort of", "kind of", "actually", "essentially",
            "in some sense", "manifold", "emergence", "representation",
            "latent", "distribution", "intelligence", "alignment", "reasoning",
        ]
        reference_markers = ["this", "that", "it", "these", "those", "they"]
        caveat_markers = ["but", "however", "except", "although", "not exactly"]

        risk = 0.18
        if any(token in lowered for token in abstract_markers):
            risk += 0.20
        if sum(1 for token in reference_markers if f" {token} " in f" {lowered} ") >= 2:
            risk += 0.18
        if any(token in lowered for token in caveat_markers):
            risk += 0.18
        if len(text.split()) > 24:
            risk += 0.10
        if any(token in lowered for token in ("basically", "just", "simply", "kind of", "sort of")):
            risk += 0.12
        if any(token in lowered for token in ("all", "always", "never", "everything", "nothing")):
            risk += 0.10
        if '"' in text or "'" in text:
            risk -= 0.05

        support = prev_text or next_text or text
        return {
            "confusion_risk": min(risk, 0.95),
            "likely_misconception": f"Viewers may flatten this into a simpler claim: {text[:80]}",
            "correct_understanding": support[:140],
            "why_confusing": "The segment is abstract, compressed, or reference-heavy and may hide important caveats.",
            "display_label": "[ ⚠ Misconception Alert ]",
        }

    def _save_checkpoint(self, payloads: Dict):
        temp_path = self.cache_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payloads, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.cache_path)
