"""
Code Validator Agent
====================

代码质检 - 基础检查 + LLM深度验证
画布: 1920x1080
"""

from typing import Dict, Tuple, List
from base_agent import BaseAgent
from state import SVGState

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class CodeValidatorAgent(BaseAgent):
    """代码验证Agent - 双层质检"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("code_validator", llm_type)
        self.role_description = "Validate SVG code"
        self.capabilities = ["syntax_check", "structure_validation", "llm_deep_check"]
    
    def execute(self, state: SVGState) -> SVGState:
        """执行代码验证"""
        self._log("Validating SVG code...")
        
        svg_content = state.get("current_svg", "")
        
        if not svg_content:
            state["validation_result"] = {"valid": False, "error": "no_svg"}
            return state
        
        # === 1. Initial Render Test ===
        current_svg = svg_content
        render_check = self._simple_render_test(current_svg, state)
        
        # === 2. If render passes, do basic check only and return (fast path) ===
        if render_check.get("renders_successfully"):
            self._log("✓ Render test passed on first try")
            basic = self._basic_syntax_check(current_svg)
            validation = {
                "valid": basic["critical_count"] == 0,
                "issues": basic["issues"],
                "critical_count": basic["critical_count"],
                "score": max(0, 100 - basic["critical_count"] * 40),
                "render_test": "passed"
            }
            
            # Auto-save if valid
            if validation["valid"]:
                if state.get("iteration", 0) > 0:
                    self._save_validated_artifacts(current_svg, state)
                else:
                    self._log("✓ Valid & Unchanged. Skipping redundant file save.")
            
            state["validation_result"] = validation
            state["code_issues"] = validation.get("issues", [])
            
            self.record_decision(
                state, "code_validation",
                f"Valid: {validation.get('valid')}",
                f"Score: {validation.get('score', 0)}/100"
            )
            self._log(f"✓ Validation passed (score: {validation.get('score')})")
            return state
        
        # === 3. Render failed — LLM Fix Loop ===
        max_retries = 3
        for attempt in range(max_retries):
            self._log(f"⚠ Render failed (Attempt {attempt + 1}), trying LLM fix...", "warning")
            current_svg = self._fix_render_issues(current_svg, render_check.get("error", "Unknown error"))
            render_check = self._simple_render_test(current_svg, state)
            
            if render_check.get("renders_successfully"):
                self._log(f"✓ Render fixed on attempt {attempt + 1}")
                break
        
        # Update state with fixed SVG if changed
        if current_svg != svg_content:
            state["current_svg"] = current_svg
            self._log("Updated SVG with fixed version", "success")
        
        # === 4. Final Validation ===
        basic = self._basic_syntax_check(current_svg)
        
        if render_check.get("renders_successfully"):
            validation = {
                "valid": basic["critical_count"] == 0,
                "issues": basic["issues"],
                "critical_count": basic["critical_count"],
                "score": max(0, 100 - basic["critical_count"] * 40),
                "render_test": "passed"
            }
            if validation["valid"]:
                self._save_validated_artifacts(current_svg, state)
        else:
            validation = {
                "valid": False,
                "issues": basic["issues"] + [{"type": "render_error", "severity": "critical", "message": render_check.get("error")}],
                "critical_count": basic["critical_count"] + 1,
                "score": 0,
                "render_test": "failed"
            }
        
        state["validation_result"] = validation
        state["code_issues"] = validation.get("issues", [])
        
        self.record_decision(
            state, "code_validation",
            f"Valid: {validation.get('valid')}",
            f"Score: {validation.get('score', 0)}/100"
        )
        
        if validation.get("valid"):
            self._log(f"✓ Validation passed (score: {validation.get('score')})")
        else:
            self._log(f"✗ Validation failed: {len(validation.get('issues', []))} issues", "error")
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "code_validation":
            return True, 0.95
        return False, 0.0
    
    def _simple_render_test(self, svg_content: str, state: SVGState) -> Dict:
        """简单渲染测试 (使用临时文件)"""
        try:
            import cairosvg
            import tempfile
            import os
            
            # 使用现有路径或创建临时文件
            svg_path = state.get("svg_path")
            
            # 如果svg_content与文件不一致(例如经过了修复)，则需要写入临时文件
            # 为简单起见，我们总是写入临时文件来测试当前内存中的内容
            with tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w', encoding='utf-8') as f:
                f.write(svg_content)
                temp_svg_path = f.name
            
            try:
                # 渲染到内存
                png_data = cairosvg.svg2png(url=temp_svg_path, write_to=None)
                
                # 检查数据有效性
                if not png_data or len(png_data) < 10:
                    return {"renders_successfully": False, "error": "Rendered PNG is empty"}
                
                self._log("✓ Render test passed", "info")
                return {"renders_successfully": True, "error": None}
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_svg_path):
                    os.remove(temp_svg_path)
                    
        except ImportError:
            self._log("cairosvg not installed/found", "error")
            return {"renders_successfully": False, "error": "cairosvg not available", "fallback": True}
        except Exception as e:
            # DEBUG: Print exact error to console so user can see it
            print(f"    [Validator DEBUG] Render failed for temp file {state.get('svg_path', 'unknown')}: {str(e)}")
            return {"renders_successfully": False, "error": str(e)}
    
    def _basic_syntax_check(self, svg: str) -> Dict:
        """基础语法检查"""
        issues = []
        import re
        
        # 基础标签检查
        if '<svg' not in svg.lower():
            issues.append({"type": "missing_tag", "severity": "critical", "message": "Missing <svg> tag"})
        if '</svg>' not in svg.lower():
            issues.append({"type": "missing_tag", "severity": "critical", "message": "Missing </svg> tag"})
        
        if '<svg' in svg and 'xmlns=' not in svg:
            issues.append({"type": "missing_attribute", "severity": "warning", "message": "Missing xmlns"})
        
        if 'viewBox' not in svg and 'width' not in svg:
            issues.append({"type": "missing_dimensions", "severity": "critical", "message": "Missing viewBox or dimensions"})
        
        content_tags = ['<rect', '<circle', '<path', '<line', '<polygon', '<text', '<g']
        if not any(tag in svg for tag in content_tags):
            issues.append({"type": "empty_svg", "severity": "critical", "message": "No visual content"})
        
        # viewBox检查（应为1920x1080）
        viewbox_match = re.search(r'viewBox=["\']([^"\']+)["\']', svg)
        if viewbox_match:
            vb = viewbox_match.group(1).split()
            if len(vb) >= 4:
                try:
                    vb_w, vb_h = float(vb[2]), float(vb[3])
                    if abs(vb_w - CANVAS_WIDTH) > 1 or abs(vb_h - CANVAS_HEIGHT) > 1:
                        issues.append({
                            "type": "wrong_viewbox", "severity": "warning",
                            "message": f"viewBox should be '0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}'",
                            "suggestion": f'Change to viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}"'
                        })
                except:
                    pass
        
        # 坐标聚集检查（过滤掉style和defs内容）
        svg_no_style = re.sub(r'<style[^>]*>.*?</style>', '', svg, flags=re.DOTALL)
        svg_no_defs = re.sub(r'<defs[^>]*>.*?</defs>', '', svg_no_style, flags=re.DOTALL)
        
        x_coords = re.findall(r'\b(?:x|cx)=["\']?(\d+(?:\.\d+)?)', svg_no_defs)
        y_coords = re.findall(r'\b(?:y|cy)=["\']?(\d+(?:\.\d+)?)', svg_no_defs)
        
        # 加上translate坐标
        for tx, ty in re.findall(r'translate\s*\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)', svg_no_defs):
            x_coords.append(tx)
            y_coords.append(ty)
        
        if len(x_coords) >= 3 and len(y_coords) >= 3:
            x_vals = [float(x) for x in x_coords if float(x) >= 10]
            y_vals = [float(y) for y in y_coords if float(y) >= 10]
            
            if x_vals and y_vals:
                # 检查聚集（>50%的坐标在左上角20%区域）
                clustered_x = sum(1 for x in x_vals if x < CANVAS_WIDTH * 0.2) / len(x_vals)
                clustered_y = sum(1 for y in y_vals if y < CANVAS_HEIGHT * 0.2) / len(y_vals)
                
                if clustered_x > 0.5 and clustered_y > 0.5:
                    issues.append({
                        "type": "coordinate_clustering", "severity": "critical",
                        "message": f"Elements clustered in top-left ({int(clustered_x*100)}% X < {int(CANVAS_WIDTH*0.2)}, {int(clustered_y*100)}% Y < {int(CANVAS_HEIGHT*0.2)})",
                        "suggestion": f"Redistribute: left x~400, center x~960, right x~1520"
                    })
                
                # 检查水平展开度
                if len(x_vals) >= 2:
                    spread = max(x_vals) - min(x_vals)
                    if spread < CANVAS_WIDTH * 0.3:
                        issues.append({
                            "type": "narrow_spread", "severity": "warning",
                            "message": f"Horizontal spread only {int(spread)}px (should be > {int(CANVAS_WIDTH*0.3)}px)",
                            "suggestion": "Spread elements across full canvas width"
                        })
        
        critical_count = len([i for i in issues if i.get("severity") == "critical"])
        return {"issues": issues, "critical_count": critical_count, "passed_basic": critical_count == 0}
    
    def _llm_deep_validation(self, svg_content: str, basic_check: Dict) -> Dict:
        """LLM深度验证"""
        try:
            system_prompt = f"""You are an SVG Code Validator. Check this SVG for issues.

Canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT} (viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}")

Check: structure, attributes, animations, rendering safety, coordinate distribution.
Elements should be distributed across X: 0-{CANVAS_WIDTH}, Y: 0-{CANVAS_HEIGHT}.
Center should be near ({CANVAS_WIDTH//2}, {CANVAS_HEIGHT//2}).

Output JSON:
{{
  "issues": [{{"type": "...", "severity": "critical/warning/info", "message": "...", "suggestion": "..."}}],
  "strengths": ["..."],
  "rendering_safe": true/false,
  "educational_quality": "high/medium/low"
}}"""
            
            # 截断SVG避免token过多
            svg_preview = svg_content[:3000] + ("..." if len(svg_content) > 3000 else "")
            
            prompt = f"""Validate this SVG:

{svg_preview}

Basic check found {basic_check['critical_count']} critical issues.
Return JSON only."""
           
            # print("CodeValidatorAgent prompt:",prompt)
            result = self.invoke_llm(prompt, system_prompt)
            parsed = self.parse_json_response(result)
            # print("CodeValidatorAgent result:",parsed)
            return self.parse_json_response(parsed)
            
        except Exception as e:
            self._log(f"LLM validation failed: {e}", "warning")
            return {"issues": [], "rendering_safe": True, "educational_quality": "unknown"}
    
    def _merge_validation_results(self, basic: Dict, llm: Dict) -> Dict:
        all_issues = basic.get("issues", []) + llm.get("issues", [])
        critical = len([i for i in all_issues if i.get("severity") == "critical"])
        warnings = len([i for i in all_issues if i.get("severity") == "warning"])
        score = max(0, 100 - critical * 40 - warnings * 10)
        valid = critical == 0 and llm.get("rendering_safe", True) and score >= 60
        
        return {
            "valid": valid,
            "issues": all_issues,
            "critical_count": critical,
            "warning_count": warnings,
            "score": score,
            "rendering_safe": llm.get("rendering_safe", True),
            "educational_quality": llm.get("educational_quality", "unknown")
        }
    
    def parse_json_response(self, response: str) -> Dict:
        import json
        try:
            response = response.strip()
            if response.startswith('```'):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
            response = response.replace('```json', '').replace('```', '').strip()
            return json.loads(response)
        except:
            return {}

    def _fix_render_issues(self, svg_content: str, error_msg: str) -> str:
        """Fix SVG rendering issues using LLM"""
        try:
            system_prompt = "You are an SVG Debugger. Fix the syntax error causing rendering failure. Return ONLY the fixed SVG."
            prompt = f"""Render Error: {error_msg}

Broken SVG:
{svg_content}

Fix the error (e.g., matching tags, xml namespace, encoding). Return fixed SVG only."""
            
            result = self.invoke_llm(prompt, system_prompt)
            
            # Clean output
            import re
            fixed = result.replace('```svg', '').replace('```xml', '').replace('```', '').strip()
            match = re.search(r'<svg.*?</svg>', fixed, re.DOTALL)
            return match.group(0) if match else fixed
            
        except Exception as e:
            self._log(f"Fix failed: {e}", "error")
            return svg_content

    def _save_validated_artifacts(self, svg_content: str, state: SVGState):
        """Save validated SVG and render PNG"""
        try:
            import os
            output_dir = state.get("output_dir")
            if not output_dir:
                return

            sample_id = state.get("sample_id", "output")
            iteration = state.get("iteration", 0)
            
            # Save SVG
            svg_path = os.path.join(output_dir, f"{sample_id}_val_iter{iteration}.svg")
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_content)
            
            state["svg_path"] = svg_path
            self._log(f"Saved Validated SVG: file://{os.path.abspath(svg_path)}")
            
            # Save PNG (using cairosvg since we know it works if we are here)
            try:
                import cairosvg
                png_path = svg_path.replace('.svg', '.png')
                cairosvg.svg2png(bytestring=svg_content.encode('utf-8'), write_to=png_path)
                state["svg_png_path"] = png_path
                self._log(f"Saved Validated PNG: file://{os.path.abspath(png_path)}")
            except Exception as e:
                self._log(f"PNG save failed: {e}", "warning")
                
        except Exception as e:
            self._log(f"Artifact save failed: {e}", "error")