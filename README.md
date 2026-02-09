# audio_video_align 使用说明 ✅

> 简要：基于音频自动计算多视频之间的起始偏移（offset），并可选地将视频裁剪导出为同步后的视频。

---

## 概述 🔍
- 脚本：`audio_video_align.py`
- 功能：遍历源目录中的视频文件，使用 `syncstart.file_offset` 计算视频间的偏移，输出 CSV。可选地按偏移裁剪并导出同步后的视频。

---

## 顶部配置（请直接修改这些变量） 🛠️
在 `audio_video_align.py` 文件顶部，你会看到如下变量（以及默认值）：

- `SOURCE_DIR = "gopro/"`  # 源视频目录
- `CSV_PATH = "syncstart_result/sync_results2.csv"`  # 输出 CSV 路径
- `EDIT_VIDEOS = False`  # 是否修剪并导出同步后的视频
- `OUTPUT_DIR = "synced_videos"`  # 修剪后视频输出目录
- `TAKE = 20`  # 视频的前多少秒部分的音频会被用来做同步对齐，默认前20秒
- `SHOW = False`  # 是否显示 `file_offset` 的中间比对结果

简单修改这些变量，然后直接运行脚本即可。

---

## 运行方式 ▶️
在项目根目录下运行：

```bash
python audio_video_align.py
```

脚本会打印当前运行配置并开始处理。

---

## 输出说明 📦
- CSV 文件（由 `CSV_PATH` 指定）包含列：`base_file, target_file, offset_seconds`。
- target 比 base 晚开始,需要裁掉target 前 offset 秒以与 base 对齐。

---

## 裁剪与编码说明 🎞️
- 裁剪逻辑：以各视频裁剪后可用的最小帧数为统一长度，按每个视频的 offset 计算 start（start = max(0, offset)），裁剪并导出。
- 默认视频编码器：`hevc_nvenc`（若你的系统或 ffmpeg 没有 NVIDIA 编码支持，请在 `trim_videos` 函数中修改 `codec` 参数为合适值，例如 `libx264`）。
- 默认 CRF：18

---

## 依赖与安装 🧩
- ffmpeg（系统可执行）
- Python 包：
  - `moviepy`
  - `pandas`
  - `syncstart`（或本地模块，提供 `file_offset` 函数）

示例安装：

```bash
pip install moviepy pandas
# syncstart 根据你的来源安装或放置为本地模块
```

---

## 故障排查（FAQ） 🛠️
- 如果运行时报 `无法导入 syncstart 模块`：
  - 检查 `syncstart` 是否在你的 Python path 中；如果它是一个脚本，考虑把它作为模块或把其目录加入 `PYTHONPATH`。
- 如果看到 `syncstart: error: unrecognized arguments`：
  - 说明 `syncstart` 在导入时尝试解析命令行参数。脚本使用懒加载来避免此问题；若你的 `syncstart` 模块本身仍会在导入时解析参数，请修改 `syncstart` 源码或把其改为可导入的模块（不要在导入时执行 CLI 解析）。
- 若输出视频编码失败：将 `trim_videos` 中的 `codec` 参数改为系统支持的编码器（例如 `libx264`）并重新运行。

---

## 示例（修改配置后运行）
1. 只生成 CSV（默认）：

```bash
# 修改 SOURCE_DIR / CSV_PATH 后
python audio_video_align.py
```

2. 生成 CSV 并导出裁剪后视频：

```python
# 将文件顶部的 EDIT_VIDEOS = True 并设置 OUTPUT_DIR
# 然后运行
python audio_video_align.py
```

---

---
