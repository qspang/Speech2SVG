"""
Configuration - 系统配置
=========================

系统各项配置参数
"""

# ========== 视频分析配置 ==========
VIDEO_ANALYSIS = {
    # 关键帧提取
    'keyframe_interval': 2.0,  # 关键帧提取间隔（秒）
    'scene_change_threshold': 0.3,  # 场景变化阈值
    
    # 分段配置
    'min_segment_duration': 3.0,  # 最小片段时长（秒）
    'max_segment_duration': 30.0,  # 最大片段时长（秒）
    
    # 聚类配置
    'similarity_threshold': 0.7,  # 相似度阈值
    'min_cluster_size': 2,  # 最小聚类大小
    
    # 高光检测
    'highlight_threshold': 0.6,  # 高光分数阈值
    'enable_audio_analysis': False,  # TODO: 音频分析
    'enable_motion_analysis': False,  # TODO: 运动分析
}

# ========== 多模态分析配置 ==========
MULTIMODAL_ANALYSIS = {
    # 字幕分析
    'subtitle_importance_threshold': 0.6,  # 字幕重要性阈值
    'enable_keyword_extraction': False,  # TODO: 关键词提取
    'enable_topic_modeling': False,  # TODO: 主题建模
    
    # 融合策略
    'fusion_weights': {
        'highlight': 0.4,
        'subtitle': 0.4,
        'visual': 0.2
    },
    
    # 去重配置
    'min_time_gap': 3.0,  # 增强点最小时间间隔（秒）
}

# ========== 布局配置 ==========
LAYOUT = {
    # 布局策略
    'strategy': 'fallback',  # fallback | smart | grid | adaptive
    
    # 边距和间距
    'margin': 20,  # 画面边距（像素）
    'min_spacing': 30,  # 容器间最小间距（像素）
    
    # Z-index
    'z_index_base': 1000,
    'z_index_step': 10,
    
    # 动画
    'default_animation': 'fade-in',
    'animation_duration': 0.5,  # 秒
    
    # 预定义位置（fallback模式）
    'fallback_positions': [
        {'x': 50, 'y': 50, 'anchor': 'top-left'},
        {'x': 1870, 'y': 50, 'anchor': 'top-right'},
        {'x': 50, 'y': 1030, 'anchor': 'bottom-left'},
        {'x': 1870, 'y': 1030, 'anchor': 'bottom-right'},
    ]
}

# ========== 容器配置 ==========
CONTAINER = {
    # 默认尺寸（像素）
    'default_sizes': {
        'svg_animation': {'width': 400, 'height': 300},
        'chart': {'width': 500, 'height': 350},
        'text_card': {'width': 350, 'height': 200},
        'annotation': {'width': 300, 'height': 150},
        'image': {'width': 400, 'height': 300},
        'video': {'width': 480, 'height': 270},
    },
    
    # 默认显示时长（秒）
    'default_duration': 5.0,
    
    # 内容类型优先级
    'content_type_priority': [
        'svg_animation',
        'chart',
        'image',
        'text_card',
        'annotation'
    ]
}

# ========== SVG Agent集成配置 ==========
SVG_AGENT = {
    # SVG Agent路径
    'agent_path': None,  # 自动检测
    
    # 默认参数
    'default_style': 'educational',
    'enable_animation': True,
    'animation_duration': 5.0,
    
    # 批处理
    'batch_size': 5,
    'enable_parallel': False,
}

# ========== 输出配置 ==========
OUTPUT = {
    # 目录结构
    'base_dir': './enhanced_videos',
    'create_timestamp_folder': True,
    
    # 文件命名
    'html_filename': 'enhanced_video.html',
    'config_filename': 'enhancement_config.json',
    
    # 资源目录
    'assets_dir': 'assets',
    'svg_dir': 'assets/svg',
    'images_dir': 'assets/images',
    'videos_dir': 'assets/videos',
}

# ========== HTML生成配置 ==========
HTML = {
    # 视频播放器
    'enable_controls': True,
    'autoplay': False,
    'loop': False,
    
    # 容器控制
    'containers_enabled_by_default': True,
    'show_debug_info': False,
    
    # 快捷键
    'keyboard_shortcuts': {
        'play_pause': ' ',  # 空格键
        'toggle_containers': 'c',
        'next_container': 'n',
        'prev_container': 'p'
    }
}

# ========== 开发配置 ==========
DEV = {
    # 调试模式
    'debug': False,
    'verbose': True,
    
    # 测试模式
    'use_mock_data': False,
    'skip_video_processing': False,
    
    # 日志
    'enable_logging': True,
    'log_file': None,  # None表示输出到控制台
}

# ========== 性能配置 ==========
PERFORMANCE = {
    # 多线程
    'enable_multiprocessing': False,
    'max_workers': 4,
    
    # 缓存
    'enable_cache': True,
    'cache_dir': './.cache',
    
    # 限制
    'max_containers_per_video': 50,
    'max_concurrent_generations': 3,
}


def get_config(section: str = None) -> dict:
    """
    获取配置
    
    Args:
        section: 配置节名称，None表示获取所有配置
        
    Returns:
        配置字典
    """
    if section is None:
        return {
            'video_analysis': VIDEO_ANALYSIS,
            'multimodal_analysis': MULTIMODAL_ANALYSIS,
            'layout': LAYOUT,
            'container': CONTAINER,
            'svg_agent': SVG_AGENT,
            'output': OUTPUT,
            'html': HTML,
            'dev': DEV,
            'performance': PERFORMANCE,
        }
    
    sections = {
        'video_analysis': VIDEO_ANALYSIS,
        'multimodal_analysis': MULTIMODAL_ANALYSIS,
        'layout': LAYOUT,
        'container': CONTAINER,
        'svg_agent': SVG_AGENT,
        'output': OUTPUT,
        'html': HTML,
        'dev': DEV,
        'performance': PERFORMANCE,
    }
    
    if section not in sections:
        raise ValueError(f"Unknown config section: {section}")
    
    return sections[section]


def update_config(section: str, updates: dict):
    """
    更新配置
    
    Args:
        section: 配置节名称
        updates: 更新字典
    """
    sections = {
        'video_analysis': VIDEO_ANALYSIS,
        'multimodal_analysis': MULTIMODAL_ANALYSIS,
        'layout': LAYOUT,
        'container': CONTAINER,
        'svg_agent': SVG_AGENT,
        'output': OUTPUT,
        'html': HTML,
        'dev': DEV,
        'performance': PERFORMANCE,
    }
    
    if section not in sections:
        raise ValueError(f"Unknown config section: {section}")
    
    sections[section].update(updates)
