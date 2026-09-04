"""
Check Top-Left Cluster
======================

直接传入 SVG 文件路径，测试是否存在关键 g 缺少 translate、
且主实体异常聚集在左上角的问题。
"""

import argparse
import json
from pathlib import Path

import svg_validator


def main():
    parser = argparse.ArgumentParser(description="Check SVG top-left clustering geometry issues")
    parser.add_argument("svg_path", help="Path to SVG file")
    args = parser.parse_args()

    svg_path = Path(args.svg_path).expanduser().resolve()
    if not svg_path.exists():
        raise SystemExit(f"SVG not found: {svg_path}")

    svg_content = svg_path.read_text(encoding="utf-8")
    result = svg_validator.detect_top_left_cluster(svg_content)

    print(json.dumps({
        "svg_path": str(svg_path),
        "flagged": result.get("flagged", False),
        "reason": result.get("reason"),
        "suspicious_groups": result.get("suspicious_groups", []),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
