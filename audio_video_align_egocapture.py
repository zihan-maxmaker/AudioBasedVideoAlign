import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict
import pandas as pd
from moviepy.editor import VideoFileClip

# ----------------- 用户配置 -----------------
# `SOURCE_DIR` 指向包含两个子目录的 data 目录：
# - egocapture: 存放无声的视频和一个共享的 .wav 音频（egocapture 视频与该 wav 同步）
# - gopro: 存放带声的视频（需要与共享 wav 对齐）
SOURCE_DIR = "/home/zihan/Videos/syncTest/gopro_n_egocapture/take2"
EGO_SUBDIR = "egocapture"
GOPRO_SUBDIR = "gopro"
CSV_PATH = os.path.join(SOURCE_DIR, "sync_results.csv")  # 输出CSV路径
EDIT_VIDEOS = False                      # 是否修剪并导出同步后的视频
OUTPUT_DIR = os.path.join(SOURCE_DIR, "synced_videos")  # 修剪后视频输出目录（会保留子文件夹）
TAKE = 30                                # 视频前多少秒用于对齐
SHOW = False                          # 是否显示 file_offset 的中间结果
# --------------------------------------------
# The generated CSV file discribes time offsets between the shared audio (wav) and each video file.

def get_file_offset(in1: str, in2: str, take: int = 500, show: bool = False) -> Tuple[str, float]:
    try:
        from syncstart import file_offset as _file_offset
    except Exception as e:
        raise RuntimeError(f"无法导入 syncstart 模块：{e}")
    return _file_offset(in1=in1, in2=in2, take=take, show=show)


def get_video_list(source_dir: str, exts: List[str] = None) -> List[str]:
    """返回目录下的文件名列表（按字母排序）。

    如果提供 `exts`（例如 ['.mp4']），则只包含这些扩展名的文件（不区分大小写）。
    """
    p = Path(source_dir)
    if not p.exists() or not p.is_dir():
        return []
    allowed = None
    if exts:
        # 标准化扩展名（确保以点开头并小写）
        allowed = set([e.lower() if e.startswith('.') else f'.{e.lower()}' for e in exts])
    return sorted([f.name for f in p.iterdir() if f.is_file() and (allowed is None or f.suffix.lower() in allowed)])


def find_wav_in_dir(dir_path: str) -> str:
    p = Path(dir_path)
    if not p.exists() or not p.is_dir():
        return ""
    for f in sorted(p.iterdir()):
        if f.is_file() and f.suffix.lower() == ".wav":
            return str(f)
    return ""


def compute_pair_offsets(base_path: str, targets: List[str], take: int = 500, show: bool = False) -> List[Tuple[str, str, float]]:
    """计算 base_path 与每个 target_path 之间的 signed offset，返回 (base_name, target_relpath, offset)."""
    data = []
    for target_rel in targets:
        target_path = target_rel['abs']
        file, offset = get_file_offset(in1=base_path, in2=target_path, take=take, show=show)
        # 如果返回的 file 是 base（更早的需要被裁剪），则取负值
        signed_offset = -offset if os.path.abspath(file) == os.path.abspath(base_path) else offset
        data.append((os.path.basename(base_path), target_rel['rel'], signed_offset))
    return data


def choose_base_and_compute_all(*args, **kwargs):
    """选择一个基准文件并计算与其它文件的偏移。

    参数:
      files: List[dict] 或 List[str]
        - 如果是 dict 列表，期望每项包含 'rel' 和 'abs'。
        - 如果是 str 列表，会被解释为绝对路径，'rel' 使用文件名。
      take, show: 透传给 `compute_pair_offsets` 的参数。

    行为:
      1. 以列表第一项作为初始 base，计算 base 与其它每个文件的 signed offset。
      2. 如果有任意负值（表示 base 比某些文件更晚），则找出最小的负值对应的文件，
         将该文件作为新的 base，重新计算偏移。重复直到没有负值或 base 不再变化。

    返回: List[Tuple[str, str, float]]，元素为 (base_basename, target_relpath, offset_seconds)。
    """
    files = None
    take = kwargs.get('take', 500)
    show = kwargs.get('show', False)

    if args:
        files = args[0]
    else:
        files = kwargs.get('files')

    if not files:
        return []

    # 规范化为 {'rel': ..., 'abs': ...} 列表
    norm = []
    for item in files:
        if isinstance(item, str):
            norm.append({'rel': os.path.basename(item), 'abs': item})
        elif isinstance(item, dict) and 'abs' in item and 'rel' in item:
            norm.append({'rel': item['rel'], 'abs': item['abs']})
        else:
            raise ValueError("items must be str or dict with 'rel' and 'abs'")

    # 初始 base 为第一个文件
    base_abs = norm[0]['abs']

    prev_base = None
    final_results = []

    # 迭代直到没有负偏移或 base 不再变化
    while True:
        # 构建 targets（排除 base 本身）
        targets = [x for x in norm if os.path.abspath(x['abs']) != os.path.abspath(base_abs)]
        if not targets:
            # 只有 base 本身
            final_results = [(os.path.basename(base_abs), os.path.basename(base_abs), 0.0)]
            break

        results = compute_pair_offsets(base_abs, targets, take=take, show=show)

        # 找出最小的偏移（可能为负）
        offsets = [r[2] for r in results]
        min_offset = min(offsets)
        if min_offset < 0:
            # 找到对应的 target（第一个出现最小值的）
            idx = offsets.index(min_offset)
            candidate_rel = results[idx][1]
            # 在 norm 中查找其绝对路径
            candidate = next((x for x in norm if x['rel'] == candidate_rel), None)
            if candidate is None:
                # 安全回退，直接退出并返回当前结果
                final_results = results
                break
            new_base_abs = candidate['abs']
            # 如果 base 没有变化则终止以避免死循环
            if prev_base and os.path.abspath(new_base_abs) == os.path.abspath(prev_base):
                final_results = results
                break
            prev_base = base_abs
            base_abs = new_base_abs
            # 继续下一轮重新计算
            continue
        else:
            # 全部非负，结果相对于当前 base 是最终结果
            final_results = results
            break

    return final_results


def save_results(final_list: List[Tuple[str, str, float]], out_csv: str) -> pd.DataFrame:
    """保存结果为 CSV 并返回 DataFrame。final_list 中元素为 (base_name, target_relpath, offset_seconds)."""
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(final_list, columns=["base_file", "target_file", "offset_seconds"])
    df.to_csv(out_path, index=False)
    return df


def trim_videos(relpaths: List[str], source_dir: str, offsets: Dict[str, float], output_dir: str = "synced_videos", codec: str = "hevc_nvenc", crf: int = 18) -> int:
    """修剪并导出同步后的视频，返回统一的帧数（min_frames）。

    `relpaths` 为相对于 `source_dir` 的路径，如 "egocapture/vid.mp4" 或 "gopro/vid.mp4"。
    输出会保留子文件夹结构到 `output_dir` 下。
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_counts = []
    for rel in relpaths:
        abs_path = os.path.join(source_dir, rel)
        offset = offsets.get(rel, 0.0)
        with VideoFileClip(abs_path) as clip:
            duration = clip.duration - max(0, offset)
            fps = clip.fps or 30
            frames = int(duration * fps)
            frame_counts.append(frames)

    if not frame_counts:
        return 0

    min_frames = min(frame_counts)

    for rel in relpaths:
        src_path = os.path.join(source_dir, rel)
        offset = offsets.get(rel, 0.0)
        dest_path = Path(output_dir) / Path(rel)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
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
            str(dest_path),
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
    # 查找子目录
    ego_dir = os.path.join(source, EGO_SUBDIR)
    gopro_dir = os.path.join(source, GOPRO_SUBDIR)

    # egocapture 目录中只有 .wav（音频）和 .mp4（视频）是有意义的：只读取 .mp4 视频文件
    ego_videos = get_video_list(ego_dir, exts=['.mp4'])
    gopro_videos = get_video_list(gopro_dir)

    if not ego_videos and not gopro_videos:
        print("未找到 egocapture 或 gopro 视频文件，退出。")
        return

    wav_path = find_wav_in_dir(ego_dir)
    if not wav_path:
        print(f"未在 {ego_dir} 中找到 .wav 文件，无法对齐。")
        return

    # 构建 targets 列表（相对路径 + 绝对路径）用于与 wav 对齐（只对 gopro 文件有意义）
    gopro_targets = []
    for name in gopro_videos:
        rel = os.path.join(GOPRO_SUBDIR, name)
        gopro_targets.append({"rel": rel, "abs": os.path.join(gopro_dir, name)})

    # 计算 wav 与每个 gopro 文件的偏移（使用 choose_base_and_compute_all）
    final_data_list = []
    if gopro_targets:
        # 把共享 wav 也加入列表，让函数决定最终的 base
        wav_entry = {'rel': os.path.basename(wav_path), 'abs': wav_path}
        files_for_choice = [wav_entry] + gopro_targets
        data = choose_base_and_compute_all(files_for_choice, take=take, show=show)
        final_data_list.extend(data)

    # 将 egocapture 下的视频视为与 wav 同步（offset=0）
    for name in ego_videos:
        rel = os.path.join(EGO_SUBDIR, name)
        final_data_list.append((os.path.basename(wav_path), rel, 0.0))

    df = save_results(final_data_list, csv_path)

    print("同步分析完成！ ✅")
    print(f"共享音频为：{wav_path}")
    print(f"结果已保存至 {csv_path}")

    if edit:
        offsets = {row['target_file']: row['offset_seconds'] for _, row in df.iterrows()}
        # 确保 egocapture 的视频也在 offsets 中
        for name in ego_videos:
            rel = os.path.join(EGO_SUBDIR, name)
            offsets.setdefault(rel, 0.0)

        # 需要裁剪的相对路径列表（保留子文件夹）
        relpaths = [os.path.join(GOPRO_SUBDIR, n) for n in gopro_videos] + [os.path.join(EGO_SUBDIR, n) for n in ego_videos]
        min_frames = trim_videos(relpaths, source, offsets, output_dir=output)
        print(f"所有同步后的视频已保存至 {output}，帧数统一为 {min_frames} 帧。 ✅")


if __name__ == "__main__":
    main()