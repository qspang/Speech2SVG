"""
Layout Expert Agent
====================

布局专家Agent — 为SVG选择最佳布局并生成坐标骨架

输入: state["concepts"] (entities + relationships + layout_type hint)
输出: state["layout_plan_detailed"] (布局类型 + 实体坐标 + 连接路径)

使用LLM选择布局类型，算法生成坐标（确保不溢出画布）
"""

import math
from typing import Dict, List, Tuple
from base_agent import BaseAgent
from state import SVGState

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
MARGIN = 180
SAFE_X = (MARGIN, CANVAS_WIDTH - MARGIN)
SAFE_Y = (MARGIN, CANVAS_HEIGHT - MARGIN)
CENTER = (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2)


# ═══════════════════════════════════════════════════════════════
# 布局算法库 (10+ 种布局)
# ═══════════════════════════════════════════════════════════════

def _layout_flow(n: int) -> List[Dict]:
    """水平流式: A → B → C"""
    usable_w = SAFE_X[1] - SAFE_X[0]
    cy = CENTER[1]
    positions = []
    for i in range(n):
        x = SAFE_X[0] + int(i * usable_w / max(n - 1, 1)) if n > 1 else CENTER[0]
        positions.append({"x": x, "y": cy})
    return positions


def _layout_hierarchy(n: int) -> List[Dict]:
    """层级树: 顶部1个, 中间2个, 底部N个"""
    positions = []
    if n <= 1:
        return [{"x": CENTER[0], "y": CENTER[1]}]
    
    # 分层
    layers = []
    remaining = n
    layer_size = 1
    while remaining > 0:
        count = min(layer_size, remaining)
        layers.append(count)
        remaining -= count
        layer_size = min(layer_size * 2, 4)
    
    usable_h = SAFE_Y[1] - SAFE_Y[0]
    for layer_idx, count in enumerate(layers):
        y = SAFE_Y[0] + int(layer_idx * usable_h / max(len(layers) - 1, 1))
        usable_w = SAFE_X[1] - SAFE_X[0]
        for j in range(count):
            x = SAFE_X[0] + int((j + 0.5) * usable_w / count) if count > 0 else CENTER[0]
            positions.append({"x": x, "y": y})
    
    return positions[:n]


def _layout_radial(n: int) -> List[Dict]:
    """放射: 中心+周围环绕"""
    if n <= 1:
        return [{"x": CENTER[0], "y": CENTER[1]}]
    
    positions = [{"x": CENTER[0], "y": CENTER[1]}]  # 中心
    radius = min(SAFE_X[1] - CENTER[0], SAFE_Y[1] - CENTER[1]) * 0.7
    for i in range(n - 1):
        angle = 2 * math.pi * i / (n - 1) - math.pi / 2
        x = CENTER[0] + int(radius * math.cos(angle))
        y = CENTER[1] + int(radius * math.sin(angle))
        positions.append({"x": x, "y": y})
    
    return positions


def _layout_cycle(n: int) -> List[Dict]:
    """圆环循环: 所有元素均匀分布在圆上"""
    if n <= 1:
        return [{"x": CENTER[0], "y": CENTER[1]}]
    
    radius = min(SAFE_X[1] - CENTER[0], SAFE_Y[1] - CENTER[1]) * 0.6
    positions = []
    for i in range(n):
        angle = 2 * math.pi * i / n - math.pi / 2
        x = CENTER[0] + int(radius * math.cos(angle))
        y = CENTER[1] + int(radius * math.sin(angle))
        positions.append({"x": x, "y": y})
    
    return positions


def _layout_comparison(n: int) -> List[Dict]:
    """对比: 左右分屏"""
    if n <= 1:
        return [{"x": CENTER[0], "y": CENTER[1]}]
    
    left_count = n // 2
    right_count = n - left_count
    positions = []
    
    left_x = SAFE_X[0] + (CENTER[0] - SAFE_X[0]) // 2
    right_x = CENTER[0] + (SAFE_X[1] - CENTER[0]) // 2
    
    usable_h = SAFE_Y[1] - SAFE_Y[0]
    for i in range(left_count):
        y = SAFE_Y[0] + int((i + 0.5) * usable_h / left_count)
        positions.append({"x": left_x, "y": y})
    for i in range(right_count):
        y = SAFE_Y[0] + int((i + 0.5) * usable_h / right_count)
        positions.append({"x": right_x, "y": y})
    
    return positions


def _layout_grid(n: int) -> List[Dict]:
    """网格: 均匀矩阵"""
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    
    usable_w = SAFE_X[1] - SAFE_X[0]
    usable_h = SAFE_Y[1] - SAFE_Y[0]
    
    positions = []
    for i in range(n):
        row = i // cols
        col = i % cols
        x = SAFE_X[0] + int((col + 0.5) * usable_w / cols)
        y = SAFE_Y[0] + int((row + 0.5) * usable_h / rows)
        positions.append({"x": x, "y": y})
    
    return positions


def _layout_pyramid(n: int) -> List[Dict]:
    """金字塔: 顶部1, 往下递增"""
    if n <= 1:
        return [{"x": CENTER[0], "y": SAFE_Y[0]}]
    
    layers = []
    remaining = n
    size = 1
    while remaining > 0:
        layers.append(min(size, remaining))
        remaining -= size
        size += 1
    
    usable_h = SAFE_Y[1] - SAFE_Y[0]
    usable_w = SAFE_X[1] - SAFE_X[0]
    positions = []
    
    for layer_idx, count in enumerate(layers):
        y = SAFE_Y[0] + int(layer_idx * usable_h / max(len(layers) - 1, 1))
        for j in range(count):
            x = CENTER[0] + int((j - (count - 1) / 2) * usable_w / max(count, 1) * 0.7)
            positions.append({"x": x, "y": y})
    
    return positions[:n]


def _layout_timeline(n: int) -> List[Dict]:
    """时间线: 水平线 + 上下交替"""
    usable_w = SAFE_X[1] - SAFE_X[0]
    positions = []
    for i in range(n):
        x = SAFE_X[0] + int(i * usable_w / max(n - 1, 1)) if n > 1 else CENTER[0]
        y = CENTER[1] + ((-1) ** i) * 120  # 上下交替偏移
        positions.append({"x": x, "y": y})
    return positions


def _layout_orbit(n: int) -> List[Dict]:
    """轨道: 中心 + 多层环"""
    if n <= 1:
        return [{"x": CENTER[0], "y": CENTER[1]}]
    
    positions = [{"x": CENTER[0], "y": CENTER[1]}]
    
    # 分配到多层轨道
    remaining = n - 1
    orbit = 1
    max_radius = min(SAFE_X[1] - CENTER[0], SAFE_Y[1] - CENTER[1])
    
    while remaining > 0:
        orbit_count = min(4 + orbit * 2, remaining)
        radius = max_radius * (0.3 + 0.25 * orbit)
        for i in range(orbit_count):
            angle = 2 * math.pi * i / orbit_count - math.pi / 2
            x = CENTER[0] + int(radius * math.cos(angle))
            y = CENTER[1] + int(radius * math.sin(angle))
            positions.append({"x": x, "y": y})
        remaining -= orbit_count
        orbit += 1
    
    return positions[:n]


def _layout_venn(n: int) -> List[Dict]:
    """维恩图: 重叠圆心位置"""
    if n <= 1:
        return [{"x": CENTER[0], "y": CENTER[1]}]
    
    overlap_radius = 200
    positions = []
    for i in range(n):
        angle = 2 * math.pi * i / n - math.pi / 2
        x = CENTER[0] + int(overlap_radius * math.cos(angle))
        y = CENTER[1] + int(overlap_radius * math.sin(angle))
        positions.append({"x": x, "y": y})
    
    return positions


def _layout_staircase(n: int) -> List[Dict]:
    """阶梯: 左上→右下对角线"""
    usable_w = SAFE_X[1] - SAFE_X[0]
    usable_h = SAFE_Y[1] - SAFE_Y[0]
    
    positions = []
    for i in range(n):
        t = i / max(n - 1, 1)
        x = SAFE_X[0] + int(t * usable_w)
        y = SAFE_Y[0] + int(t * usable_h)
        positions.append({"x": x, "y": y})
    
    return positions


def _layout_splitscreen(n: int) -> List[Dict]:
    """分屏: 左半和右半各一组, 中间留空"""
    if n <= 1:
        return [{"x": CENTER[0], "y": CENTER[1]}]
    
    left_n = (n + 1) // 2
    right_n = n - left_n
    
    positions = []
    usable_h = SAFE_Y[1] - SAFE_Y[0]
    
    for i in range(left_n):
        y = SAFE_Y[0] + int((i + 0.5) * usable_h / left_n)
        positions.append({"x": SAFE_X[0] + 200, "y": y})
    
    for i in range(right_n):
        y = SAFE_Y[0] + int((i + 0.5) * usable_h / right_n)
        positions.append({"x": SAFE_X[1] - 200, "y": y})
    
    return positions


def _layout_scatter(n: int) -> List[Dict]:
    """散射: 黄金分割螺旋"""
    golden = (1 + math.sqrt(5)) / 2
    max_r = min(SAFE_X[1] - CENTER[0], SAFE_Y[1] - CENTER[1]) * 0.8
    
    positions = []
    for i in range(n):
        angle = 2 * math.pi * golden * i
        r = max_r * math.sqrt((i + 1) / n) * 0.9
        x = CENTER[0] + int(r * math.cos(angle))
        y = CENTER[1] + int(r * math.sin(angle))
        positions.append({"x": x, "y": y})
    
    return positions


# 布局注册表
LAYOUT_REGISTRY = {
    "flow": _layout_flow,
    "hierarchy": _layout_hierarchy,
    "radial": _layout_radial,
    "cycle": _layout_cycle,
    "comparison": _layout_comparison,
    "grid": _layout_grid,
    "pyramid": _layout_pyramid,
    "timeline": _layout_timeline,
    "orbit": _layout_orbit,
    "venn": _layout_venn,
    "staircase": _layout_staircase,
    "splitscreen": _layout_splitscreen,
    "scatter": _layout_scatter,
}


class LayoutExpertAgent(BaseAgent):
    """布局专家Agent — 选择布局类型 + 生成坐标骨架"""
    
    def __init__(self, llm_type: str = "claude-sonnet-4-5-20250929"):
        super().__init__("layout_expert", llm_type)
        self.role_description = "Select optimal layout and generate coordinate skeleton"
        self.capabilities = ["layout_selection", "coordinate_generation"]
    
    def execute(self, state: SVGState) -> SVGState:
        """选择布局并生成坐标"""
        self._log("Layout Planning...")
        
        concepts = state.get("concepts", {})
        entities = concepts.get("entities", [])
        relationships = concepts.get("relationships", [])
        layout_hint = concepts.get("layout_type", "")
        
        n = len(entities)
        if n == 0:
            state["layout_plan_detailed"] = {
                "layout_type": "flow",
                "entity_positions": [],
                "focal_point": CENTER,
                "connection_style": "straight"
            }
            return state
        
        # Step 1: LLM 选择最佳布局类型
        layout_type = self._select_layout(entities, relationships, layout_hint)
        
        # Step 2: 算法生成坐标
        layout_fn = LAYOUT_REGISTRY.get(layout_type, _layout_flow)
        raw_positions = layout_fn(n)
        
        # Step 3: 将位置绑定到实体
        entity_positions = []
        for i, pos in enumerate(raw_positions):
            label = entities[i] if isinstance(entities[i], str) else entities[i].get("label", f"Node{i}")
            entity_positions.append({
                "label": label,
                "x": pos["x"],
                "y": pos["y"],
                "index": i
            })
        
        # Step 4: 连接线风格
        connection_style = self._pick_connection_style(layout_type)
        
        # 计算视觉焦点
        focal_x = sum(p["x"] for p in raw_positions) // max(n, 1)
        focal_y = sum(p["y"] for p in raw_positions) // max(n, 1)
        
        plan = {
            "layout_type": layout_type,
            "entity_positions": entity_positions,
            "focal_point": {"x": focal_x, "y": focal_y},
            "connection_style": connection_style
        }
        
        state["layout_plan_detailed"] = plan
        state["layout_type"] = layout_type  # 覆盖 concept_analyzer 的 hint
        
        self._log(f"  Layout: {layout_type} | Entities: {n} | Focal: ({focal_x}, {focal_y})")
        
        self.record_decision(
            state, "layout_planning",
            f"Layout: {layout_type} for {n} entities",
            f"Connection style: {connection_style}"
        )
        
        return state
    
    def can_contribute(self, state: SVGState) -> Tuple[bool, float]:
        phase = state.get("phase", "")
        if phase == "layout_planning":
            return True, 0.95
        return False, 0.0
    
    def _select_layout(self, entities: List, relationships: List, hint: str) -> str:
        """用LLM选择最佳布局"""
        try:
            available = ", ".join(LAYOUT_REGISTRY.keys())
            
            system_prompt = f"""You are a Layout Selection Expert. Choose the BEST layout for SVG visualization.

Available layouts: {available}

**LAYOUT GUIDE — match content semantics:**
- flow: sequential process A→B→C, pipeline
- hierarchy: tree, org chart, layered architecture (top→bottom)
- radial: central concept with orbiting sub-concepts
- cycle: feedback loops, recurring process, lifecycle
- comparison: versus, before/after, pros/cons (left vs right)
- grid: matrix, feature table, categorized items
- pyramid: hierarchical importance (top=most important)
- timeline: chronological events, version history (zigzag)
- orbit: planetary/satellite model, central+rings
- venn: overlapping concepts, shared properties
- staircase: progressive steps, ascending complexity
- splitscreen: two distinct groups, dual perspectives
- scatter: independent items, mind-map, no clear hierarchy

**ANTI-FLOW BIAS:** DO NOT always pick "flow". Only use "flow" when the content
is genuinely a sequential pipeline. For most content, another layout is better.

Output JSON:
{{"layout": "layout_name", "reason": "10 words max"}}"""
            
            entity_str = ", ".join([
                e if isinstance(e, str) else e.get("label", "?")
                for e in entities[:8]
            ])
            rel_str = ", ".join([
                f"{r.get('from','?')}→{r.get('to','?')}"
                for r in relationships[:6]
                if isinstance(r, dict)
            ])
            
            prompt = f"""Entities: [{entity_str}]
Relationships: [{rel_str}]
Hint (may override): {hint}

Pick the BEST layout. Return JSON only."""
            
            result = self.invoke_llm(prompt, system_prompt)
            parsed = self.parse_json_response(result)
            
            layout = parsed.get("layout", hint or "radial")
            
            # 验证是合法类型
            if layout not in LAYOUT_REGISTRY:
                layout = hint if hint in LAYOUT_REGISTRY else "radial"
            
            return layout
            
        except Exception as e:
            self._log(f"Layout selection failed: {e}", "warning")
            return hint if hint in LAYOUT_REGISTRY else "radial"
    
    def _pick_connection_style(self, layout_type: str) -> str:
        """根据布局类型选择连接线风格"""
        style_map = {
            "flow": "arrow",
            "hierarchy": "straight",
            "radial": "curved",
            "cycle": "curved-arrow",
            "comparison": "dashed",
            "grid": "straight",
            "pyramid": "straight",
            "timeline": "dotted-arrow",
            "orbit": "curved",
            "venn": "none",
            "staircase": "arrow",
            "splitscreen": "dashed",
            "scatter": "curved",
        }
        return style_map.get(layout_type, "straight")
    
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
