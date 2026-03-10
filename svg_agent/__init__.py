"""
SVG Agent System Package
=========================

FUI-style technical animation SVG generator using multi-agent system
"""

from .workflow import SVGWorkflow
from .main import (
    generate_svg_animation,
    generate_for_video_system,
    generate_svg_from_text  # 新增：主要文本输入接口
)

__version__ = "2.0.0"

__all__ = [
    'SVGWorkflow',
    'generate_svg',
    'generate_svg_for_video',
    'generate_svg_animation',
    'generate_for_video_system',
    'generate_svg_from_text',  # 推荐使用这个接口
]
