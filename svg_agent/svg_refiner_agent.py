"""
SVG Refiner Agent
=================

SVG精炼 - 局部修补
画布: 1920x1080
"""

import os
import re
from typing import Dict, Tuple, List
from base_agent import BaseAgent
from state import SVGState

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class SVGRefinerAgent(BaseAgent):
    """SVG精炼Agent"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("svg_refiner", llm_type)
        self.role_description = "Refine SVG with surgical precision"
        self.capabilities = ["code_analysis", "targeted_fixes", "minimal_changes"]
    
    def execute(self, state: SVGState) -> SVGState:
        """执行SVG精炼"""
        self._log("Refining SVG...")
        
        current_svg = state.get("current_svg", "")
        improvement_suggestions = state.get("improvement_suggestions", [])
        review_result = state.get("review_result", {})
        validation_result = state.get("validation_result", {})
        
        if not current_svg:
            self._log("No SVG to refine", "warning")
            return state
        
        refine_count = state.get("refine_count", 0) + 1
        state["refine_count"] = refine_count
        
        code_issues = validation_result.get("issues", [])
        has_code_issues = len([i for i in code_issues if i.get("severity") == "critical"]) > 0
        has_visual_issues = len(improvement_suggestions) > 0
        
        # 坐标问题优先程序化修复
        coordinate_issues = [i for i in code_issues if i.get("type") in ["coordinate_clustering", "coordinates_out_of_range", "wrong_viewbox"]]
        
        if coordinate_issues:
            self._log("  Strategy: Programmatic coordinate fix")
            refined_svg = self._fix_coordinates_programmatically(current_svg)
            other_issues = [i for i in code_issues if i not in coordinate_issues]
            if other_issues:
                refined_svg = self._fix_code_issues(refined_svg, other_issues)
        elif has_code_issues:
            refined_svg = self._fix_code_issues(current_svg, code_issues)
            self._log("  Strategy: Fix code issues")
        elif has_visual_issues:
            refined_svg = self._apply_targeted_improvements(current_svg, improvement_suggestions, review_result)
            self._log("  Strategy: Apply targeted improvements")
        else:
            refined_svg = self._gentle_enhancement(current_svg, review_result)
            self._log("  Strategy: Gentle enhancement")
        
        if self._validate_svg(refined_svg):
            refined_svg = self._fix_css_transform_conflict(refined_svg)
            state["current_svg"] = refined_svg
            self._log("✓ SVG refined successfully")
        else:
            self._log("⚠ Refined SVG invalid, keeping original", "warning")
        
        if state.get("output_dir"):
            svg_path = self._save_svg_with_version(refined_svg, state, refine_count)
            state["svg_path"] = svg_path
            png_path = self._render_svg_to_png(svg_path, state)
            if png_path:
                state["svg_png_path"] = png_path
        
        self.record_decision(
            state, "refinement",
            f"Iteration: {state.get('iteration', 0)}",
            f"Applied: {len(improvement_suggestions)} suggestions"
        )
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "refinement":
            return True, 0.9
        return False, 0.0
    
    def _fix_code_issues(self, svg_content: str, issues: List[Dict]) -> str:
        """修复代码问题"""
        try:
            critical_issues = [i for i in issues if i.get("severity") == "critical"]
            
            system_prompt = f"""You are an SVG Code Surgeon. Fix ONLY the reported issues.

RULES:
1. MINIMAL CHANGES - Touch only what needs fixing
2. PRESERVE WORKING PARTS - Keep all good code exactly as is
3. Canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT} (viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}")
4. Coordinates should be distributed across full canvas:
   - X range: 100-1820, center at 960
   - Y range: 100-980, center at 540
5. If elements are clustered, redistribute them (left x~400, center x~960, right x~1520)

⚠️ CRITICAL: CSS transform in @keyframes OVERWRITES SVG transform="translate()". 
NEVER use transform: translateY() in @keyframes. Use ONLY opacity.
Always use nested <g>: outer <g> for position, inner <g> for animation class.

Output: The corrected SVG code only."""
            
            issues_text = "\n".join([
                f"- {i.get('severity','').upper()}: {i.get('message')} ({i.get('suggestion', '')})"
                for i in critical_issues[:5]
            ])
            
            prompt = f"""Fix these issues:

{issues_text}

SVG:
{svg_content}

Make MINIMAL changes. Return corrected SVG only."""
            
            result = self.invoke_llm(prompt, system_prompt)
            return self._extract_svg(result)
            
        except Exception as e:
            self._log(f"Code fix failed: {e}", "error")
            return svg_content
    
    def _apply_targeted_improvements(self, svg_content: str, suggestions: List[Dict], review: Dict) -> str:
        """应用针对性改进"""
        try:
            top_suggestions = suggestions[:3]
            
            system_prompt = """You are an SVG Improvement Specialist. Apply ONLY the requested changes.
Keep everything else identical.
⚠️ CRITICAL: NEVER use transform: translate in CSS @keyframes (it overrides SVG positioning).
Always use nested <g>: outer for position, inner for animation.
Output corrected SVG only."""
            
            suggestions_text = "\n".join([
                f"{i+1}. {s.get('type', 'unknown')}: {s.get('target', 'N/A')} → {s.get('suggested', 'N/A')}"
                for i, s in enumerate(top_suggestions)
            ])
            
            prompt = f"""Apply these improvements:

{suggestions_text}

SVG:
{svg_content}

Return improved SVG only."""
            
            result = self.invoke_llm(prompt, system_prompt)
            return self._extract_svg(result)
            
        except Exception as e:
            self._log(f"Targeted improvements failed: {e}", "error")
            return svg_content
    
    def _gentle_enhancement(self, svg_content: str, review_result: Dict) -> str:
        """温和增强"""
        try:
            consistency_score = review_result.get("consistency_score", 5)
            aesthetic_score = review_result.get("aesthetic_score", 5)
            
            if consistency_score >= 8 and aesthetic_score >= 8:
                return svg_content
            
            system_prompt = """You are an SVG Polisher. Make subtle, professional refinements only.
Fine-tune spacing, colors, timing. Don't redesign.
⚠️ CRITICAL: NEVER use transform: translate in CSS @keyframes.
Output SVG only."""
            
            prompt = f"""Polish this SVG (scores: consistency={consistency_score}/10, aesthetic={aesthetic_score}/10):

{svg_content}

Return polished SVG only."""
            
            # print("Refineagent prompt:",prompt)
            result = self.invoke_llm(prompt, system_prompt)
            return self._extract_svg(result)
            
        except Exception as e:
            self._log(f"Gentle enhancement failed: {e}", "error")
            return svg_content
    
    def _fix_coordinates_programmatically(self, svg_content: str) -> str:
        """
        程序化修复坐标问题（保护style和defs不被修改）
        目标画布: 1920x1080
        """
        # 1. 保护style和defs块
        style_blocks = []
        defs_blocks = []
        
        def save_style(match):
            style_blocks.append(match.group(0))
            return f'__STYLE_{len(style_blocks)-1}__'
        
        def save_defs(match):
            defs_blocks.append(match.group(0))
            return f'__DEFS_{len(defs_blocks)-1}__'
        
        working = re.sub(r'<style[^>]*>.*?</style>', save_style, svg_content, flags=re.DOTALL)
        working = re.sub(r'<defs[^>]*>.*?</defs>', save_defs, working, flags=re.DOTALL)
        
        # 2. 检测当前viewBox
        viewbox_match = re.search(r'viewBox=["\']([^"\']+)["\']', working)
        current_width, current_height = CANVAS_WIDTH, CANVAS_HEIGHT
        
        if viewbox_match:
            parts = viewbox_match.group(1).split()
            if len(parts) >= 4:
                try:
                    current_width = float(parts[2])
                    current_height = float(parts[3])
                except:
                    pass
        
        # 3. 只在尺寸不匹配时缩放
        if abs(current_width - CANVAS_WIDTH) > 1 or abs(current_height - CANVAS_HEIGHT) > 1:
            self._log(f"Scaling from {current_width}x{current_height} to {CANVAS_WIDTH}x{CANVAS_HEIGHT}", "info")
            
            scale_x = CANVAS_WIDTH / current_width if current_width > 0 else 1.0
            scale_y = CANVAS_HEIGHT / current_height if current_height > 0 else 1.0
            
            # 缩放元素属性（使用word boundary防止匹配CSS属性）
            def scale_x_attr(match):
                attr = match.group(1)
                val = float(match.group(2))
                return f'{attr}="{val * scale_x:.1f}"'
            
            def scale_y_attr(match):
                attr = match.group(1)
                val = float(match.group(2))
                return f'{attr}="{val * scale_y:.1f}"'
            
            working = re.sub(r'\b(x|cx|x1|x2)="(\d+(?:\.\d+)?)"', scale_x_attr, working)
            working = re.sub(r'\b(y|cy|y1|y2)="(\d+(?:\.\d+)?)"', scale_y_attr, working)
            
            # 缩放transform translate
            def scale_translate(match):
                tx = float(match.group(1)) * scale_x
                ty = float(match.group(2)) * scale_y
                return f'translate({tx:.1f}, {ty:.1f})'
            
            working = re.sub(
                r'translate\s*\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)',
                scale_translate, working
            )
        
        # 4. 修复viewBox
        working = re.sub(
            r'viewBox=["\'][^"\']*["\']',
            f'viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}"',
            working
        )
        
        # 5. 恢复保护的块
        for i, block in enumerate(style_blocks):
            working = working.replace(f'__STYLE_{i}__', block)
        for i, block in enumerate(defs_blocks):
            working = working.replace(f'__DEFS_{i}__', block)
        
        return working
    
    def _fix_css_transform_conflict(self, svg_content: str) -> str:
        """
        修复 LLM 生成 SVG 中的 CSS 致命 bug:
        1. opacity: 0 被锁死 (animation shorthand 覆盖 fadeIn)
        2. CSS transform 覆盖 SVG transform (位置跑到左上角)
        """
        if not svg_content:
            return svg_content
        
        style_match = re.search(r'(<style[^>]*>)(.*?)(</style>)', svg_content, re.DOTALL)
        if not style_match:
            return svg_content
        
        css = style_match.group(2)
        fixes = []
        
        # Fix 1: 保护 @keyframes, 从普通选择器移除 opacity: 0
        kf_blocks = []
        def save_kf(m):
            kf_blocks.append(m.group(0))
            return f'__KF_{len(kf_blocks)-1}__'
        
        css_work = re.sub(r'@keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}', save_kf, css)
        
        css_before = css_work
        css_work = re.sub(r'\bopacity\s*:\s*0\s*;?', '', css_work)
        css_work = re.sub(r'\btransform\s*:\s*translate[XYxy]?\([^)]*\)\s*;?', '', css_work)
        if css_work != css_before:
            fixes.append('opacity+translate-in-selectors')
        
        for i, block in enumerate(kf_blocks):
            css_work = css_work.replace(f'__KF_{i}__', block)
        
        # Fix 2: 从 @keyframes 内移除 translate
        css_before = css_work
        css_work = re.sub(r'\btransform\s*:\s*translate[XYxy]?\([^)]*\)\s*;?', '', css_work)
        if css_work != css_before:
            fixes.append('translate-in-keyframes')
        
        # Fix 3: 注入安全规则
        safety = '/* SAFETY */ svg g > g { opacity: 1; }'
        if safety not in css_work:
            css_work += f'\n      {safety}'
            fixes.append('safety-visibility')
        
        css_work = re.sub(r'\n\s*\n\s*\n', '\n\n', css_work)
        
        if fixes:
            self._log(f"CSS fixes in refined SVG: {', '.join(fixes)}", "info")
            svg_content = svg_content[:style_match.start(2)] + css_work + svg_content[style_match.end(2):]
        
        # Fix 4: 内联 style 中的 transform: translate
        svg_content = re.sub(
            r'(style="[^"]*?)\s*transform\s*:\s*translate[^;"]*;?\s*',
            r'\1',
            svg_content
        )
        
        # Fix 5: 移除 opacity="0" 属性
        svg_content = re.sub(r'\s+opacity\s*=\s*["\']0["\']', '', svg_content)
        
        return svg_content
    
    def _extract_svg(self, text: str) -> str:
        text = text.replace('```svg', '').replace('```xml', '').replace('```', '').strip()
        match = re.search(r'<svg.*?</svg>', text, re.DOTALL)
        return match.group(0) if match else text
    
    def _validate_svg(self, svg: str) -> bool:
        if not svg or len(svg) < 50:
            return False
        if '<svg' not in svg.lower() or '</svg>' not in svg.lower():
            return False
        content_tags = ['<rect', '<circle', '<path', '<line', '<polygon', '<text', '<g']
        return any(tag in svg for tag in content_tags)
    
    def _save_svg_with_version(self, svg_content: str, state: SVGState, refine_count: int) -> str:
        output_dir = state.get("output_dir")
        sample_id = state.get("sample_id", "output")
        suffix = f"_v{refine_count}" if refine_count > 0 else ""
        filepath = os.path.join(output_dir, f"{sample_id}{suffix}.svg")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        print(f"  Saved Refined SVG: file://{os.path.abspath(filepath)}")
        return filepath
    
    def _render_svg_to_png(self, svg_path: str, state: SVGState) -> str:
        try:
            from playwright.async_api import async_playwright
            import asyncio
            
            png_path = svg_path.replace('.svg', '.png')
            temp_html = svg_path + '_temp.html'
            
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg = f.read()
            
            html = f'<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{{margin:0;background:#000;display:flex;justify-content:center;align-items:center;min-height:100vh}}svg{{max-width:100%;height:auto}}</style></head><body>{svg}</body></html>'
            
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(html)
            
            async def render():
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    page = await browser.new_page()
                    await page.set_viewport_size({"width": 1920, "height": 1080})
                    await page.goto(f"file:///{os.path.abspath(temp_html).replace(os.sep, '/')}")
                    await page.wait_for_timeout(500)
                    loc = page.locator("svg").first
                    if await loc.count() > 0:
                        await loc.screenshot(path=png_path)
                    else:
                        await page.screenshot(path=png_path)
                    await browser.close()
            
            asyncio.run(render())
            if os.path.exists(temp_html):
                os.remove(temp_html)
            return png_path if os.path.exists(png_path) else None
        except:
            return None