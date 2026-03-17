"""
Concept Graph Agent
===================

Builds a persistent evolving concept graph from transcript segments using LLM
concept extraction plus lightweight aggregation.
"""

import json
import os
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple


class ConceptGraphAgent:
    """Create a global concept graph with LLM-guided concept extraction."""

    def __init__(self, llm_type: str, output_dir: str, max_workers: int = 1):
        self.llm_type = llm_type
        self.output_dir = output_dir
        self.max_workers = max(1, max_workers)
        self.cache_path = os.path.join(output_dir, "concept_graph.json")
        self.extraction_cache_path = os.path.join(output_dir, "concept_graph_extractions.json")

    def build_graph(
        self,
        segments: List[Dict],
        decisions: List[Dict],
        global_summary: str,
        force: bool = False,
    ) -> Dict:
        if not force and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    print(f"    > Loading cached concept graph from {self.cache_path}")
                    return json.load(f)
            except Exception:
                pass

        candidate_indices = [
            idx for idx, decision in enumerate(decisions)
            if decision.get("enhancement_type") != "none"
        ]
        total = len(candidate_indices)
        print(f"    > Concept graph candidates: {total} (workers={self.max_workers})")
        extraction_cache = {} if force else self._load_extraction_cache()
        completed_indices = {
            int(key) for key in extraction_cache.keys()
            if str(key).isdigit()
        }
        if extraction_cache and completed_indices:
            print(f"    > Partial concept graph cache found: {len(completed_indices)}/{total} complete. Resuming.")

        if not candidate_indices:
            graph = {
                "graph_title": self._build_title(global_summary),
                "nodes": [],
                "edges": [],
                "clusters": [],
                "timeline_updates": [],
                "summary": global_summary[:220],
            }
            self._save_graph(graph)
            return graph

        extraction_results: List[Tuple[int, Dict]] = []
        for idx in candidate_indices:
            cached = extraction_cache.get(str(idx))
            if cached:
                extraction_results.append((idx, cached))

        pending_indices = [idx for idx in candidate_indices if idx not in completed_indices]
        pending_total = len(pending_indices)
        if pending_total == 0:
            print("    > Concept graph extraction cache complete. Aggregating graph...")

        if self.max_workers <= 1:
            for processed, idx in enumerate(pending_indices, start=1):
                extraction = self._extract_segment_concepts(segments, idx, global_summary)
                extraction_results.append((idx, extraction))
                extraction_cache[str(idx)] = extraction
                if processed % 10 == 0 or processed == pending_total:
                    self._save_extraction_cache(extraction_cache)
                    print(f"    > Concept graph progress: {len(extraction_results)}/{total}")
        else:
            completed = 0
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._extract_segment_concepts, segments, idx, global_summary): idx
                    for idx in pending_indices
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    extraction = future.result()
                    extraction_results.append((idx, extraction))
                    extraction_cache[str(idx)] = extraction
                    completed += 1
                    if completed % 10 == 0 or completed == pending_total:
                        self._save_extraction_cache(extraction_cache)
                        print(f"    > Concept graph progress: {len(extraction_results)}/{total}")

        self._save_extraction_cache(extraction_cache)

        graph = self._aggregate_graph(
            segments=segments,
            decisions=decisions,
            global_summary=global_summary,
            extraction_results=sorted(extraction_results, key=lambda item: item[0]),
        )
        self._save_graph(graph)
        print(f"    > Concept graph complete: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
        return graph

    def _extract_segment_concepts(self, segments: List[Dict], idx: int, global_summary: str) -> Dict:
        segment = segments[idx]
        prev_text = segments[idx - 1]["text"] if idx > 0 else ""
        next_text = segments[idx + 1]["text"] if idx + 1 < len(segments) else ""
        current_text = segment.get("text", "")

        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "svg_agent"))
            from custom_chat_model import CustomChatModel
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = CustomChatModel(llm_type=self.llm_type, temperature=0.1)
            system_prompt = """You extract meaningful knowledge graph concepts from educational video transcript segments.

Return JSON only:
{
  "concepts": [
    {"name": "concept phrase", "role": "topic|entity|method|principle|outcome"}
  ],
  "relations": [
    {"source": "concept phrase", "target": "concept phrase", "relation": "short relation label"}
  ]
}

Rules:
- Extract 0 to 3 concepts only from the CURRENT segment.
- Prefer concrete multi-word concepts, technical terms, named ideas, systems, methods, or outcomes.
- Do not output filler words, pronouns, vague adjectives, discourse markers, or generic verbs.
- Bad examples: "like", "good", "they", "really", "thing", "stuff", "people".
- Good examples: "reverse engineering", "latent manifold", "artificial intelligence", "training signal".
- Add 0 to 2 relations only when the CURRENT segment clearly states a relation.
- Keep names short and canonical.
"""
            prompt = f"""Global summary:
{global_summary}

Previous context:
{prev_text}

Current segment:
{current_text}

Next context:
{next_text}

Extract concepts and relations from the CURRENT segment only. Return JSON only."""
            result = llm._generate([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
            parsed = llm.parse_json_response(result.generations[0].message.content)
            return self._normalize_extraction(parsed)
        except Exception:
            return self._heuristic_extraction(current_text)

    def _normalize_extraction(self, parsed: Dict) -> Dict:
        concepts = []
        for item in parsed.get("concepts", [])[:4]:
            raw_name = str(item.get("name", "")).strip()
            name = self._normalize_name(raw_name)
            if not self._is_valid_concept(name):
                continue
            concepts.append({
                "name": name,
                "role": str(item.get("role", "topic")).strip() or "topic",
            })

        concept_names = {item["name"] for item in concepts}
        relations = []
        for item in parsed.get("relations", [])[:3]:
            source = self._normalize_name(str(item.get("source", "")).strip())
            target = self._normalize_name(str(item.get("target", "")).strip())
            relation = self._clean_relation(str(item.get("relation", "")).strip())
            if source == target:
                continue
            if source not in concept_names or target not in concept_names:
                continue
            if not relation:
                continue
            relations.append({
                "source": source,
                "target": target,
                "relation": relation,
            })

        return {"concepts": concepts, "relations": relations}

    def _heuristic_extraction(self, text: str) -> Dict:
        noun_like = re.findall(r"\b[A-Za-z][A-Za-z\-]{4,}\b", text or "")
        concepts = []
        for token in noun_like:
            normalized = self._normalize_name(token)
            if not self._is_valid_concept(normalized):
                continue
            concepts.append({"name": normalized, "role": "topic"})
            if len(concepts) >= 2:
                break
        return {"concepts": concepts, "relations": []}

    def _aggregate_graph(
        self,
        segments: List[Dict],
        decisions: List[Dict],
        global_summary: str,
        extraction_results: List[Tuple[int, Dict]],
    ) -> Dict:
        node_weights = Counter()
        node_roles = defaultdict(Counter)
        node_timestamps = defaultdict(list)
        edge_weights = Counter()
        edge_labels = defaultdict(Counter)
        timeline_updates = []

        for idx, extraction in extraction_results:
            concepts = extraction.get("concepts", [])
            relations = extraction.get("relations", [])
            current_nodes = []

            for concept in concepts:
                name = concept["name"]
                node_weights[name] += 1
                node_roles[name][concept.get("role", "topic")] += 1
                if len(node_timestamps[name]) < 5:
                    node_timestamps[name].append(segments[idx]["start"])
                current_nodes.append(name)

            if current_nodes:
                timeline_updates.append({
                    "timestamp": segments[idx]["start"],
                    "node_ids": current_nodes[:4],
                    "segment_index": idx,
                })

            if relations:
                for relation in relations:
                    source = relation["source"]
                    target = relation["target"]
                    if source not in node_weights or target not in node_weights:
                        continue
                    key = tuple(sorted((source, target)))
                    edge_weights[key] += 1
                    edge_labels[key][relation["relation"]] += 1
            elif len(current_nodes) >= 2:
                for i in range(len(current_nodes) - 1):
                    key = tuple(sorted((current_nodes[i], current_nodes[i + 1])))
                    edge_weights[key] += 1
                    edge_labels[key]["co-mentioned"] += 1

        ranked_nodes = [name for name, _ in node_weights.most_common(10)]
        ranked_node_set = set(ranked_nodes)
        nodes = []
        for name in ranked_nodes:
            nodes.append({
                "id": name,
                "label": self._display_label(name),
                "weight": node_weights[name],
                "role": node_roles[name].most_common(1)[0][0] if node_roles[name] else "topic",
                "timestamps": node_timestamps[name][:4],
            })

        edges = []
        for (source, target), weight in edge_weights.most_common(16):
            if source not in ranked_node_set or target not in ranked_node_set:
                continue
            label = edge_labels[(source, target)].most_common(1)[0][0]
            edges.append({
                "source": source,
                "target": target,
                "weight": weight,
                "label": label,
            })

        filtered_updates = []
        for update in timeline_updates:
            node_ids = [name for name in update["node_ids"] if name in ranked_node_set]
            if not node_ids:
                continue
            filtered_updates.append({
                "timestamp": update["timestamp"],
                "node_ids": node_ids,
                "segment_index": update["segment_index"],
            })

        return {
            "graph_title": self._build_title(global_summary),
            "nodes": nodes,
            "edges": edges,
            "clusters": self._build_clusters(nodes),
            "timeline_updates": filtered_updates,
            "summary": global_summary[:220],
            "metadata": {
                "candidate_segments": sum(1 for d in decisions if d.get("enhancement_type") != "none"),
                "llm_powered": True,
            },
        }

    def _build_clusters(self, nodes: List[Dict]) -> List[Dict]:
        clusters = defaultdict(list)
        role_labels = {
            "topic": "Core Topics",
            "entity": "Entities",
            "method": "Methods",
            "principle": "Principles",
            "outcome": "Outcomes",
        }
        for node in nodes:
            role = node.get("role", "topic")
            clusters[role].append(node["id"])

        items = []
        for idx, (role, node_ids) in enumerate(clusters.items()):
            if not node_ids:
                continue
            items.append({
                "id": f"cluster_{idx}",
                "label": role_labels.get(role, role.title()),
                "node_ids": node_ids,
            })
        return items

    def _build_title(self, summary: str) -> str:
        if not summary:
            return "Global Concept Graph"
        first_line = summary.strip().splitlines()[0].strip()
        if len(first_line) > 60:
            first_line = first_line[:57] + "..."
        return first_line or "Global Concept Graph"

    def _normalize_name(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text.strip().lower())
        text = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", text)
        return text

    def _display_label(self, name: str) -> str:
        return " ".join(word.capitalize() for word in name.split())

    def _clean_relation(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text.strip().lower())
        if len(text) > 36:
            text = text[:33].rstrip() + "..."
        return text

    def _is_valid_concept(self, name: str) -> bool:
        if not name or len(name) < 4:
            return False
        bad_terms = {
            "like", "good", "they", "them", "this", "that", "really", "yeah",
            "maybe", "little", "thing", "things", "stuff", "people", "there",
            "something", "anything", "nothing", "basically", "actually",
        }
        if name in bad_terms:
            return False
        words = name.split()
        if len(words) == 1 and len(words[0]) < 6:
            return False
        if all(word in bad_terms for word in words):
            return False
        return True

    def _save_graph(self, graph: Dict):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)

    def _load_extraction_cache(self) -> Dict:
        if not os.path.exists(self.extraction_cache_path):
            return {}
        try:
            with open(self.extraction_cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_extraction_cache(self, cache: Dict):
        temp_path = self.extraction_cache_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.extraction_cache_path)
