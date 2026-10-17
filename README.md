
# Spine 离线渲染工具

使用 Chromium + PixiJS 将 Spine 骨骼动画离线渲染为透明 WebM 或 PNG

## 功能

- 离线渲染，不依赖实时播放
- 支持透明背景输出 WebM（VP9 / yuva420p）
- 支持单帧 PNG 输出
- 使用多线程并行渲染，实测渲染 3840×2160 / 60fps 长约 1min 左右的 Spine 动画，本工具约需 6~7 分钟。

## 环境要求

类 Unix Only （如 GNU/Linux, macOS, etc.)

不兼容 win ，路径的处理依赖类 Unix 环境，如果有需要欢迎尝试

- Python 3.10+
- Node.js 18+
- FFmpeg

## 安装

```bash
git clone https://github.com/mingyangqianli2357/spine-render.git
cd spine-render
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
npm install
```
### 使用示例

```bash
cd spine-render
source .venv/bin/activate
TMPDIR=tmp \
python main.py \
--data your_data.skel \
--atlas your_data.atlas \
--anim idle \
--format webm \
--output output.webm \
--size 3840x2160 \
--offset 0,1200 \
--scale 0.6 \
--port 8123 \
--cdp-port 9333 \
--parallel 4
```
