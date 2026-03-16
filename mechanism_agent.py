"""
Mechanism Agent
===============

Builds stage-based mechanism chains for process-heavy segments.
"""

import json
import os
import re
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed


class MechanismAgent:
    """Extract stage chains from process-like segments."""

    def __init__(self, llm_type: str, output_dir: str, max_workers: int = 1):
        self.llm_type = llm_type
        self.output_dir = output_dir
        self.max_workers = max(1, max_workers)
        self.cache_path = os.path.join(output_dir, "mechanism_chains.json")

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
                print(f"    > Loading cached mechanism chains from {self.cache_path}")
                return self._merge_payloads(decisions, cached)
            except Exception:
                pass

        candidates = [
            idx for idx, decision in enumerate(decisions)
            if decision.get("enhancement_type") in ("svg", "text")
            and self._looks_like_mechanism_candidate(segments, idx)
        ]
        total = len(candidates)
        hits = 0
        payloads = {}
        print(f"    > Mechanism candidates: {total} (workers={self.max_workers})")
        if self.max_workers <= 1:
            for processed, idx in enumerate(candidates, start=1):
                payload = self._analyze_single_segment(segments, idx, global_summary)
                if payload.get("is_mechanism"):
                    payloads[str(idx)] = payload
                    decisions[idx]["enhancement_type"] = "mechanism_chain"
                    decisions[idx]["mechanism_payload"] = payload
                    decisions[idx]["visual_description"] = payload.get("visual_hint", decisions[idx].get("visual_description", ""))
                    decisions[idx]["reason"] = f"{decisions[idx].get('reason', 'classified')} + mechanism_chain"
                    hits += 1
                    print(f"    > Mechanism hit #{hits}: segment {idx + 1}, stages={len(payload.get('stages', []))}")
                if processed % 10 == 0 or processed == total:
                    self._save_checkpoint(payloads)
                    print(f"    > Mechanism progress: {processed}/{total}, hits={hits}")
        else:
            completed = 0
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._analyze_single_segment, segments, idx, global_summary): idx
                    for idx in candidates
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    payload = future.result()
                    completed += 1
                    if payload.get("is_mechanism"):
                        payloads[str(idx)] = payload
                        decisions[idx]["enhancement_type"] = "mechanism_chain"
                        decisions[idx]["mechanism_payload"] = payload
                        decisions[idx]["visual_description"] = payload.get("visual_hint", decisions[idx].get("visual_description", ""))
                        decisions[idx]["reason"] = f"{decisions[idx].get('reason', 'classified')} + mechanism_chain"
                        hits += 1
                        print(f"    > Mechanism hit #{hits}: segment {idx + 1}, stages={len(payload.get('stages', []))}")
                    if completed % 10 == 0 or completed == total:
                        self._save_checkpoint(payloads)
                        print(f"    > Mechanism progress: {completed}/{total}, hits={hits}")

        self._save_checkpoint(payloads)

        print(f"    > Mechanism analysis complete: {hits} hits")
        return decisions

    def _merge_payloads(self, decisions: List[Dict], payloads: Dict) -> List[Dict]:
        for idx, decision in enumerate(decisions):
            payload = payloads.get(str(idx))
            if not payload:
                continue
            decision["enhancement_type"] = "mechanism_chain"
            decision["mechanism_payload"] = payload
        return decisions

    def _analyze_single_segment(self, segments: List[Dict], idx: int, global_summary: str) -> Dict:
        segment = segments[idx]
        context = []
        for j in range(max(0, idx - 1), min(len(segments), idx + 2)):
            context.append(segments[j]["text"])
        combined = " ".join(context)

        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "svg_agent"))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = CustomChatModel(llm_type=self.llm_type, temperature=0.2)
            system_prompt = """You convert explanatory transcript segments into mechanism chains.

Return JSON:
{
  "is_mechanism": true/false,
  "chain_title": "Short title",
  "stages": ["Stage 1", "Stage 2", "Stage 3"],
  "links": ["why 1 leads to 2", "why 2 leads to 3"],
  "current_focus_stage": 0,
  "visual_hint": "Short visual direction"
}

Be selective, but not overly strict.
Use true if the content clearly describes a real process, transformation, causal chain, pipeline, or system flow with 2 to 4 coherent stages.

Reject interview chatter, opinions, scene-setting, praise, vague predictions, analogies without steps, and general discussion.
Only accept if the segment itself contains operational progression such as:
- input -> transformation -> output
- cause -> mechanism -> effect
- step 1 -> step 2
- system component A passes something to B, then B changes it, then C produces a result

Prefer stages that are concrete and action-bearing, but concise abstract stages are acceptable if they clearly describe progression.
"""
            prompt = f"""Global summary:
{global_summary[:1200]}

Target context:
{combined}

Extract a mechanism chain if present. Return JSON only."""
            result = llm._generate([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
            parsed = llm.parse_json_response(result.generations[0].message.content)
            stages = [self._normalize_stage_text(s) for s in parsed.get("stages", []) if str(s).strip()]
            stages = [stage for stage in stages if self._is_specific_stage(stage)]
            if parsed.get("is_mechanism") and self._is_valid_llm_payload(stages, combined):
                links = parsed.get("links", [])
                return {
                    "is_mechanism": True,
                    "chain_title": parsed.get("chain_title", "Mechanism Chain"),
                    "stages": stages[:4],
                    "links": links[: max(0, len(stages) - 1)],
                    "current_focus_stage": min(max(int(parsed.get("current_focus_stage", 0)), 0), len(stages) - 1),
                    "visual_hint": parsed.get("visual_hint", "Sequential mechanism chain"),
                }
        except Exception:
            pass

        return self._heuristic_payload(segment.get("text", ""), combined)

    def _heuristic_payload(self, text: str, combined: str) -> Dict:
        lowered = combined.lower()
        process_markers = [
            "first", "then", "finally", "step", "process", "mechanism",
            "pipeline", "flow", "works", "happens", "causes", "leads to",
            "sends", "returns", "transforms", "moves through", "input", "output",
            "feeds into", "results in", "converts", "produces",
        ]
        marker_hits = sum(1 for marker in process_markers if marker in lowered)
        if marker_hits < 1:
            return {"is_mechanism": False}
        if self._is_conversational_chatter(lowered):
            return {"is_mechanism": False}

        parts = [p.strip(" .") for p in combined.replace("Then", "then").replace("Finally", "finally").split(".") if p.strip()]
        stages = []
        for part in parts:
            stage = self._normalize_stage_text(part)
            if not self._is_specific_stage(stage):
                continue
            stages.append(stage)
            if len(stages) >= 4:
                break

        if len(stages) < 2:
            return {"is_mechanism": False}

        links = [f"{stages[i]} -> {stages[i + 1]}" for i in range(len(stages) - 1)]
        return {
            "is_mechanism": True,
            "chain_title": text[:48] or "Mechanism Chain",
            "stages": stages,
            "links": links,
            "current_focus_stage": min(1, len(stages) - 1),
            "visual_hint": "Wide horizontal mechanism chain",
        }

    def _looks_like_mechanism_candidate(self, segments: List[Dict], idx: int) -> bool:
        context = []
        for j in range(max(0, idx - 1), min(len(segments), idx + 2)):
            context.append(segments[j].get("text", ""))
        combined = " ".join(context).lower()
        process_markers = [
            "first", "then", "finally", "step", "process", "pipeline", "workflow",
            "flow", "mechanism", "causes", "leads to", "results in", "input",
            "output", "transforms", "converts", "feeds into", "passes through",
            "system", "model", "network", "signal", "stage",
        ]
        marker_hits = sum(1 for marker in process_markers if marker in combined)
        if marker_hits < 1:
            return False
        if self._is_conversational_chatter(combined):
            return False
        return True

    def _is_conversational_chatter(self, lowered: str) -> bool:
        chatter_markers = [
            "i think", "you know", "kind of", "sort of", "in a way", "it's like",
            "that's maybe", "i mean", "one of the", "fascinating", "brilliant",
            "honor", "pleasure", "podcast", "conversation with", "what's interesting",
        ]
        return sum(1 for marker in chatter_markers if marker in lowered) >= 3

    def _normalize_stage_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", str(text).strip(" .:-"))
        words = text.split()
        if len(words) > 8:
            text = " ".join(words[:8])
        return text

    def _is_specific_stage(self, stage: str) -> bool:
        lowered = stage.lower()
        generic_phrases = {
            "this is important", "it works", "something happens", "that's the idea",
            "people talk about", "it is interesting", "the conversation continues",
        }
        if len(stage.split()) < 2:
            return False
        if lowered in generic_phrases:
            return False
        if self._is_conversational_chatter(lowered):
            return False
        action_markers = [
            "input", "output", "transform", "convert", "produce", "process",
            "send", "pass", "map", "encode", "decode", "predict", "update",
            "train", "retrieve", "store", "cause", "lead", "flow", "stage",
        ]
        if any(marker in lowered for marker in action_markers):
            return True
        abstract_progress_markers = [
            "problem", "constraint", "tradeoff", "decision", "approach",
            "bottleneck", "handoff", "review", "feedback", "iteration",
        ]
        return any(marker in lowered for marker in abstract_progress_markers)

    def _is_valid_llm_payload(self, stages: List[str], combined: str) -> bool:
        if len(stages) < 2:
            return False
        if len(set(stage.lower() for stage in stages)) < 2:
            return False
        specific_count = sum(1 for stage in stages if self._is_specific_stage(stage))
        if specific_count < 2:
            return False
        if self._is_conversational_chatter(combined.lower()):
            return False
        return True

    def _save_checkpoint(self, payloads: Dict):
        temp_path = self.cache_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payloads, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.cache_path)
