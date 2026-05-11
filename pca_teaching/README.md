# PCA 交互教学系统

主成分分析（PCA）交互式教学网站，帮助学生直观理解 PCA 的核心概念。

## 三个教学模块

### 📐 2D 直觉演示
- 调整数据分布参数（展幅、旋转角度、点数）
- 实时观察主成分方向和方差解释比例
- 理解"方差 = 信息"的核心思想

### 🌸 真实数据集
- Iris（4维）和 Wine（13维）数据集
- 调整保留主成分数，观察碎石图和累积方差
- 理解降维的效果和选择主成分数的方法

### 👤 人脸重建（Eigenfaces）
- 40 张 64×64 人脸图像（Olivetti Faces）
- 拖动滑块调整主成分数量（1-40）
- 观察逐步重建过程：从模糊到清晰
- 查看特征脸（Eigenfaces）的可视化

## 快速开始

```bash
cd pca_teaching
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

浏览器打开 `http://localhost:5001`

## 技术栈

- Flask + scikit-learn + matplotlib + Pillow
- 暗色主题 UI，适合投影展示
