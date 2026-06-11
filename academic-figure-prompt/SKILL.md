---
id: academic-figure-prompt
name: Academic Figure Prompt
version: 1.0.0
description: Use this skill whenever the user wants to generate detailed prompts for AI image tools (NanoBanana / Gemini / DALL-E / Midjourney) to produce top-conference-quality academic figures — including framework diagrams, network architecture diagrams, pipeline flowcharts, module detail diagrams, comparison/ablation figures, and data pattern grids. If the user has not specified a color scheme, default to Option A (Okabe-Ito Academic Standard).
stages: [writing, research, review]
tools: [bash]
---

# Academic Figure Prompt — 学术论文配图提示词生成器

为学术论文生成**极其详细的提示词**，供 AI 图片生成工具（NanoBanana / Gemini / Midjourney / DALL-E）生成一张专业学术配图。

## 核心理念

生成的提示词必须做到四点：**包含核心概念**、**视觉风格精确**、**内容完整无遗漏**、**总长度不超过 4096 字符**。

在以上约束下做到最佳平衡：优先保留关键模块、公式、维度标注和配色规格；次要描述可精简但不可省略核心结构。学术配图的价值在于精准传达复杂信息，而非美观简洁。

## 工作流程

### Step 1: 理解论文内容

在生成提示词之前，**必须**先充分理解论文内容：

1. 提取每个章节的核心概念、方法、模型架构、数据流
2. 判断需要的标注语言（如英文、中文、无文字）、配图类型及其内容
3. 理解论文中的数学符号、变量含义、维度信息
4. **从原文中提取图中文字**：配图中的所有文字内容（模块名称、标签、公式、维度标注、箭头注释等）必须从输入原文中提取，不得凭空编造。优先提取 `\caption`、`\label`、章节标题、公式中的符号作为图中文字来源

### Step 2: 分析参考图（如有）

如果用户提供了参考图，**必须**详细分析：

| 分析维度 | 提取内容 |
|---------|---------|
| **配色方案** | 主色、辅色、强调色的精确色值（如 #3A8F85） |
| **布局结构** | 流向（左→右 / 上→下）、分区方式、层次关系 |
| **模块样式** | 框的形状、边框粗细、填充色、圆角大小 |
| **标注方式** | 标题栏样式、公式标注、维度标注、箭头类型 |
| **信息密度** | 每个模块内的子细节数量、嵌入缩略图的使用方式 |
| **特殊元素** | 反馈环路、虚线框、跳接箭头、图例位置 |

### Step 2.5: 配色方案确定（非阻塞，自动决策）

配色方案按以下优先级确定：

1. **从初始请求中提取**：如果用户在请求中已包含配色信息（如指定了 hex 色值、颜色名称如"蓝绿配色"、或请求中直接附带了 `color_scheme` / `custom_colors` JSON），则提取并使用该配色方案。
2. **从参考图中提取**：如果用户提供了参考图，从参考图中分析提取主色、辅色、点缀色。
3. **使用默认方案**：如果以上均未提供，**默认使用方案 A：Okabe-Ito 学术标准**（色盲友好，Nature / Science / CVPR 推荐），直接进入 Step 3，不询问用户。

| 优先级 | 来源 | 处理方式 |
|--------|------|----------|
| 1 | 请求中明确指定的配色 | 直接使用 |
| 2 | 参考图提取 | 直接使用 |
| 3 | 默认方案 A: Okabe-Ito | 直接使用，不询问 |

默认配色方案供参考：

| # | 方案名 | 风格定位 | 主色 | 辅色 | 点缀色 |
|---|--------|----------|------|------|--------|
| A | Okabe-Ito 学术标准 | Nature / Science / CVPR 推荐，色盲友好 | Steel Blue `#0072B2` | Warm Orange `#E69F00` | Bluish Green `#009E73` |

> 提示：如需覆盖默认配色，直接把主色/辅色/点缀色的 hex 值在请求中提供即可（如 `主色 #2E7D32，辅色 #C49A00`）。

### Step 3: 生成提示词

按照下方的「提示词结构模板」为每张图生成提示词。

---

## 提示词结构模板

每个提示词必须包含以下 **四个层次**，缺一不可：

### 层次 1: 全局描述（Global Description）

开头一段话，概括整张图的类型、主题和整体布局，同时指定标注语言（如英文、中文、无文字）。

``` 英文prompt
A highly detailed, information-dense academic paper [类型] diagram. The diagram illustrates [主题概述], arranged as [布局描述: e.g., "a rich multi-stage left-to-right pipeline with multiple parallel
pathways, embedded thumbnail visualizations, and dense annotations"].
```

``` 中文prompt
一份细节饱满、信息高密度的学术论文 [类型]，整张图展示 [主题概述] ，整体排布形式为 [布局描述：如：“从左至右多阶段流水线、多条并行分支、内嵌微型可视化图、高密度文字标注”]。
```

**类型词汇表：**
- 英文：architecture / framework / pipeline / flowchart / comparison / ablation / network architecture / module detail / data flow / system overview
- 中文：架构图 / 框架图 / 流水线 / 流程图 / 对比图 / 消融图 / 网络架构图 / 模块详解图 / 数据流图 / 系统总览图

### 层次 2: 分区详细描述（Section-by-Section Description）

用 `=== SECTION NAME ===` 格式分隔每个区域。每个区域内部必须包含：

| 元素 | 要求 | 示例 |
|------|------|------|
| **背景面板** | 极浅色填充 + 色值 | `very faint grey #F7F7F7 background panel` |
| **节标签** | small-caps 文字 + 细灰分割线 | `small-caps Steel Blue label "ENCODER"` |
| **模块框** | 白色填充 + 彩色/灰色边框 | `white rounded-rectangle box with Steel Blue border` |
| **子结构** | 每个模块内部的组件 | `containing three parallel branches...` |
| **嵌入缩略图** | 模块内的小型单色可视化 | `a small monochrome FFT spectrum bar chart thumbnail` |
| **公式标注** | LaTeX 风格公式 | `with formula "HT = 1/(1 + d/d₀)"` |
| **维度标注** | 张量/向量维度 | `labeled "X ∈ R^(120×6)"` |
| **连接箭头** | 箭头类型和标签 | `thin arrow labeled "30-step predicted trajectory"` |

**关键原则：每个模块框内部都必须有子内容。不允许出现空白占位框。**

### 层次 3: 全局标注（Global Annotations）

- 维度标注沿主要箭头：`"R^(120×6)", "R^(30×6)", "R^14", "R^5"`
- 反馈环路（如有）：`dashed feedback arrow from output back to input`
- 图例（如有）：`legend box in bottom-right corner`
- 跨区域连接：`skip connection dashed arrow from Stage 1 to Stage 3`

### 层次 4: 风格规格（Style Specifications）

每个提示词末尾必须附加完整的风格描述，将选定方案的色值填入。

---

## 配色方案色值表

用户在 Step 2.5 中选定方案后，从下方取对应色值填入提示词末尾的 STYLE SPECIFICATIONS。

### 方案 A: Okabe-Ito 学术标准（默认）

| 元素 | 色值 | 用途 |
|------|------|------|
| 主色 | Steel Blue `#0072B2` | 核心模块边框、节标签、主箭头 |
| 辅色 | Warm Orange `#E69F00` | 次要模块边框、替代高亮 |
| 点缀色 | Bluish Green `#009E73` | 输出/结果模块（极少量） |
| 警告色 | Vermillion `#D55E00` | 关键高亮/警告（极少量） |
| 模块填充 | Pure White `#FFFFFF` | 所有内容框 |
| 区域背景 | Faint Grey `#F7F7F7` | 大区域分组 |
| 标准边框 | Light Grey `#CCCCCC` | 普通框体（1px） |
| 正文字色 | Charcoal `#333333` | 所有标签 |
| 箭头/线条 | Dark Grey `#4D4D4D` | 连接线 |
| 次要注释 | Medium Grey `#666666` | 标注文字 |

### 方案 B: Blue 单色系

| 元素 | 色值 | 用途 |
|------|------|------|
| 强调/标签 | Navy `#0072B2` | 关键模块边框、节标签 |
| 主要边框 | Medium Blue `#4A90D9` | 主流程模块 |
| 次要边框 | Light Blue `#A0C4E8` | 次要/辅助模块 |
| 区域背景 | Pale Blue `#EBF3FA` | 大区域分组 |
| 模块填充 | Pure White `#FFFFFF` | 所有内容框 |
| 中性/箭头 | Grey `#999999` | 连接线、次要标注 |
| 正文字色 | Charcoal `#333333` | 所有标签 |

### 方案 C: Teal + Amber

| 元素 | 色值 | 用途 |
|------|------|------|
| 主色 | Deep Teal `#00897B` | 核心模块边框、节标签 |
| 辅色 | Amber `#FFB300` | 次要模块边框、强调 |
| 区域背景 | Soft Grey-Blue `#ECEFF1` | 大区域分组 |
| 模块填充 | Pure White `#FFFFFF` | 所有内容框 |
| 标准边框 | Light Grey `#CFD8DC` | 普通框体 |
| 正文字色 | Dark Slate `#263238` | 所有标签 |
| 箭头/线条 | Medium Grey `#607D8B` | 连接线 |
| 次要注释 | Grey `#90A4AE` | 标注文字 |

### 方案 D: Navy + Coral

| 元素 | 色值 | 用途 |
|------|------|------|
| 主色 | Deep Navy `#1A3A5C` | 核心模块边框、节标签 |
| 辅色 | Coral `#E05A47` | 强调模块、关键路径 |
| 点缀色 | Warm Sand `#D4A96A` | 输出/结果模块（极少量） |
| 区域背景 | Ivory `#F9F6EE` | 大区域分组 |
| 模块填充 | Pure White `#FFFFFF` | 所有内容框 |
| 标准边框 | Light Warm Grey `#D4C5B0` | 普通框体 |
| 正文字色 | Dark Slate `#1A3A5C` | 所有标签 |
| 箭头/线条 | Medium Grey `#7A8A99` | 连接线 |

### 方案 E: Slate + Violet

| 元素 | 色值 | 用途 |
|------|------|------|
| 主色 | Indigo `#3F51B5` | 核心模块边框、节标签 |
| 辅色 | Muted Violet `#7E57C2` | 次要模块边框 |
| 点缀色 | Teal Accent `#26A69A` | 输出/结果模块（极少量） |
| 区域背景 | Pale Lavender `#EDE7F6` | 大区域分组 |
| 模块填充 | Pure White `#FFFFFF` | 所有内容框 |
| 标准边框 | Light Purple Grey `#C5CAE9` | 普通框体 |
| 正文字色 | Deep Indigo `#1A237E` | 所有标签 |
| 箭头/线条 | Medium Grey `#7986CB` | 连接线 |

### 方案 F: Forest + Gold

| 元素 | 色值 | 用途 |
|------|------|------|
| 主色 | Forest Green `#2E7D32` | 核心模块边框、节标签 |
| 辅色 | Antique Gold `#C49A00` | 次要模块边框、强调 |
| 区域背景 | Warm Cream `#F9F6EE` | 大区域分组 |
| 模块填充 | Pure White `#FFFFFF` | 所有内容框 |
| 标准边框 | Sage `#A5D6A7` | 普通框体 |
| 正文字色 | Dark Forest `#1B5E20` | 所有标签 |
| 箭头/线条 | Warm Grey `#795548` | 连接线 |

### 方案 G: Minimal Grey + 单一强调色

| 元素 | 色值 | 用途 |
|------|------|------|
| 强调色（可替换） | Steel Blue `#0072B2` | 仅用于最核心的 1-2 个模块边框 |
| 深灰 | Charcoal `#263238` | 节标签、正文字色 |
| 中深灰 | Slate `#546E7A` | 主要边框、箭头 |
| 中灰 | Medium Grey `#90A4AE` | 次要边框 |
| 浅灰 | Light Grey `#ECEFF1` | 区域背景 |
| 模块填充 | Pure White `#FFFFFF` | 所有内容框 |
| 标准边框 | Grey `#B0BEC5` | 普通框体 |

---

## 配色禁忌（避免 AI 生图感）

| 禁止做法 | 替代做法 |
|---------|---------|
| 4-5 种彩色背景面板 | 白色为主 + 极浅灰分组 |
| 高饱和度 Header Banner Bar | 小号 small-caps 文字标签 + 灰色分割线 |
| 每个模块不同颜色填充 | 纯白填充 + 仅边框用色 |
| 彩色缩略图 | 单色灰度或仅用 2 色 |
| 5+ 种颜色同时出现 | 最多 3 种色彩 + 灰色系 |
| 彩虹/渐变效果 | 纯色、扁平、无渐变 |

---

## 图片类型专用模板

### 类型 1: 框架图/系统总览图（Overall Framework / System Overview）

```
结构: [输入] → [阶段1] → [阶段2] → ... → [输出]
要求:
- 各阶段用 small-caps 文字标签 + 细灰色分割线（不用彩色背景面板）
- 核心模块用主色边框，次要模块用辅色边框，普通模块用 Grey 边框
- 所有模块白色填充，无彩色填充
- 阶段间箭头标注数据维度和含义
- 每个阶段内展示 2-4 个子模块，子模块内嵌入单色缩略图
- 底部或顶部添加反馈/跳接连接（灰色虚线）
```

### 类型 2: 网络架构图（Network Architecture）

```
结构: [输入层] → [编码器堆叠] → [核心模块（并行分支）] → [输出头]
要求:
- 并行分支用不同边框色区分，内部均为白色填充
- 每个分支内标注操作名称 + 单色缩略图
- 残差连接用灰色虚线弧形箭头
- 维度标注在每层转换处（灰色小字）
- 重复层用 "×N" 灰色虚线框标识
```

### 类型 3: 模块详解图（Module Detail）

```
结构: [输入] → [操作1] → [中间表示] → [操作2] → [输出]
要求:
- 每步操作用白色独立框，关键操作用主色边框，次要用 Grey 边框
- 中间表示用单色灰度缩略图可视化（频谱图、热力图等）
- 跳接/残差连接用灰色虚线
- 公式标注在对应操作框旁（灰色小字）
```

### 类型 4: 对比/消融图（Comparison / Ablation）

```
结构: N 列并排，每列一个变体
要求:
- 共享的基础结构用相同灰色边框
- 差异部分用主色或辅色边框高亮 + 灰色虚线框标出
- 每列顶部标注变体名称（small-caps）
- 底部可添加性能指标对比条（仅用主色 + 辅色 + Grey）
```

### 类型 5: 数据流图/流水线/流程图（Data Flow / Pipeline / Flowchart）

```
结构: 1×N 网格，每格一个类别
要求:
- 每格为白色框 + 细灰色边框，顶部标签用主色小字
- 格内嵌入该类别的单色/双色典型可视化（轨迹、波形等）
- 用主色 / 辅色区分正面/负面类别（如有对比语义）
- 关键特征用文字标签
- 底部共享坐标轴（如有）
```

---

## 缩略图词汇表（Thumbnail Vocabulary）

| 数据类型 | 缩略图描述 |
|---------|-----------|
| 时间序列 | `a small time-series waveform thumbnail` |
| 频率谱 | `a small frequency spectrum bar chart thumbnail` |
| 注意力图 | `a small monochrome attention heatmap grid thumbnail` |
| 轨迹 | `a small 3D orbital trajectory curve thumbnail` |
| 概率分布 | `a small probability distribution bar chart thumbnail` |
| 决策树 | `a small decision tree branching diagram thumbnail` |
| 混淆矩阵 | `a small confusion matrix heatmap thumbnail` |
| 网络节点 | `a small neural network layer diagram thumbnail` |
| 特征向量 | `a small horizontal feature vector bar visualization` |
| 散点图 | `a small scatter plot with cluster coloring thumbnail` |
| 感受野 | `a progressively larger receptive field grid icon` |
| 卷积核 | `a small convolution filter kernel grid thumbnail` |
| 梯度流 | `a small gradient flow direction arrow diagram` |
| 损失曲线 | `a small training loss convergence curve thumbnail` |
| ROC 曲线 | `a small ROC curve with AUC shading thumbnail` |
| 图像样本 | `a small example image/photo thumbnail` |
| 点云 | `a small 3D point cloud visualization thumbnail` |
| 热力图 | `a small spatial heatmap overlay thumbnail` |

---

## 质量检查清单

生成每个提示词后，对照以下清单自检：

- [ ] **信息密度**：每个模块框内都有子内容（子框或缩略图或公式），没有空白框
- [ ] **色彩克制**：仅使用 2-3 种色彩，无多余颜色
- [ ] **白色主导**：≥70% 面积为白色/近白色，无彩色背景面板
- [ ] **边框而非填充**：模块用白色填充 + 彩色/灰色细边框，而非彩色填充
- [ ] **分区方式**：用 small-caps 文字标签 + 灰色分割线，不用彩色 banner bar
- [ ] **维度标注**：所有主要数据流箭头上都标注了维度（如 R^(N×D)）
- [ ] **公式标注**：关键操作旁有对应数学公式
- [ ] **缩略图嵌入**：至少 50% 的模块内嵌入了单色/双色缩略可视化
- [ ] **完整性**：论文中描述的所有组件都在图中体现，无遗漏
- [ ] **连接清晰**：并行路径、残差连接、反馈环路都有明确描述
- [ ] **风格规格**：末尾包含完整的 STYLE SPECIFICATIONS 段落（含色值约束和禁止项）
- [ ] **无简化**：没有用 "..." 或 "etc." 省略任何内容
- [ ] **灰度测试**：描述确保图片在黑白打印时仍可完整阅读
- [ ] **Token 限制**：提示词总长度不超过 4096 tokens（如超限，精简次要模块描述和冗余修饰词，但保留所有模块名称、公式、维度标注）
- [ ] **文字来源**：图中所有文字（模块名、标签、公式、注释）均从输入原文中提取，无凭空编造

---

## 输出格式

每个提示词用 markdown 代码块包裹：

```markdown
### 图 X.Y — [中文图名]

适用类型：[框架图/架构图/模块图/对比图/模板图]
配色方案：[已选方案名]
推荐分辨率：[建议的宽高比，如 16:9, 3:2]

​```
[完整提示词]
​```
```

---

## 注意事项

1. **提示词语言**：提示词本身与原文语言保持一致
2. **Token 限制**：每段提示词不超过 4096 个字符。精简策略：优先压缩全局描述和风格规格中的重复描述，保留所有模块名称、公式、维度标注和核心结构；避免冗余修饰词
3. **领域自适应**：根据论文领域（CV、NLP、Robotics、医学等）调整缩略图和图标选择
4. **参考图优先**：如果用户提供了参考图，配色和布局以参考图为准，覆盖预设方案
5. **配图数量**：当用户要求为整篇论文生成配图时，配图类型为整体架构图
6. **图中文字来源**：所有图中文字必须从输入原文中提取，不得凭空创建。对于 LaTeX 源文件，图中文字应来自 `\caption`、`\label`、章节标题、`\section`、公式符号、表格内容等；对于 PDF/Word 文档，从正文段落、标题、图表标题中提取
