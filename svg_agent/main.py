"""
SVG Agent Main Entry
====================

入口函数 - 支持上下文注入
"""

import os
from typing import Dict, Any, Optional
from workflow import SVGWorkflow


def generate_svg_from_text(
    text_input: str,
    output_dir: str = None,
    save_file: bool = True,
    llm_type: str = "claude-sonnet-4-5-20250929",
    vision_llm_type: str = None,
    layout_context: Optional[Dict] = None,
    scene_context: Optional[Dict] = None,
    motion_context: Optional[Dict] = None,
    enable_complex_mode: bool = False,
    sample_id: str = "svg_output"
) -> Dict[str, Any]:
    """
    从文本生成SVG动画
    
    Args:
        text_input: 输入文本
        output_dir: 输出目录
        save_file: 是否保存文件
        llm_type: 文本LLM类型
        vision_llm_type: 视觉LLM类型
        layout_context: 布局上下文（空间约束）
        scene_context: 场景上下文（风格约束）
        enable_complex_mode: 启用复杂模式（默认False，简单模式）
        sample_id: 样本ID，用于文件命名（如animation_0_98）
        
    Returns:
        {
            "svg_content": SVG字符串,
            "svg_path": 文件路径（如果save_file=True）,
            "overall_score": 质量分数,
            "workflow_mode": "simple/complex",
            ...
        }
    """
    # 创建输出目录
    if save_file and output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 初始化工作流
    workflow = SVGWorkflow(
        llm_type=llm_type,
        vision_llm_type=vision_llm_type
    )
    
    # 生成SVG
    result = workflow.generate(
        input_text=text_input,
        context="technical",
        layout_context=layout_context,
        scene_context=scene_context,
        output_dir=output_dir if save_file else None,
        sample_id=sample_id,
        enable_complex_mode=enable_complex_mode
    )
    
    return result


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate SVG animation from text")
    parser.add_argument("text", help="Input text")
    parser.add_argument("--output", "-o", default="./svg_output", help="Output directory")
    parser.add_argument("--llm", default="claude-sonnet-4-5-20250929", help="LLM type")
    parser.add_argument("--vision-llm", help="Vision LLM type")
    parser.add_argument("--complex", action="store_true", help="Enable complex mode (default: simple)")
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"SVG Agent - Generating animation...")
    print(f"Mode: {'Complex' if args.complex else 'Simple'}")
    print(f"{'='*60}\n")
    
    result = generate_svg_from_text(
        text_input=args.text,
        output_dir=args.output,
        save_file=True,
        llm_type=args.llm,
        vision_llm_type=args.vision_llm,
        enable_complex_mode=args.complex
    )
    
    print(f"\n{'='*60}")
    print(f"✓ Generation complete!")
    print(f"  SVG path: {result.get('svg_path', 'N/A')}")
    print(f"  Score: {result.get('overall_score', 0)}/10")
    print(f"  Workflow mode: {result.get('workflow_mode', 'N/A')}")
    print(f"  Iterations: {result.get('iteration', 0)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
