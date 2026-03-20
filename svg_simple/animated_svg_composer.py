"""
Animated SVG Composer
=====================

Deterministically composes explanatory animated SVGs from a normalized motion
plan. This avoids over-relying on one-shot LLM code generation for motion.
"""

from typing import Any, Dict, List


CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


class AnimatedSVGComposer:
    """Compose motion-grammar-specific animated SVG overlays."""

    def compose(self, brief: Dict[str, Any], motion_plan: Dict[str, Any]) -> str:
        grammar = motion_plan.get("motion_grammar", "none")
        colors = self._colors(brief)
        title = self._escape(brief.get("display_title") or brief.get("core_topic") or "Animated Concept")
        subtitle = self._escape(brief.get("display_subtitle") or brief.get("core_topic") or "")
        entities = motion_plan.get("motion_entities", [])

        grammar_dispatch = {
            "flow": self._compose_flow,
            "orbit": self._compose_orbit,
            "cycle": self._compose_cycle,
            "transform": self._compose_transform,
            "compare": self._compose_compare,
            "build": self._compose_build,
            "signal": self._compose_signal,
            "field": self._compose_field,
        }
        body = grammar_dispatch.get(grammar, self._compose_flow)(entities, title, subtitle, colors)
        return self._wrap_svg(body, colors)

    def _wrap_svg(self, body: str, colors: Dict[str, str]) -> str:
        return f'''<svg viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="glow-soft" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <style>
      text {{ font-family: system-ui, -apple-system, sans-serif; }}
      .title {{ fill: {colors["text"]}; font-size: 64px; font-weight: 900; letter-spacing: 1px; }}
      .subtitle {{ fill: {colors["secondary"]}; font-size: 42px; font-weight: 500; }}
      .label {{ fill: {colors["text"]}; font-size: 28px; font-weight: 700; }}
      .small {{ fill: rgba(255,255,255,0.76); font-size: 22px; font-weight: 500; }}
      .fade-in {{ opacity: 0; animation: fadeIn 0.8s ease forwards; }}
      .pulse {{ animation: pulse 2s ease-in-out infinite; transform-origin: center; }}
      .shimmer {{ animation: shimmer 2.4s ease-in-out infinite; }}
      .soft {{ fill-opacity: 0.10; stroke-opacity: 0.95; }}
      .line-soft {{ stroke-opacity: 0.38; }}
      .line-strong {{ stroke-opacity: 0.92; filter: url(#glow-soft); }}
      @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
      @keyframes pulse {{ 0%,100% {{ opacity: 0.7; }} 50% {{ opacity: 1; }} }}
      @keyframes shimmer {{ 0%,100% {{ opacity: 0.45; }} 50% {{ opacity: 1; }} }}
    </style>
  </defs>
  {body}
</svg>'''

    def _compose_flow(self, entities: List[Dict[str, str]], title: str, subtitle: str, colors: Dict[str, str]) -> str:
        entities = self._ensure_entities(entities, ["Input", "Transform", "Output"])
        xs = [300, 960, 1620]
        y = 520
        node_markup = []
        connector_markup = []
        particle_markup = []
        for idx, entity in enumerate(entities[:3]):
            x = xs[idx]
            node_markup.append(
                f'<g class="fade-in" style="animation-delay:{0.2 + idx * 0.25}s">'
                f'<rect x="{x-170}" y="{y-110}" rx="28" ry="28" width="340" height="220" fill="{colors["background"]}" fill-opacity="0.14" stroke="{colors["primary"]}" stroke-width="4" class="soft"/>'
                f'<text x="{x}" y="{y-12}" class="label" text-anchor="middle">{self._escape(entity["label"])}</text>'
                f'<text x="{x}" y="{y+38}" class="small" text-anchor="middle">{self._escape(entity["role"].replace("_", " ").title())}</text>'
                f'</g>'
            )
            if idx < 2:
                x1 = x + 170
                x2 = xs[idx + 1] - 170
                connector_markup.append(
                    f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{colors["secondary"]}" stroke-width="6" class="line-soft fade-in" style="animation-delay:{0.6 + idx * 0.5}s"/>'
                )
                particle_markup.append(
                    f'<circle r="12" fill="{colors["secondary"]}" filter="url(#glow)">'
                    f'<animate attributeName="cx" values="{x1};{x2}" dur="2.4s" begin="{1.0 + idx * 0.8}s" repeatCount="indefinite"/>'
                    f'<animate attributeName="cy" values="{y};{y}" dur="2.4s" begin="{1.0 + idx * 0.8}s" repeatCount="indefinite"/>'
                    f'<animate attributeName="opacity" values="0;1;1;0" dur="2.4s" begin="{1.0 + idx * 0.8}s" repeatCount="indefinite"/>'
                    f'</circle>'
                )
        return f'''
  <g class="fade-in"><text x="960" y="120" class="title" text-anchor="middle">{title}</text><text x="960" y="178" class="subtitle" text-anchor="middle">{subtitle}</text></g>
  {"".join(connector_markup)}
  {"".join(node_markup)}
  <g>{"".join(particle_markup)}</g>
'''

    def _compose_orbit(self, entities: List[Dict[str, str]], title: str, subtitle: str, colors: Dict[str, str]) -> str:
        entities = self._ensure_entities(entities, ["Core Body", "Primary Orbiter", "Secondary Orbiter"])
        center_x, center_y = 960, 540
        orbit_specs = [(170, entities[1]["label"], 5.8), (270, entities[2]["label"], 9.5)]
        orbit_groups = []
        for idx, (radius, label, dur) in enumerate(orbit_specs):
            orbit_groups.append(
                f'<circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="none" stroke="{colors["secondary"]}" stroke-width="3" class="line-soft fade-in" style="animation-delay:{0.5 + idx * 0.2}s"/>'
                f'<g transform="translate({center_x},{center_y})">'
                f'<g>'
                f'<animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="{dur}s" repeatCount="indefinite"/>'
                f'<circle cx="{radius}" cy="0" r="{28 - idx * 6}" fill="{colors["primary"]}" filter="url(#glow)" class="pulse"/>'
                f'<text x="{radius}" y="56" class="small" text-anchor="middle">{self._escape(label)}</text>'
                f'</g></g>'
            )
        return f'''
  <g class="fade-in"><text x="960" y="120" class="title" text-anchor="middle">{title}</text><text x="960" y="178" class="subtitle" text-anchor="middle">{subtitle}</text></g>
  <g class="fade-in" style="animation-delay:0.2s">
    <circle cx="{center_x}" cy="{center_y}" r="98" fill="{colors["background"]}" fill-opacity="0.16" stroke="{colors["text"]}" stroke-width="5"/>
    <circle cx="{center_x}" cy="{center_y}" r="72" fill="{colors["primary"]}" fill-opacity="0.34" filter="url(#glow)"/>
    <text x="{center_x}" y="{center_y+10}" class="label" text-anchor="middle">{self._escape(entities[0]["label"])}</text>
  </g>
  {"".join(orbit_groups)}
'''

    def _compose_cycle(self, entities: List[Dict[str, str]], title: str, subtitle: str, colors: Dict[str, str]) -> str:
        entities = self._ensure_entities(entities, ["Trigger", "Process", "Feedback", "Reset"])
        positions = [(960, 290), (1320, 540), (960, 790), (600, 540)]
        nodes = []
        for idx, (entity, (x, y)) in enumerate(zip(entities[:4], positions)):
            nodes.append(
                f'<g class="fade-in" style="animation-delay:{0.2 + idx * 0.2}s">'
                f'<circle cx="{x}" cy="{y}" r="92" fill="{colors["background"]}" fill-opacity="0.14" stroke="{colors["primary"]}" stroke-width="4"/>'
                f'<text x="{x}" y="{y+10}" class="label" text-anchor="middle">{self._escape(entity["label"])}</text>'
                f'</g>'
            )
        return f'''
  <g class="fade-in"><text x="960" y="120" class="title" text-anchor="middle">{title}</text><text x="960" y="178" class="subtitle" text-anchor="middle">{subtitle}</text></g>
  <circle cx="960" cy="540" r="330" fill="none" stroke="{colors["secondary"]}" stroke-width="5" stroke-dasharray="18 18" class="line-soft"/>
  <g transform="translate(960,540)">
    <g><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="7.5s" repeatCount="indefinite"/><circle cx="330" cy="0" r="15" fill="{colors["secondary"]}" filter="url(#glow)"/></g>
  </g>
  {"".join(nodes)}
'''

    def _compose_transform(self, entities: List[Dict[str, str]], title: str, subtitle: str, colors: Dict[str, str]) -> str:
        entities = self._ensure_entities(entities, ["State A", "State B", "State C"])
        return f'''
  <g class="fade-in"><text x="960" y="120" class="title" text-anchor="middle">{title}</text><text x="960" y="178" class="subtitle" text-anchor="middle">{subtitle}</text></g>
  <g class="fade-in" style="animation-delay:0.2s">
    <rect x="270" y="360" width="360" height="280" rx="32" fill="{colors["background"]}" fill-opacity="0.14" stroke="{colors["primary"]}" stroke-width="4"/>
    <text x="450" y="515" class="label" text-anchor="middle">{self._escape(entities[0]["label"])}</text>
  </g>
  <g class="fade-in" style="animation-delay:1.0s">
    <polygon points="960,330 1180,500 960,670 740,500" fill="{colors["secondary"]}" fill-opacity="0.12" stroke="{colors["secondary"]}" stroke-width="4"/>
    <text x="960" y="510" class="label" text-anchor="middle">{self._escape(entities[1]["label"])}</text>
  </g>
  <g class="fade-in" style="animation-delay:1.8s">
    <circle cx="1470" cy="500" r="160" fill="{colors["background"]}" fill-opacity="0.14" stroke="{colors["text"]}" stroke-width="4"/>
    <text x="1470" y="510" class="label" text-anchor="middle">{self._escape(entities[2]["label"])}</text>
  </g>
  <circle r="12" fill="{colors["secondary"]}" filter="url(#glow)">
    <animate attributeName="cx" values="630;740;1180;1310" dur="3.6s" begin="1.0s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="500;500;500;500" dur="3.6s" begin="1.0s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;1;1;1;0" dur="3.6s" begin="1.0s" repeatCount="indefinite"/>
  </circle>
'''

    def _compose_compare(self, entities: List[Dict[str, str]], title: str, subtitle: str, colors: Dict[str, str]) -> str:
        entities = self._ensure_entities(entities, ["Baseline", "New Method", "Delta"])
        return f'''
  <g class="fade-in"><text x="960" y="120" class="title" text-anchor="middle">{title}</text><text x="960" y="178" class="subtitle" text-anchor="middle">{subtitle}</text></g>
  <g class="fade-in" style="animation-delay:0.3s">
    <rect x="180" y="260" width="640" height="520" rx="30" fill="{colors["background"]}" fill-opacity="0.12" stroke="{colors["text"]}" stroke-width="4"/>
    <text x="500" y="338" class="label" text-anchor="middle">{self._escape(entities[0]["label"])}</text>
    <line x1="300" y1="650" x2="700" y2="500" stroke="{colors["text"]}" stroke-width="5" class="line-soft"/>
  </g>
  <g class="fade-in" style="animation-delay:0.8s">
    <rect x="1100" y="260" width="640" height="520" rx="30" fill="{colors["background"]}" fill-opacity="0.12" stroke="{colors["primary"]}" stroke-width="4"/>
    <text x="1420" y="338" class="label" text-anchor="middle">{self._escape(entities[1]["label"])}</text>
    <line x1="1220" y1="650" x2="1620" y2="420" stroke="{colors["secondary"]}" stroke-width="5" class="line-strong"/>
  </g>
  <rect x="920" y="260" width="80" height="520" fill="{colors["secondary"]}" fill-opacity="0.12"/>
  <rect x="920" y="260" width="12" height="520" fill="{colors["secondary"]}" filter="url(#glow)">
    <animate attributeName="y" values="260;720;260" dur="4s" begin="1.2s" repeatCount="indefinite"/>
  </rect>
'''

    def _compose_build(self, entities: List[Dict[str, str]], title: str, subtitle: str, colors: Dict[str, str]) -> str:
        entities = self._ensure_entities(entities, ["Foundation", "Layer Two", "Layer Three", "Top Layer"])
        layers = []
        base_y = 760
        for idx, entity in enumerate(entities[:4]):
            width = 900 - idx * 140
            x = 960 - width / 2
            y = base_y - idx * 130
            layers.append(
                f'<g class="fade-in" style="animation-delay:{0.4 + idx * 0.45}s">'
                f'<rect x="{x:.0f}" y="{y:.0f}" width="{width:.0f}" height="96" rx="24" fill="{colors["background"]}" fill-opacity="0.14" stroke="{colors["primary"]}" stroke-width="4"/>'
                f'<text x="960" y="{y+58:.0f}" class="label" text-anchor="middle">{self._escape(entity["label"])}</text>'
                f'</g>'
            )
        return f'''
  <g class="fade-in"><text x="960" y="120" class="title" text-anchor="middle">{title}</text><text x="960" y="178" class="subtitle" text-anchor="middle">{subtitle}</text></g>
  {"".join(layers)}
'''

    def _compose_signal(self, entities: List[Dict[str, str]], title: str, subtitle: str, colors: Dict[str, str]) -> str:
        entities = self._ensure_entities(entities, ["Source", "Relay", "Target"])
        positions = [(320, 540), (960, 360), (1600, 540)]
        nodes = []
        for idx, (entity, (x, y)) in enumerate(zip(entities[:3], positions)):
            nodes.append(
                f'<g class="fade-in" style="animation-delay:{0.2 + idx * 0.2}s">'
                f'<circle cx="{x}" cy="{y}" r="84" fill="{colors["background"]}" fill-opacity="0.12" stroke="{colors["primary"]}" stroke-width="4"/>'
                f'<text x="{x}" y="{y+10}" class="label" text-anchor="middle">{self._escape(entity["label"])}</text>'
                f'</g>'
            )
        return f'''
  <g class="fade-in"><text x="960" y="120" class="title" text-anchor="middle">{title}</text><text x="960" y="178" class="subtitle" text-anchor="middle">{subtitle}</text></g>
  <path d="M 404 512 C 590 430, 700 400, 876 380" fill="none" stroke="{colors["secondary"]}" stroke-width="5" class="line-soft"/>
  <path d="M 1044 380 C 1210 410, 1310 430, 1516 512" fill="none" stroke="{colors["secondary"]}" stroke-width="5" class="line-soft"/>
  {"".join(nodes)}
  <circle r="10" fill="{colors["secondary"]}" filter="url(#glow)">
    <animate attributeName="cx" values="404;876;1516" dur="3.2s" begin="1.0s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="512;380;512" dur="3.2s" begin="1.0s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;1;1;0" dur="3.2s" begin="1.0s" repeatCount="indefinite"/>
  </circle>
'''

    def _compose_field(self, entities: List[Dict[str, str]], title: str, subtitle: str, colors: Dict[str, str]) -> str:
        return f'''
  <g class="fade-in"><text x="960" y="120" class="title" text-anchor="middle">{title}</text><text x="960" y="178" class="subtitle" text-anchor="middle">{subtitle}</text></g>
  <g class="fade-in" style="animation-delay:0.3s">
    <circle cx="960" cy="540" r="120" fill="{colors["primary"]}" fill-opacity="0.12" stroke="{colors["primary"]}" stroke-width="4" class="pulse"/>
    <circle cx="960" cy="540" r="220" fill="none" stroke="{colors["secondary"]}" stroke-width="3" class="line-soft">
      <animate attributeName="r" values="180;280;180" dur="4s" begin="0s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.3;0.9;0.3" dur="4s" begin="0s" repeatCount="indefinite"/>
    </circle>
    <circle cx="960" cy="540" r="320" fill="none" stroke="{colors["secondary"]}" stroke-width="3" class="line-soft">
      <animate attributeName="r" values="280;380;280" dur="4s" begin="1.2s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.2;0.8;0.2" dur="4s" begin="1.2s" repeatCount="indefinite"/>
    </circle>
  </g>
'''

    def _ensure_entities(self, entities: List[Dict[str, str]], fallback_labels: List[str]) -> List[Dict[str, str]]:
        if entities:
            return entities
        return [
            {"id": f"entity_{idx}", "label": label, "role": "stage" if idx else "anchor"}
            for idx, label in enumerate(fallback_labels)
        ]

    def _colors(self, brief: Dict[str, Any]) -> Dict[str, str]:
        colors = brief.get("color_instructions", {})
        return {
            "background": colors.get("background", "#0d1117"),
            "primary": colors.get("primary_accent", "#58a6ff"),
            "secondary": colors.get("secondary_accent", "#64ffda"),
            "text": colors.get("text", "#e6edf3"),
        }

    def _escape(self, value: Any) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
