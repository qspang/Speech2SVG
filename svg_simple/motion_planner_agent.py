"""
Motion Planner Agent
====================

Normalizes a visual strategy brief into a stable motion plan that the
animated SVG composer can execute deterministically.
"""

from typing import Any, Dict, List


VALID_MOTION_GRAMMARS = {"flow", "orbit", "cycle", "transform", "compare", "build", "signal", "field", "none"}


class MotionPlannerAgent:
    """Convert motion-aware design brief fields into a normalized motion plan."""

    def normalize_plan(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        svg_mode = str(brief.get("svg_mode", "static")).strip()
        motion_grammar = str(brief.get("motion_grammar", "none")).strip().lower()
        if motion_grammar not in VALID_MOTION_GRAMMARS:
            motion_grammar = "none"

        motion_entities = self._normalize_entities(
            brief.get("motion_entities") or brief.get("entities") or []
        )
        animation_beats = self._normalize_beats(
            brief.get("animation_beats") or [],
            motion_entities,
            motion_grammar,
        )

        if svg_mode != "animated_explanatory" or motion_grammar == "none":
            svg_mode = "static"

        if svg_mode == "animated_explanatory" and not motion_entities:
            motion_entities = self._fallback_entities(brief)
        if svg_mode == "animated_explanatory" and not animation_beats:
            animation_beats = self._fallback_beats(motion_grammar, motion_entities)

        return {
            "svg_mode": svg_mode,
            "motion_grammar": motion_grammar,
            "motion_entities": motion_entities,
            "animation_beats": animation_beats,
            "temporal_focus": brief.get("temporal_focus", "clarify the main relation over time"),
        }

    def _normalize_entities(self, items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        entities = []
        for idx, item in enumerate(items[:6]):
            if isinstance(item, str):
                label = item.strip()
                role = "stage"
                entity_id = f"entity_{idx}"
            else:
                label = str(item.get("label") or item.get("name") or item.get("id") or "").strip()
                role = str(item.get("role", "stage")).strip() or "stage"
                entity_id = str(item.get("id", f"entity_{idx}")).strip() or f"entity_{idx}"
            if not label:
                continue
            entities.append({
                "id": entity_id.lower().replace(" ", "_"),
                "label": label[:36],
                "role": role,
            })
        return entities

    def _normalize_beats(self, beats: List[Dict[str, Any]], entities: List[Dict[str, str]], motion_grammar: str) -> List[Dict[str, Any]]:
        normalized = []
        for idx, beat in enumerate(beats[:5]):
            if isinstance(beat, str):
                normalized.append({"t": round(idx * 0.9, 1), "action": beat[:40], "target": entities[min(idx, len(entities) - 1)]["id"] if entities else ""})
                continue
            try:
                t = float(beat.get("t", idx * 0.9))
            except Exception:
                t = idx * 0.9
            normalized.append({
                "t": round(max(0.0, t), 1),
                "action": str(beat.get("action", "reveal")).strip()[:40],
                "target": str(beat.get("target", entities[min(idx, len(entities) - 1)]["id"] if entities else "")).strip(),
            })
        if normalized:
            return normalized
        return self._fallback_beats(motion_grammar, entities)

    def _fallback_entities(self, brief: Dict[str, Any]) -> List[Dict[str, str]]:
        labels = []
        for item in brief.get("entities", [])[:4]:
            if isinstance(item, dict):
                label = str(item.get("label", "")).strip()
            else:
                label = str(item).strip()
            if label:
                labels.append(label)
        if not labels:
            labels = [brief.get("display_title", "Concept")[:24]]
        return [
            {"id": f"entity_{idx}", "label": label, "role": "stage" if idx else "anchor"}
            for idx, label in enumerate(labels[:4])
        ]

    def _fallback_beats(self, motion_grammar: str, entities: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        if not entities:
            return []
        first = entities[0]["id"]
        second = entities[min(1, len(entities) - 1)]["id"]
        third = entities[min(2, len(entities) - 1)]["id"]
        templates = {
            "flow": [
                {"t": 0.0, "action": "reveal_source", "target": first},
                {"t": 0.8, "action": "flow_forward", "target": second},
                {"t": 1.6, "action": "emit_result", "target": third},
            ],
            "orbit": [
                {"t": 0.0, "action": "reveal_anchor", "target": first},
                {"t": 0.8, "action": "start_primary_orbit", "target": second},
                {"t": 1.6, "action": "start_secondary_orbit", "target": third},
            ],
            "cycle": [
                {"t": 0.0, "action": "reveal_cycle", "target": first},
                {"t": 0.9, "action": "propagate_loop", "target": second},
                {"t": 1.8, "action": "close_feedback", "target": third},
            ],
            "transform": [
                {"t": 0.0, "action": "reveal_initial_state", "target": first},
                {"t": 1.0, "action": "transition_state", "target": second},
                {"t": 2.0, "action": "show_final_state", "target": third},
            ],
            "compare": [
                {"t": 0.0, "action": "reveal_left_case", "target": first},
                {"t": 0.8, "action": "reveal_right_case", "target": second},
                {"t": 1.6, "action": "highlight_gap", "target": third},
            ],
            "build": [
                {"t": 0.0, "action": "reveal_foundation", "target": first},
                {"t": 0.8, "action": "stack_layer", "target": second},
                {"t": 1.6, "action": "complete_structure", "target": third},
            ],
            "signal": [
                {"t": 0.0, "action": "activate_source", "target": first},
                {"t": 0.8, "action": "transmit_signal", "target": second},
                {"t": 1.6, "action": "activate_target", "target": third},
            ],
            "field": [
                {"t": 0.0, "action": "reveal_field", "target": first},
                {"t": 0.8, "action": "expand_field", "target": second},
                {"t": 1.6, "action": "settle_field", "target": third},
            ],
        }
        return templates.get(motion_grammar, [])
