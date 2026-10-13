# Spine 离线渲染工具

使用 Chromium + PixiJS 将 Spine 骨骼动画离线渲染为透明 WebM 或 PNG

## 功能

- 离线渲染，不依赖实时播放
- 支持透明背景输出 WebM（VP9 / yuva420p）
- 支持单帧 PNG 输出
- 已规避浏览器内存问题，可渲染长动画

## 环境要求

- Python 3.14（实测）
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
python main.py \
--data ./your_data.skel \
--atlas ./your_data.atlas \
--anim idle \
--format webm \
--output output.webm \
--size 3840x2160 \
--offset 0,1200 \
--scale 0.6
```

运行 `main.py` 时，`.skel`（`.json`） 和 `.atlas` 等数据文件必须放在当前工作目录或其子目录中，不能放在项目文件夹之外
