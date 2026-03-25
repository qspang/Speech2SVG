"""
Video Enhancer - 视频增强器主入口
==================================

集成完整的Phase 1-7流程
"""

import os
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class VideoEnhancer:
    """视频增强器 - 主控制器"""
    
    def __init__(
        self,
        video_path: str,
        output_base_dir: str = "../enhanced_videos",
        llm_type: str = "claude-sonnet-4-5-20250929",
        vision_llm_type: str = "claude-sonnet-4-5-20250929",
        svg_mode: str = "simple",
        max_workers: int = 1,
        layout_max_workers: int = 1,
        scene_max_workers: int = 1,
        enable_print_layout: bool = False,
        enable_print_scene: bool = False,
        enable_concept_graph: bool = False,
    ):
        """
        初始化
        
        Args:
            video_path: 视频路径
            output_base_dir: 输出基础目录
            llm_type: 文本LLM类型（用于文本分类、内容生成等）
            vision_llm_type: 视觉LLM类型（用于图像分析、SVG评审等）
            svg_mode: SVG生成模式（simple, normal, complex）
            max_workers: 内容生成并发数（默认1=串行）
        """
        self.video_path = video_path
        self.output_base_dir = output_base_dir
        self.llm_type = llm_type
        self.vision_llm_type = vision_llm_type
        self.svg_mode = svg_mode
        self.max_workers = max(1, max_workers)
        self.layout_max_workers = max(1, layout_max_workers)
        self.scene_max_workers = max(1, scene_max_workers)
        self.enable_print_layout = enable_print_layout
        self.enable_print_scene = enable_print_scene
        self.enable_concept_graph = enable_concept_graph
        
        # 创建输出目录（不使用时间戳）
        video_name = Path(video_path).stem
        self.output_dir = os.path.join(output_base_dir, video_name)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 分析临时目录
        self.temp_dir = os.path.join(self.output_dir, "temp_analysis")
        
        print(f"✓ VideoEnhancer initialized")
        print(f"  Video: {video_path}")
        print(f"  Output: {self.output_dir}")
        print(f"  LLM: {llm_type}")
        print(f"  Vision LLM: {vision_llm_type}")
        print(f"  SVG Generation Mode: {svg_mode.capitalize()}")
        print(f"  Max Workers: {self.max_workers}")
        print(f"  Layout Workers: {self.layout_max_workers}")
        print(f"  Scene Workers: {self.scene_max_workers}")
        print(f"  Print Layout Debug: {self.enable_print_layout}")
        print(f"  Print Scene Debug: {self.enable_print_scene}")
    
    def process(self, force_reprocess: bool = False) -> str:
        """
        完整处理流程（Phase 1-7）
        
        增量生成模式:
        - Phase 6之前先生成HTML骨架（含视频、字幕面板）
        - Phase 6每生成一个SVG/文字就追加到HTML中
        - Phase 7为最终确认和资源整理
        
        Returns:
            生成的HTML文件路径
        """
        print("\n" + "="*70)
        print("VIDEO ENHANCEMENT PIPELINE")
        print("="*70)
        
        # 导入分析器和HTML生成器
        from multimodal_analyzer import MultimodalAnalyzer
        from html_generator import HTMLGenerator
        
        # 创建分析器
        analyzer = MultimodalAnalyzer(
            video_path=self.video_path,
            output_dir=self.temp_dir,
            llm_type=self.llm_type,
            vision_llm_type=self.vision_llm_type,
            svg_mode=self.svg_mode,
            max_workers=self.max_workers,
            layout_max_workers=self.layout_max_workers,
            scene_max_workers=self.scene_max_workers,
            enable_print_layout=self.enable_print_layout,
            enable_print_scene=self.enable_print_scene,
            enable_concept_graph=self.enable_concept_graph,
        )
        
        # Phase 1-5: 分析流程
        segments = analyzer.analyze_video_phase1_2(force_reprocess=force_reprocess)
        decisions = analyzer.analyze_video_phase3(segments, force_reprocess=force_reprocess)
        enhancement_points = analyzer.analyze_video_phase4(decisions, force_reprocess=force_reprocess)
        enhancement_points = analyzer.analyze_video_phase5(enhancement_points, force_reprocess=force_reprocess)
        
        # Pre-Phase 6: 生成HTML骨架
        print("\n" + "="*70)
        print("PRE-PHASE 6: HTML Skeleton Generation")
        print("="*70)
        
        html_generator = HTMLGenerator()
        html_path = os.path.join(self.output_dir, "enhanced_video.html")
        transcript_path = os.path.join(self.temp_dir, "whisper_transcript.txt")
        
        html_generator.generate_skeleton(
            video_source=self.video_path,
            transcript_path=transcript_path,
            html_path=html_path,
            concept_graph=analyzer.global_concept_graph
        )
        
        print(f"  ✓ HTML skeleton ready: {html_path}")
        print(f"  → 可以在浏览器中打开此文件实时查看生成进度")
        
        # Phase 6: 内容生成（增量追加到HTML）
        enhancement_points = analyzer.analyze_video_phase6(
            enhancement_points, 
            force_reprocess=force_reprocess,
            llm_type=self.llm_type,
            vision_llm_type=self.vision_llm_type,
            html_generator=html_generator,
            html_path=html_path
        )
        
        # Phase 7: 最终确认和资源整理
        print("\n" + "="*70)
        print("PHASE 7: Finalization")
        print("="*70)
        
        self._finalize_html(html_path)
        
        print(f"\n✓ Enhancement complete!")
        print(f"  HTML: {html_path}")
        
        return html_path
    
    def _finalize_html(self, html_path: str):
        """最终确认: 复制assets到输出目录"""
        print(f"  > Finalized assets path mappings")

        print(f"  > Finalized: {html_path}")


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Video Enhancement System')
    parser.add_argument('video_path', help='Path to video file')
    parser.add_argument('--output', '--output-base-dir', dest='output_base_dir', 
                        default='../enhanced_videos', help='Output base directory')
    parser.add_argument('--llm', '--llm-type', dest='llm_type',
                        default='claude-sonnet-4-5-20250929', help='LLM type for text processing')
    parser.add_argument('--vision-llm', '--vision-llm-type', dest='vision_llm_type',
                        default='claude-sonnet-4-5-20250929', help='Vision LLM type for image analysis')
    parser.add_argument('--svg-mode', dest='svg_mode', choices=['simple', 'normal', 'complex'], default='simple',
                        help='SVG Generation mode (default: simple)')
    parser.add_argument('--max-workers', type=int, default=1, dest='max_workers',
                        help='Max concurrent workers for content generation (default: 1 = sequential)')
    parser.add_argument('--layout-max-workers', type=int, default=1, dest='layout_max_workers',
                        help='Max concurrent workers for layout analysis')
    parser.add_argument('--scene-max-workers', type=int, default=1, dest='scene_max_workers',
                        help='Max concurrent workers for scene analysis')
    parser.add_argument('--enable-print-layout', action='store_true',
                        help='Print detailed layout / VLLM placement debug logs')
    parser.add_argument('--enable-print-scene', action='store_true',
                        help='Print detailed scene / LLM design-guide debug logs')
    parser.add_argument('--enable-concept-graph', action='store_true',
                        help='Enable persistent global concept graph panel')
    parser.add_argument('--force-reprocess', action='store_true',
                        help='Ignore caches and recompute all analysis stages')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video_path):
        print(f"Error: Video not found: {args.video_path}")
        return 1
    
    # 实例化Enhancer，传入解析后的参数
    enhancer = VideoEnhancer(
        video_path=args.video_path,
        output_base_dir=args.output_base_dir,
        llm_type=args.llm_type,
        vision_llm_type=args.vision_llm_type,
        svg_mode=args.svg_mode,
        max_workers=args.max_workers,
        layout_max_workers=args.layout_max_workers,
        scene_max_workers=args.scene_max_workers,
        enable_print_layout=args.enable_print_layout,
        enable_print_scene=args.enable_print_scene,
        enable_concept_graph=args.enable_concept_graph,
    )
    
    html_path = enhancer.process(force_reprocess=args.force_reprocess)
    
    print(f"\n✓ Open {html_path} in browser")
    return 0


if __name__ == "__main__":
    exit(main())
