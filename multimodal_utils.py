"""
Multimodal Analyzer Utilities
==============================

辅助函数：fallback、load/save等
"""

import os
from typing import List, Dict, Any


# ========== Fallback Functions ==========

def create_fallback_svg(topic: str, scene_info: Dict, svg_dir: str, idx: int, timestamp: float) -> Dict:
    """生成fallback SVG"""
    colors = scene_info.get('color_palette', ['#00f3ff', '#764ba2', '#ffffff'])
    primary = colors[0] if len(colors) > 0 else '#00f3ff'
    secondary = colors[1] if len(colors) > 1 else '#764ba2'
    
    svg = f'''<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">
  <style>
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
    .pulse {{ animation: pulse 2s ease-in-out infinite; }}
  </style>
  
  <rect width="400" height="300" fill="#050510"/>
  
  <text x="200" y="40" font-family="sans-serif" font-size="18" 
        fill="{primary}" text-anchor="middle" class="pulse">
    {topic[:20]}
  </text>
  
  <circle cx="200" cy="150" r="50" fill="none" stroke="{primary}" stroke-width="2" class="pulse"/>
  <circle cx="200" cy="150" r="35" fill="none" stroke="{secondary}" stroke-width="1.5"/>
</svg>'''
    
    filename = f"fallback_{idx}_{int(timestamp)}.svg"
    filepath = os.path.join(svg_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(svg)
    
    return {
        'type': 'svg',
        'path': f'temp_analysis/assets/svg/{filename}',
        'svg_content': svg
    }


def create_fallback_text_content(text: str, scene_info: Dict) -> Dict:
    """降级文字内容"""
    return {
        'type': 'text',
        'text': text[:20],
        'mood': 'default',
        'use_glassmorphism': True,
        'style': {
            'background': 'rgba(0, 0, 0, 0.8)',
            'color': '#ffffff',
            'padding': '15px',
            'border_radius': '10px'
        }
    }


def create_fallback_scene_analysis() -> Dict:
    """降级场景分析（匹配新格式）"""
    return {
        'is_single_scene': True,
        'color_hierarchy': {
            'background_color': '#1a1a1a',
            'accent_color': '#3498db',
            'text_color': '#ffffff',
            'all_colors': ['#1a1a1a', '#3498db', '#ffffff', '#808080', '#2c3e50'],
            'color_weights': [0.4, 0.2, 0.15, 0.15, 0.1]
        },
        'color_metrics': {
            'saturation_level': 'medium',
            'brightness_level': 'medium',
            'temperature': 'neutral',
            'avg_saturation': 0.5,
            'avg_brightness': 0.5
        },
        'visual_complexity': 'medium',
        'design_guide': {
            'recommended_bg': '#1a1a1a',
            'recommended_accent': '#3498db',
            'recommended_text': '#ffffff',
            'svg_prompt': 'Use clean geometric shapes with moderate colors',
            'text_style': 'clean sans-serif with good contrast'
        },
        'frame_count': 0,
        # 兼容旧接口
        'color_palette': ['#1a1a1a', '#3498db', '#ffffff', '#808080', '#2c3e50'],
        'style_keywords': ['medium', 'medium']
    }


# ========== Load/Save Functions ==========

def save_transcript(transcript: List[Dict], filepath: str):
    """保存转录结果（句子级别）"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for item in transcript:
            f.write(f"{item['start']:.2f}\t{item['end']:.2f}\t{item['text']}\n")


def load_transcript(filepath: str) -> List[Dict]:
    """加载转录结果（句子级别）"""
    transcript = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                transcript.append({
                    'start': float(parts[0]),
                    'end': float(parts[1]),
                    'text': parts[2]
                })
    return transcript


def save_segments(segments: List[Dict], filepath: str):
    """保存语义段"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for seg in segments:
            f.write(f"{seg['start']:.2f}\t{seg['end']:.2f}\t{seg['text']}\n")


def load_segments(filepath: str) -> List[Dict]:
    """加载语义段"""
    segments = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                segments.append({
                    'start': float(parts[0]),
                    'end': float(parts[1]),
                    'text': parts[2]
                })
    return segments


def save_decisions(decisions: List[Dict], filepath: str):
    """保存判断结果"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for dec in decisions:
            f.write(f"{dec['start']:.2f}\t{dec['end']:.2f}\t{dec['enhancement_type']}\t{dec['text']}\n")


def load_decisions(filepath: str) -> List[Dict]:
    """加载判断结果"""
    decisions = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                decisions.append({
                    'start': float(parts[0]),
                    'end': float(parts[1]),
                    'enhancement_type': parts[2],
                    'text': parts[3],
                    'reason': 'cached'
                })
    return decisions


def save_scene_analysis(scene_info: Dict, filepath: str):
    """保存场景分析"""
    import json
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(scene_info, f, indent=2, ensure_ascii=False)


def load_scene_analysis(filepath: str) -> Dict:
    """加载场景分析"""
    import json
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# ========== Transcript Fallback ==========

def create_fallback_transcript() -> list:
    """生成fallback转录数据（句子级别）"""
    demo_sentences = [
        "Today we will explain the TCP three-way handshake mechanism.",
        "First, the client sends a SYN packet to the server.",
        "Then, the server returns a SYN-ACK packet.",
        "Finally, the client sends an ACK packet to complete the connection."
    ]
    
    transcript = []
    current_time = 0.0
    for sentence in demo_sentences:
        duration = len(sentence.split()) * 0.4
        transcript.append({
            'text': sentence,
            'start': current_time,
            'end': current_time + duration
        })
        current_time += duration + 0.5
    
    return transcript


def create_fallback_segments(transcript: list) -> list:
    """生成fallback语义段（基于句子）"""
    segments = []
    window = 10.0  # 10秒一个段
    
    current_start = 0.0 if not transcript else transcript[0]['start']
    current_sentences = []
    
    for sentence in transcript:
        if sentence['start'] - current_start > window:
            if current_sentences:
                segments.append({
                    'text': ' '.join([s['text'] for s in current_sentences]),
                    'start': current_sentences[0]['start'],
                    'end': current_sentences[-1]['end'],
                    'sentences': current_sentences.copy()
                })
            current_start = sentence['start']
            current_sentences = [sentence]
        else:
            current_sentences.append(sentence)
    
    if current_sentences:
        segments.append({
            'text': ' '.join([s['text'] for s in current_sentences]),
            'start': current_sentences[0]['start'],
            'end': current_sentences[-1]['end'],
            'sentences': current_sentences.copy()
        })
    
    return segments


def simple_classify_segment(segment: Dict) -> Dict:
    """简单关键词分类（fallback）"""
    text = segment['text']
    
    # SVG关键词
    svg_keywords = ['原理', '流程', '过程', '机制', '架构', '系统', '算法', '协议', 
                   '如何', '怎么', '握手', '请求', 'mechanism', 'process', 'architecture',
                   'system', 'algorithm', 'protocol', 'handshake', 'request', 'flow']
    # Text关键词  
    text_keywords = ['重点', '关键', '注意', '总结', '定义', '概念', '是指', '重要',
                    'key', 'important', 'note', 'summary', 'definition', 'concept']
    
    text_lower = text.lower()
    
    if any(kw in text_lower for kw in svg_keywords):
        return {
            **segment, 
            'enhancement_type': 'svg', 
            'visual_description': 'keyword-based SVG',
            'information_density': 'medium',
            'reason': 'keyword_match', 
            'confidence': 0.6
        }
    elif any(kw in text_lower for kw in text_keywords):
        return {
            **segment, 
            'enhancement_type': 'text',
            'visual_description': 'N/A',
            'information_density': 'medium',
            'reason': 'keyword_match', 
            'confidence': 0.6
        }
    else:
        return {
            **segment, 
            'enhancement_type': 'none',
            'visual_description': 'N/A',
            'information_density': 'low',
            'reason': 'no_match', 
            'confidence': 0.8
        }
