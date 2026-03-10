"""
SVG Agent Integration - SVG Agent集成接口
==========================================

桥梁模块：视频增强系统 <-> SVG Agent系统
统一画布: 1920x1080
"""

import os
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class SVGAgentInterface:
    """SVG Agent系统集成接口"""
    
    def __init__(self, svg_agent_path: Optional[str] = None):
        self.svg_agent_path = svg_agent_path or self._find_svg_agent_path()
        self.svg_agent_available = False
        
        if self.svg_agent_path and os.path.exists(self.svg_agent_path):
            self._setup_svg_agent()
        
        print(f"✓ SVGAgentInterface initialized")
        print(f"  SVG Agent available: {self.svg_agent_available}")
    
    def _find_svg_agent_path(self) -> Optional[str]:
        possible_paths = [
            './svg_agent',
            '../svg_agent',
            './svg_agent_system',
            os.path.join(os.path.dirname(__file__), 'svg_agent'),
        ]
        
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path) and os.path.exists(os.path.join(abs_path, 'main.py')):
                return abs_path
        
        return None
    
    def _setup_svg_agent(self):
        try:
            if self.svg_agent_path not in sys.path:
                sys.path.insert(0, self.svg_agent_path)
            
            from main import generate_svg_animation, generate_for_video_system
            self.generate_svg_animation = generate_svg_animation
            self.generate_for_video_system = generate_for_video_system
            self.svg_agent_available = True
            
            print("  ✓ SVG Agent system loaded successfully")
            
        except ImportError as e:
            print(f"  ⚠ SVG Agent import failed: {e}")
            self.svg_agent_available = False
    
    def generate_svg(
        self,
        topic: str,
        context: Optional[str] = None,
        style: str = 'educational',
        animation: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        if not self.svg_agent_available:
            print("  ⚠ SVG Agent not available, using fallback")
            return self._generate_fallback_svg(topic)
        
        try:
            result = self.generate_svg_animation(
                input_text=topic,
                context=style,
                output_dir=kwargs.get('output_dir'),
                sample_id=kwargs.get('sample_id')
            )
            
            return {
                'svg_content': result.get('svg_content'),
                'svg_path': result.get('svg_path'),
                'metadata': result.get('metadata', {})
            }
            
        except Exception as e:
            print(f"  ✗ SVG generation failed: {e}")
            return self._generate_fallback_svg(topic)
    
    def generate_batch(self, topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for idx, topic_info in enumerate(topics):
            print(f"\n[SVG Generation {idx+1}/{len(topics)}]")
            print(f"  Topic: {topic_info.get('topic', 'Unknown')}")
            
            result = self.generate_svg(
                topic=topic_info.get('topic', ''),
                context=topic_info.get('context'),
                style=topic_info.get('style', 'educational'),
                animation=topic_info.get('animation', True)
            )
            results.append(result)
        
        return results
    
    def _generate_fallback_svg(self, topic: str) -> Dict[str, Any]:
        """生成fallback SVG — 使用1920x1080标准画布"""
        safe_topic = topic[:40] if topic else "Visualization"
        cx = CANVAS_WIDTH // 2
        cy = CANVAS_HEIGHT // 2
        
        svg_content = f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1" />
    </linearGradient>
  </defs>
  
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="url(#grad)" rx="10"/>
  
  <text x="{cx}" y="250" font-family="Arial" font-size="48" 
        font-weight="bold" fill="white" text-anchor="middle">
    {safe_topic}
  </text>
  
  <circle cx="{cx}" cy="{cy}" r="100" fill="white" opacity="0.8">
    <animate attributeName="r" values="100;120;100" dur="2s" repeatCount="indefinite"/>
  </circle>
  
  <text x="{cx}" y="850" font-family="Arial" font-size="28" 
        fill="white" text-anchor="middle" opacity="0.6">
    [Fallback SVG - SVG Agent Not Available]
  </text>
</svg>'''
        
        return {
            'svg_content': svg_content,
            'svg_path': None,
            'metadata': {
                'fallback': True,
                'topic': topic
            }
        }
    
    def test_single_generation(self, topic: str = "How satellites work") -> Dict[str, Any]:
        print("\n" + "="*70)
        print("SVG AGENT TEST - SINGLE GENERATION")
        print("="*70)
        print(f"\nTopic: {topic}")
        
        result = self.generate_svg(
            topic=topic, context="scientific",
            style="educational", animation=True
        )
        
        print("\n" + "="*70)
        print("TEST COMPLETE")
        print("="*70)
        
        if result['svg_path']:
            print(f"\nSVG saved to: {result['svg_path']}")
        else:
            print(f"\nSVG content length: {len(result['svg_content'])} chars")
        
        return result
    
    def test_batch_generation(self, topics: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if topics is None:
            topics = [
                "How solar energy works",
                "The water cycle",
                "DNA replication process"
            ]
        
        print("\n" + "="*70)
        print("SVG AGENT TEST - BATCH GENERATION")
        print("="*70)
        
        topic_infos = [
            {'topic': t, 'context': 'scientific', 'style': 'educational'}
            for t in topics
        ]
        
        results = self.generate_batch(topic_infos)
        
        print(f"\nGenerated {len(results)} SVGs")
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="SVG Agent Interface Test")
    parser.add_argument('--topic', type=str, default="How satellites work")
    parser.add_argument('--batch', action='store_true')
    parser.add_argument('--svg-agent-path', type=str, default=None)
    
    args = parser.parse_args()
    
    interface = SVGAgentInterface(svg_agent_path=args.svg_agent_path)
    
    if args.batch:
        interface.test_batch_generation()
    else:
        interface.test_single_generation(topic=args.topic)


if __name__ == "__main__":
    main()