# SVG Agent - FUI风格技术动画生成器

## 🎯 核心功能

SVG Agent是一个专门生成**FUI（Future User Interface）风格技术动画SVG**的多智能体系统。

### 什么是FUI风格？

- **暗色主题**：背景 #050510
- **霓虹色彩**：青色 #00f3ff（主色）、琥珀色 #ffaa00（激活态）
- **线框美学**：细线条（1-2px）、空心形状、wireframe几何
- **发光效果**：使用SVG滤镜实现霓虹辉光
- **数据驱动**：类似科幻电影中的全息界面

## 🚀 快速开始

### 方式1：命令行（最简单）

```bash
cd svg_agent

# 生成单个SVG
python main.py "TCP三次握手原理"

# 查看生成的SVG（会自动保存到./svg_output/）
open ./svg_output/svg_*.svg
```

### 方式2：交互模式

```bash
cd svg_agent
python main.py --interactive

# 然后输入你想可视化的技术概念
输入文本 > TCP三次握手原理
输入文本 > HTTP请求响应流程
输入文本 > quit
```

### 方式3：Python代码

```python
from svg_agent import generate_svg_from_text

result = generate_svg_from_text(
    text_input="TCP三次握手原理",
    output_dir="./my_output"
)

print(f"生成的SVG: {result['svg_path']}")
print(f"质量评分: {result['score']}/10")
```

## 📊 支持的可视化类型

### 自动识别布局类型

系统会根据输入自动判断最佳布局：

- **Timeline（时间线）**：适合流程、步骤（如：TCP握手、HTTP请求）
- **Cycle（循环）**：适合周期性过程（如：事件循环、生命周期）
- **Hierarchy（层级）**：适合树形结构（如：OSI七层、组织架构）
- **Network（网络）**：适合网状关系（如：分布式系统、P2P网络）

### 示例输入

```bash
# 网络协议
python main.py "TCP三次握手原理"
python main.py "HTTP请求响应流程"
python main.py "DNS域名解析过程"

# 系统架构
python main.py "微服务架构通信"
python main.py "分布式系统CAP理论"
python main.py "消息队列工作原理"

# 算法流程
python main.py "快速排序算法步骤"
python main.py "二叉搜索树遍历"
python main.py "动态规划求解过程"

# 技术原理
python main.py "区块链共识机制"
python main.py "OAuth 2.0认证流程"
python main.py "Docker容器化原理"
```

## 🎨 生成的SVG特点

### 1. FUI技术美学

```svg
<!-- 暗色背景 -->
<rect width="800" height="500" fill="#050510"/>

<!-- 霓虹线条 -->
<line stroke="#00f3ff" stroke-width="1"/>

<!-- 发光效果 -->
<filter id="glow">
  <feGaussianBlur stdDeviation="4"/>
  ...
</filter>
```

### 2. CSS动画（无需JavaScript）

```css
@keyframes flow {
  0% { stroke-dashoffset: 1000; }
  100% { stroke-dashoffset: 0; }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
```

### 3. 几何化视觉隐喻

- **服务器** → 塔状机架
- **客户端** → 显示器轮廓
- **数据库** → 圆柱堆叠
- **进程** → 六边形
- **数据流** → 虚线+移动点
- **安全** → 盾牌+锁
- **思想** → 发光圆+射线

## 🏗️ 系统架构

### Multi-Agent工作流

```
输入文本
    ↓
ConceptAnalyzer (概念提取)
    ↓
VisualStrategist (视觉策略)
    ↓
SVGCreator (SVG生成) ←──────┐
    ↓                        │
SVGReviewer (质量评审)       │
    ↓                        │
SVGRefiner (迭代优化) ───────┘
    ↓
输出SVG文件
```

### Agent职责

1. **ConceptAnalyzerAgent**
   - 提取实体（服务器、客户端、数据）
   - 识别流程（发送、接收、处理）
   - 确定布局类型（时间线/循环/层级/网络）

2. **VisualStrategistAgent**
   - 选择FUI配色方案
   - 设计布局结构
   - 规划动画序列

3. **SVGCreatorAgent**
   - 生成完整SVG代码
   - 实现CSS动画
   - 添加滤镜效果

4. **SVGReviewerAgent**
   - 评估5个维度（完整性、可读性、动画、教育性、美观性）
   - 提出改进建议

5. **SVGRefinerAgent**
   - 根据反馈优化
   - 最多2轮迭代

## 🔧 高级用法

### 批量生成

```bash
python main.py --batch
```

会生成多个测试SVG，包括：
- TCP三次握手
- HTTP请求流程
- DNS解析
- OAuth 2.0
- CAP理论

### 集成到视频系统

```python
from svg_agent import generate_for_video_system

result = generate_for_video_system(
    topic="网络七层协议",
    timestamp=30.5,  # 视频中的时间点
    context={
        "video_title": "计算机网络",
        "segment": "协议栈"
    },
    style="technical"
)
```

### 自定义LLM

```bash
# 使用GPT-4
python main.py "区块链原理" --llm gpt-4o

# 使用其他模型
python main.py "算法流程" --llm claude-opus-4
```

## 📁 输出文件

```
svg_output/
├── svg_1738123456.svg  # 时间戳命名
├── svg_1738123457.svg
└── ...
```

每个SVG文件：
- 完全独立（包含所有样式和动画）
- 可直接在浏览器中打开
- 支持响应式（viewBox）
- 纯CSS动画（无需JS）

## 🎬 查看动画

生成SVG后，直接用浏览器打开：

```bash
# macOS
open svg_output/svg_*.svg

# Linux
xdg-open svg_output/svg_*.svg

# Windows
start svg_output/svg_*.svg
```

或者拖拽到浏览器窗口。

## ⚙️ 配置

修改 `svg_agent/workflow.py`：

```python
# 调整迭代次数
self.max_iterations = 2  # 默认2次

# 调整目标分数
self.min_score = 7.0  # 默认7分
```

修改 `svg_agent/svg_creator_agent.py`：

```python
# 调整画布大小
width = 800  # 默认800px
height = 500 # 默认500px
```

## 🐛 故障排除

### 问题1：生成的SVG是fallback样式

**原因**：LLM调用失败或返回格式错误

**解决**：
1. 检查LLM配置（custom_chat_model.py）
2. 查看控制台日志
3. 尝试更简单的输入

### 问题2：动画不流畅

**原因**：浏览器渲染问题

**解决**：
1. 使用Chrome/Firefox最新版
2. 检查SVG中的CSS动画语法
3. 简化动画复杂度

### 问题3：中文显示异常

**原因**：字体或编码问题

**解决**：
1. SVG已使用sans-serif通用字体
2. 检查文件编码是UTF-8
3. 在prompt中要求使用特定字体

## 📚 技术参考

### SVG规范
- [MDN SVG Tutorial](https://developer.mozilla.org/en-US/docs/Web/SVG)
- [CSS Animation](https://developer.mozilla.org/en-US/docs/Web/CSS/animation)

### FUI设计灵感
- 科幻电影界面（如：钢铁侠的JARVIS、创战纪）
- 技术仪表盘
- 数据可视化

## 🔗 相关项目

- **视频增强系统**：../video_enhancer.py
- **主系统README**：../README.md

## 📄 许可证

与主项目相同
