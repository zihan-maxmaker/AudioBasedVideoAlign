# audio_video_align 使用说明

## 概述
基于音频自动计算多视频之间的起始偏移（offset），并可选将视频裁剪导出为同步后的视频。

脚本：`audio_video_align.py`  
主要功能：遍历目录视频、计算相互偏移、输出 CSV，并可按偏移裁剪并导出同步后的视频。

## 依赖
- ffmpeg（可执行文件需在 PATH 中）
- Python 包：
  - moviepy
  - pandas
  - syncstart（提供 file_offset）

安装示例：
```bash
pip install moviepy pandas
# syncstart 视情况安装或使用本地模块
```

## 命令行参数
- --source, -s
  - 说明：源视频目录
  - 默认：`gopro/`
- --csv, -c
  - 说明：结果 CSV 输出路径
  - 默认：`syncstart_result/sync_results.csv`
- --edit, -e
  - 说明：是否修剪并输出同步后的视频（布尔标志）
  - 默认：False（脚本中目前为普通参数，建议可改为 `action="store_true"`）
- --output, -o
  - 说明：修剪后视频输出目录
  - 默认：`synced_videos`
- --take
  - 说明：传递给 `file_offset` 的 take 参数（用于音频比对长度）
  - 默认：20
- --show
  - 说明：是否显示 `file_offset` 的中间比对结果（布尔标志）
  - 默认：False（实现为 `action="store_true"`）

## 输出说明
- CSV 列：`base_file, target_file, offset_seconds`
- 偏移含义：
  - 正值：目标比基准晚开始（需要从头跳过 offset 秒）
  - 负值：目标比基准早开始（需要裁掉目标前部，使其与基准对齐）

## 裁剪导出（trim_videos）
- 默认 codec：`hevc_nvenc`（若无 NVIDIA 编码器，请修改为系统支持的 codec）
- 默认 crf：18
- 裁剪策略：以每个视频可用的最小帧数为基准，按 offset 计算 start（start = max(0, offset)），裁剪固定时长导出。

## 注意事项
- 源目录至少需要 2 个视频文件。
- 确保 ffmpeg 支持所选编码器，或修改脚本中的 codec 参数。
  
示例用法

只做同步分析并输出 CSV：

`python audio_video_align.py --source gopro/ --csv syncstart_result/sync_results.csv`

做同步并导出裁剪后的视频：

`python audio_video_align.py -s gopro/ -e -o synced_videos --take 500`

若想查看中间比对结果：

`python audio_video_align.py -s gopro/ --show`
