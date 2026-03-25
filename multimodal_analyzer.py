"""
Multimodal Analyzer
===================

视频多模态分析器：Phase 1-6主流程协调
"""

import os
import numpy as np
from typing import List, Dict, Any, Optional
from copy import deepcopy

# 导入工具函数
from multimodal_utils import (
    create_fallback_transcript,
    save_transcript, load_transcript,
    save_segments, load_segments, save_decisions
)

# 导入各Agent
from layout_agent import LayoutProcessor
from decision_agent import DecisionAgent
from scene_agent import SceneAgent
from content_agent import ContentAgent
from concept_graph_agent import ConceptGraphAgent


class MultimodalAnalyzer:
    """多模态视频分析器 - 主流程协调器"""
    
    def __init__(
        self,
        video_path: str = None,
        output_dir: str = None,
        llm_type: str = None,
        vision_llm_type: str = None,
        svg_mode: str = "simple",
        max_workers: int = 1,
        layout_max_workers: int = 1,
        scene_max_workers: int = 1,
        enable_print_layout: bool = False,
        enable_print_scene: bool = False,
        enable_concept_graph: bool = False,
    ):
        """初始化分析器"""
        self.video_path = video_path
        self.output_dir = output_dir 
        os.makedirs(self.output_dir, exist_ok=True)
        
        # LLM配置
        self.llm_type = llm_type or "claude-sonnet-4-5-20250929"
        self.vision_llm_type = vision_llm_type or "claude-sonnet-4-5-20250929"
        self.svg_mode = svg_mode
        self.max_workers = max(1, max_workers)
        self.layout_max_workers = max(1, layout_max_workers)
        self.scene_max_workers = max(1, scene_max_workers)
        self.enable_print_layout = enable_print_layout
        self.enable_print_scene = enable_print_scene
        self.enable_concept_graph = enable_concept_graph
        
        # 文件路径
        self.whisper_transcript_path = os.path.join(self.output_dir, "whisper_transcript.txt")
        self.semantic_segments_path = os.path.join(self.output_dir, "semantic_segments.txt")
        
        # 初始化各Agent
        self.layout_agent = LayoutProcessor(
            video_path,
            max_workers=self.layout_max_workers,
            vision_llm_type=self.vision_llm_type,
            enable_print_layout=self.enable_print_layout,
        ) if video_path else None
        self.decision_agent = DecisionAgent(self.llm_type, self.vision_llm_type, self.output_dir)
        self.scene_agent = SceneAgent(
            video_path,
            self.output_dir,
            self.llm_type,
            max_workers=self.scene_max_workers,
            enable_print_scene=self.enable_print_scene,
        ) if video_path else None
        self.concept_graph_agent = ConceptGraphAgent(
            self.llm_type,
            self.output_dir,
            max_workers=self.max_workers
        )
        self.content_agent = ContentAgent(
            self.llm_type, 
            self.vision_llm_type, 
            self.output_dir,
            svg_mode=self.svg_mode,
            max_workers=self.max_workers
        )
        self.global_concept_graph = {}
        self.global_summary = ""
        
        print(f"✓ MultimodalAnalyzer initialized")
        print(f"  Output dir: {self.output_dir}")
        print(f"  SVG mode: {self.svg_mode.capitalize()}")

    def _apply_feature_flags_to_decisions(
        self,
        decisions: List[Dict[str, Any]],
        persist: bool = False
    ) -> List[Dict[str, Any]]:
        """Normalize decisions to the current simplified pipeline: svg + text only."""
        sanitized = []
        changed = 0

        for decision in decisions or []:
            dec = deepcopy(decision)
            etype = dec.get("enhancement_type", "none")

            if etype == "misconception":
                dec["enhancement_type"] = "text"
                dec.pop("misconception_payload", None)
                dec.pop("confusion_risk", None)
                reason = dec.get("reason", "flag_disabled")
                dec["reason"] = f"{reason} | misconception_removed_to_text"
                changed += 1

            if dec.get("enhancement_type") == "mechanism_chain":
                dec["enhancement_type"] = "svg"
                dec.pop("mechanism_payload", None)
                reason = dec.get("reason", "flag_disabled")
                dec["reason"] = f"{reason} | mechanism_removed_to_svg"
                changed += 1

            sanitized.append(dec)

        if changed:
            print(f"  > Simplified pipeline normalized {changed} cached/routed decisions")
            if persist:
                save_decisions(sanitized, os.path.join(self.output_dir, "enhancement_decisions.txt"))

        return sanitized
    
    # ========== Phase 1 & 2: Whisper + 语义聚合 ==========
    
    def analyze_video_phase1_2(
        self,
        video_path: str = None,
        force_reprocess: bool = False
    ) -> List[Dict[str, Any]]:
        """Phase 1 & 2: Whisper转录 + 语义聚合"""
        if video_path:
            self.video_path = video_path
        
        if not self.video_path:
            raise ValueError("Video path not provided")
        
        print("\n" + "="*70)
        print("PHASE 1 & 2: Whisper Transcription + Semantic Segmentation")
        print("="*70)
        
        # Phase 1: Whisper转录
        print("\n[Phase 1] Whisper Transcription with sentence-level timestamps...")
        transcript = self._whisper_transcribe(force_reprocess)
        print(f"  ✓ Transcribed {len(transcript)} sentences")
        
        # Phase 2: 语义聚合
        print("\n[Phase 2] Semantic Segmentation...")
        segments = self._semantic_segmentation(transcript, force_reprocess)
        print(f"  ✓ Created {len(segments)} semantic segments")
        
        return segments
    
    def _whisper_transcribe(self, force: bool = False) -> List[Dict]:
        """Whisper转录（句子级别，英文）"""
        if not force and os.path.exists(self.whisper_transcript_path):
            print(f"  ✓ Loading cached transcript from {self.whisper_transcript_path}")
            return load_transcript(self.whisper_transcript_path)
        
        print(f"  > Transcribing video: {self.video_path}")
        
        try:
            import whisper
            
            print("  > Loading Whisper model (base)...")
            model = whisper.load_model("base")
            
            print("  > Transcribing with sentence-level timestamps...")
            result = model.transcribe(self.video_path, language='en', verbose=False)
            
            # 提取segment级别（句子）
            transcript = []
            for segment in result['segments']:
                transcript.append({
                    'text': segment['text'].strip(),
                    'start': segment['start'],
                    'end': segment['end']
                })
            
            save_transcript(transcript, self.whisper_transcript_path)
            print(f"  ✓ Transcribed {len(transcript)} sentences")
            
            return transcript
            
        except ImportError:
            print("  ⚠ Whisper not installed, using fallback")
            transcript = create_fallback_transcript()
            save_transcript(transcript, self.whisper_transcript_path)
            return transcript
        except Exception as e:
            print(f"  ✗ Whisper failed: {e}")
            transcript = create_fallback_transcript()
            save_transcript(transcript, self.whisper_transcript_path)
            return transcript
    
    def _semantic_segmentation(self, transcript: List[Dict], force: bool = False) -> List[Dict]:
        """语义聚合（基于句子）"""
        if not force and os.path.exists(self.semantic_segments_path):
            print(f"  > Loading cached segments from {self.semantic_segments_path}")
            return load_segments(self.semantic_segments_path)
        
        print(f"  > Segmenting {len(transcript)} sentences into semantic chunks...")
        
        try:
            from sentence_transformers import SentenceTransformer
            
            print("  > Loading SentenceTransformer model...")
            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            
            # 创建候选段（每2-3句一组）
            candidate_segments = self._create_candidate_segments(transcript, window_size=3)
            
            # 计算embeddings
            texts = [seg['text'] for seg in candidate_segments]
            embeddings = model.encode(texts)
            
            # 合并相似段
            segments = self._merge_similar_segments(candidate_segments, embeddings, threshold=0.75)
            
            save_segments(segments, self.semantic_segments_path)
            
            return segments
            
        except ImportError:
            print("  ⚠ sentence-transformers not installed, using fallback")
            from multimodal_utils import create_fallback_segments
            segments = create_fallback_segments(transcript)
            save_segments(segments, self.semantic_segments_path)
            return segments
    
    def _create_candidate_segments(self, transcript: List[Dict], window_size: int = 3) -> List[Dict]:
        """创建候选语义段（基于句子）"""
        if not transcript:
            return []
        
        segments = []
        i = 0
        while i < len(transcript):
            end_idx = min(i + window_size, len(transcript))
            sentences = transcript[i:end_idx]
            
            if sentences:
                segments.append({
                    'text': ' '.join([s['text'] for s in sentences]),
                    'start': sentences[0]['start'],
                    'end': sentences[-1]['end'],
                    'sentences': sentences
                })
            i = end_idx
        
        return segments
    
    def _merge_similar_segments(
        self,
        segments: List[Dict],
        embeddings: np.ndarray,
        threshold: float = 0.75
    ) -> List[Dict]:
        """合并相似段"""
        from sklearn.metrics.pairwise import cosine_similarity
        
        merged = []
        i = 0
        while i < len(segments):
            current_seg = segments[i]
            current_emb = embeddings[i]
            
            # 尝试与下一段合并
            while i + 1 < len(segments):
                next_emb = embeddings[i + 1]
                similarity = cosine_similarity([current_emb], [next_emb])[0][0]
                
                if similarity > threshold:
                    # 合并
                    next_seg = segments[i + 1]
                    current_seg = {
                        'text': current_seg['text'] + ' ' + next_seg['text'],
                        'start': current_seg['start'],
                        'end': next_seg['end'],
                        'sentences': current_seg.get('sentences', []) + next_seg.get('sentences', [])
                    }
                    current_emb = (current_emb + next_emb) / 2
                    i += 1
                else:
                    break
            
            merged.append(current_seg)
            i += 1
        
        return merged
    
    # ========== Phase 3: LLM多线程判断 ==========
    
    def analyze_video_phase3(
        self,
        segments: List[Dict] = None,
        force_reprocess: bool = False
    ) -> List[Dict[str, Any]]:
        """Phase 3: LLM判断增强类型（多线程）"""
        if segments is None:
            segments = load_segments(self.semantic_segments_path)
        
        print("\n" + "="*70)
        print("PHASE 3: LLM Classification (Multi-threaded)")
        print("="*70)
        
        # 调用DecisionAgent
        decisions = self.decision_agent.classify_segments(segments, force_reprocess, max_workers=self.max_workers)
        self.global_summary = self.decision_agent.latest_global_summary
        decisions = self._apply_feature_flags_to_decisions(decisions, persist=True)

        if self.enable_concept_graph:
            print("  > Building concept graph...")
            self.global_concept_graph = self.concept_graph_agent.build_graph(
                segments, decisions, self.global_summary, force_reprocess
            )
            print(f"  > Concept graph ready: {len(self.global_concept_graph.get('nodes', []))} nodes")
        else:
            self.global_concept_graph = {}

        decisions = self._apply_feature_flags_to_decisions(decisions)

        # Persist the post-routing decisions so downstream cached phases can
        # restore misconception/mechanism types and payloads correctly.
        save_decisions(decisions, os.path.join(self.output_dir, "enhancement_decisions.txt"))
        
        return decisions
    
    # ========== Phase 4: 布局计算 ==========
    
    def analyze_video_phase4(
        self,
        decisions: List[Dict] = None,
        force_reprocess: bool = False
    ) -> List[Dict[str, Any]]:
        """Phase 4: 布局计算（显著性检测）"""
        if decisions is None:
            from multimodal_utils import load_decisions
            decisions = load_decisions(os.path.join(self.output_dir, "enhancement_decisions.txt"))
        decisions = self._apply_feature_flags_to_decisions(decisions, persist=not force_reprocess)
        
        print("\n" + "="*70)
        print("PHASE 4: Layout with Saliency Detection")
        print("="*70)
        
        # 调用LayoutProcessor
        if not self.layout_agent:
            self.layout_agent = LayoutProcessor(
                self.video_path,
                max_workers=self.layout_max_workers,
                vision_llm_type=self.vision_llm_type,
            )
        
        enhancement_points = self.layout_agent.calculate_layouts(
            decisions,
            self.output_dir,
            force_reprocess
        )
        
        return enhancement_points
    
    # ========== Phase 5: 场景分析 ==========
    
    def analyze_video_phase5(
        self,
        enhancement_points: List[Dict] = None,
        force_reprocess: bool = False
    ) -> List[Dict[str, Any]]:
        """Phase 5: 场景分析和风格提取"""
        if enhancement_points is None:
            from multimodal_utils import load_decisions
            decisions = load_decisions(os.path.join(self.output_dir, "enhancement_decisions.txt"))
            decisions = self._apply_feature_flags_to_decisions(decisions, persist=not force_reprocess)
            enhancement_points = self.analyze_video_phase4(decisions, force_reprocess)
        
        print("\n" + "="*70)
        print("PHASE 5: Scene Analysis & Style Extraction")
        print("="*70)
        
        # 调用SceneAgent
        if not self.scene_agent:
            self.scene_agent = SceneAgent(self.video_path, self.output_dir, max_workers=self.scene_max_workers)
        
        enhancement_points = self.scene_agent.analyze_scenes(enhancement_points, force_reprocess)
        
        return enhancement_points
    
    # ========== Phase 6: 内容生成 ==========
    
    def analyze_video_phase6(
        self,
        enhancement_points: List[Dict] = None,
        force_reprocess: bool = False,
        llm_type: str = None,
        vision_llm_type: str = None,
        html_generator=None,
        html_path: str = None
    ) -> List[Dict[str, Any]]:
        """Phase 6: 生成实际内容（SVG/文字）"""
        if enhancement_points is None:
            from multimodal_utils import load_decisions
            decisions = load_decisions(os.path.join(self.output_dir, "enhancement_decisions.txt"))
            decisions = self._apply_feature_flags_to_decisions(decisions, persist=not force_reprocess)
            points = self.analyze_video_phase4(decisions, force_reprocess)
            points = self.analyze_video_phase5(points, force_reprocess)
            enhancement_points = points
        
        llm_type = llm_type or self.llm_type
        vision_llm_type = vision_llm_type or self.vision_llm_type
        
        print("\n" + "="*70)
        print("PHASE 6: Content Generation")
        print("="*70)
        
        # 调用ContentAgent（传递html_generator实现增量追加）
        enhancement_points = self.content_agent.generate_content(
            enhancement_points,
            html_generator=html_generator,
            html_path=html_path
        )
        
        return enhancement_points
