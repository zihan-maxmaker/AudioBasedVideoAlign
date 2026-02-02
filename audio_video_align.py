import os
from moviepy.editor import *
from syncstart import file_offset
import pandas as pd
from moviepy.editor import VideoFileClip
import subprocess

# 定义时间转换函数
def str2sec(x):
    hours, minutes, seconds = map(int, x.split(":"))
    return hours * 3600 + minutes * 60 + seconds

def str2sec_(x):
    hours, minutes, seconds = map(int, x.split(":"))
    return hours * 3600 + minutes * 60 + seconds

# 定义源文件路径
# source_video_dir = "source_video/"
source_video_dir = "gopro/"
video_list = os.listdir(source_video_dir)
video_list.sort()  # 保证顺序一致，选第一个为基准
data_list = []

def new_func(offset):
    signed_offset = offset
    return signed_offset

if len(video_list) < 2:
    print("视频文件不足2个，无法比较。")
else:
    base = video_list[0]
    base_video_dir = os.path.join(source_video_dir, base)

    for target in video_list[1:]:
        target_video_dir = os.path.join(source_video_dir, target)
        data_dict = {
            'in1': base_video_dir,
            'in2': target_video_dir,
            'take': 500,
            'show': False
        }
        file, offset = file_offset(**data_dict)
        # file 是开始较早的，需要被裁减的视频
        # 判断 file 是否为 base，如果是，则 signed_offset 取负值，否则取正值
        if os.path.abspath(file) == os.path.abspath(base_video_dir):
            signed_offset = -offset
        else:
            signed_offset = offset
        data_list.append((base, target, signed_offset))

    # 新增逻辑：判断signed_offset全为正还是有负数
    signed_offsets = [item[2] for item in data_list]
    if all(so >= 0 for so in signed_offsets):
        # 当前base就是最晚的，直接用data_list生成final_data_list
        new_base = base
        new_base_video_dir = base_video_dir
        final_data_list = [(new_base, base, 0)]
        for entry in data_list:
            _, target, signed_offset = entry
            final_data_list.append((new_base, target, signed_offset))
    else:
        # 存在负数，最小负数对应的target为新base
        min_offset = min(signed_offsets)
        min_index = signed_offsets.index(min_offset)
        new_base = data_list[min_index][1]
        new_base_video_dir = os.path.join(source_video_dir, new_base)
        # 以新base重新计算所有视频与新base的offset
        final_data_list = [(new_base, new_base, 0)]
        for video in video_list:
            if video == new_base:
                continue
            video_dir = os.path.join(source_video_dir, video)
            data_dict = {
                'in1': new_base_video_dir,
                'in2': video_dir,
                'take': 500,
                'show': False
            }
            file, offset = file_offset(**data_dict)
            if os.path.abspath(file) == os.path.abspath(new_base_video_dir):
                signed_offset = -offset
            else:
                signed_offset = offset
            final_data_list.append((new_base, video, signed_offset))


    # 保存最终结果
    df = pd.DataFrame(final_data_list, columns=["base_file", "target_file", "offset_seconds"])
    df.to_csv("syncstart_result/sync_results.csv", index=False)
    
    print("同步分析完成！")
    print(f"基准文件为：{new_base}")
    print(f"结果已保存至 syncstart_result/sync_results.csv")

    # === 修剪视频并保存到新文件夹 ===
    output_dir = "synced_videos"
    os.makedirs(output_dir, exist_ok=True)

    # 统计所有视频修剪后应有的最短时长（以帧数为准）
    video_paths = [os.path.join(source_video_dir, v) for v in video_list]
    # offsets字典应包含所有视频，基准视频offset为0
    offsets = {row['target_file']: row['offset_seconds'] for _, row in df.iterrows()}
    offsets[new_base] = 0

    # 获取所有视频修剪后剩余帧数
    frame_counts = []
    durations = []
    for v in video_list:
        path = os.path.join(source_video_dir, v)
        offset = offsets.get(v, 0)
        clip = VideoFileClip(path)
        duration = clip.duration - max(0, offset)
        durations.append(duration)
        fps = clip.fps
        frames = int(duration * fps)
        frame_counts.append(frames)
        clip.close()
    min_frames = min(frame_counts)

    # 修剪并导出所有视频
    for v in video_list:
        src_path = os.path.join(source_video_dir, v)
        offset = offsets.get(v, 0)
        out_path = os.path.join(output_dir, v)
        clip = VideoFileClip(src_path)
        fps = clip.fps
        # 计算修剪后的视频长度（以帧为准，保证所有视频帧数一致）
        trim_duration = min_frames / fps
        start = max(0, offset)
        end = start + trim_duration
        # 防止end超过原视频长度
        end = min(end, clip.duration)
        # 使用ffmpeg命令修剪，使用hevc_nvenc编码
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", src_path,
            "-t", str(end - start),
            "-c:v", "hevc_nvenc",
            "-crf", "18",
            out_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clip.close()

    print(f"所有同步后的视频已保存至 {output_dir}，帧数统一为 {min_frames} 帧。")