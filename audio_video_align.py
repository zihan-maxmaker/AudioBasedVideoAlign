import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict
import pandas as pd
from moviepy.editor import VideoFileClip

# ----------------- 用户配置 -----------------
SOURCE_DIR = "gopro/"                    # 源视频目录
CSV_PATH = "syncstart_result/sync_results.csv"  # 输出CSV路径
EDIT_VIDEOS = False                      # 是否修剪并导出同步后的视频
OUTPUT_DIR = "synced_videos"             # 修剪后视频输出目录
TAKE = 20                                # 传给 file_offset 的 take 参数
SHOW = False                             # 是否显示 file_offset 的中间结果
# --------------------------------------------

def get_file_offset(in1: str, in2: str, take: int = 500, show: bool = False) -> Tuple[str, float]:
    try:
        from syncstart import file_offset as _file_offset
    except Exception as e:
        raise RuntimeError(f"无法导入 syncstart 模块：{e}")
    return _file_offset(in1=in1, in2=in2, take=take, show=show)


def get_video_list(source_dir: str) -> List[str]:
    """返回目录下的文件名列表（按字母排序）。"""
    p = Path(source_dir)
    if not p.exists() or not p.is_dir():
        return []
    return sorted([f.name for f in p.iterdir() if f.is_file()])


def compute_pair_offsets(base: str, targets: List[str], source_dir: str, take: int = 500, show: bool = False) -> List[Tuple[str, str, float]]:
    """计算 base 与每个 target 之间的 signed offset。"""
    base_path = os.path.join(source_dir, base)
    data = []
    for target in targets:
        target_path = os.path.join(source_dir, target)
        file, offset = get_file_offset(in1=base_path, in2=target_path, take=take, show=show)
        # 如果返回的 file 是 base（更早的需要被裁剪），则取负值
        signed_offset = -offset if os.path.abspath(file) == os.path.abspath(base_path) else offset
        data.append((base, target, signed_offset))
    return data


def choose_base_and_compute_all(video_list: List[str], source_dir: str, take: int = 500, show: bool = False) -> Tuple[str, List[Tuple[str, str, float]]]:
    """选择基准视频并计算相对于基准的视频偏移列表（包含基准自身）。"""
    if not video_list:
        raise ValueError("视频列表为空")

    initial_base = video_list[0]
    data_list = compute_pair_offsets(initial_base, video_list[1:], source_dir, take=take, show=show)

    signed_offsets = [item[2] for item in data_list]
    if all(so >= 0 for so in signed_offsets):
        final = [(initial_base, initial_base, 0.0)] + data_list
        return initial_base, final

    # 否则找到最小的负值对应的 video 作为新的 base，重新计算
    min_offset = min(signed_offsets)
    min_index = signed_offsets.index(min_offset)
    new_base = data_list[min_index][1]
    new_base_path = os.path.join(source_dir, new_base)

    final = [(new_base, new_base, 0.0)]
    for video in video_list:
        if video == new_base:
            continue
        file, offset = get_file_offset(in1=new_base_path, in2=os.path.join(source_dir, video), take=take, show=show)
        signed_offset = -offset if os.path.abspath(file) == os.path.abspath(new_base_path) else offset
        final.append((new_base, video, signed_offset))

    return new_base, final


def save_results(final_list: List[Tuple[str, str, float]], out_csv: str) -> pd.DataFrame:
    """保存结果为 CSV 并返回 DataFrame。"""
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(final_list, columns=["base_file", "target_file", "offset_seconds"])
    df.to_csv(out_path, index=False)
    return df


def trim_videos(video_list: List[str], source_dir: str, offsets: Dict[str, float], output_dir: str = "synced_videos", codec: str = "hevc_nvenc", crf: int = 18) -> int:
    """修剪并导出同步后的视频，返回统一的帧数（min_frames）。"""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_counts = []
    for v in video_list:
        path = os.path.join(source_dir, v)
        offset = offsets.get(v, 0.0)
        with VideoFileClip(path) as clip:
            duration = clip.duration - max(0, offset)
            fps = clip.fps or 30
            frames = int(duration * fps)
            frame_counts.append(frames)

    min_frames = min(frame_counts)

    for v in video_list:
        src_path = os.path.join(source_dir, v)
        offset = offsets.get(v, 0.0)
        out_path = str(out_dir / v)
        with VideoFileClip(src_path) as clip:
            fps = clip.fps or 30
            trim_duration = min_frames / fps
            start = max(0, offset)
            end = start + trim_duration
            end = min(end, clip.duration)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", src_path,
            "-t", str(end - start),
            "-c:v", codec,
            "-crf", str(crf),
            out_path,
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return min_frames


def main():
    source = SOURCE_DIR
    csv_path = CSV_PATH
    edit = EDIT_VIDEOS
    output = OUTPUT_DIR
    take = TAKE
    show = SHOW

    print(f"运行配置: source={source}, csv={csv_path}, edit={edit}, output={output}, take={take}, show={show}")

    video_list = get_video_list(source)
    if len(video_list) < 2:
        print("视频文件不足2个，无法比较。")
        return

    new_base, final_data_list = choose_base_and_compute_all(video_list, source, take=take, show=show)
    df = save_results(final_data_list, csv_path)

    print("同步分析完成！ ✅")
    print(f"基准文件为：{new_base}")
    print(f"结果已保存至 {csv_path}")

    if edit:
        offsets = {row['target_file']: row['offset_seconds'] for _, row in df.iterrows()}
        offsets[new_base] = 0.0
        min_frames = trim_videos(video_list, source, offsets, output_dir=output)
        print(f"所有同步后的视频已保存至 {output}，帧数统一为 {min_frames} 帧。 ✅")


if __name__ == "__main__":
    main()