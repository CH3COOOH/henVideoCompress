# -*- coding: UTF-8 -*-

import os
import ffmpeg
import argparse
from pathlib import Path

## Most of the codes are made by DeepSeek.

def preserve_file_dates(input_path, output_path):
    """保留原始文件的修改/访问时间到新文件"""
    try:
        stat = os.stat(input_path)
        # 设置访问和修改时间 (atime, mtime)
        os.utime(output_path, (stat.st_atime, stat.st_mtime))
    except Exception as e:
        print(f"警告: 无法保留文件时间属性 - {str(e)}")

def is_video_file(filepath):
    """检查文件是否为视频文件（mp4或mov）"""
    return filepath.lower().endswith(('.mp4', '.mov'))

def get_video_files(input_dir):
    """获取输入目录中的所有视频文件"""
    return [f for f in os.listdir(input_dir) if is_video_file(f)]

def process_video(input_path, output_path, use_hwaccel=False):
    """处理单个视频文件：考虑旋转+保留元数据+分辨率减半+压缩"""
    try:
        original_mtime = os.path.getmtime(input_path)
        probe = ffmpeg.probe(input_path)
        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        
        if not video_stream:
            print(f"警告: {input_path} 中没有视频流，跳过")
            return False

        # 处理旋转元数据
        rotation = int(video_stream.get('tags', {}).get('rotate', 0))
        is_rotated = rotation in (90, 270)
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        if is_rotated:
            width, height = height, width

        # 构建滤镜链
        vf_filters = []
        if rotation:
            vf_filters.append(f"transpose={1 if rotation == 90 else 2}")
        vf_filters.append(f"scale={int(width/1.5)}:{height}:force_original_aspect_ratio=decrease")

        # 输出参数配置
        output_kwargs = {
            'vf': ','.join(vf_filters),
            'c:v': 'h264_qsv' if use_hwaccel else 'libx264',
            'crf': 18,
            'preset': 'fast',
            'movflags': '+faststart',
            # 保留元数据的关键参数
            'map_metadata': '0',          # 复制所有元数据
            'metadata:s:v': 'rotate=0',    # 重置旋转标记
            'disposition:v': '0',          # 保留视频流设置
            'disposition:a': '0',          # 保留音频流设置
            'c:a': 'copy',
            # 特别保留iOS重要的元数据
            'metadata': f"creation_time={video_stream.get('tags', {}).get('creation_time', '')}"
        }

        (
            ffmpeg.input(input_path)
            .output(output_path, **output_kwargs)
            .global_args('-map_metadata', '0')  # 再次确保复制元数据
            .global_args('-map', '0')          # 复制所有流
            .run(overwrite_output=True)
        )

        os.utime(output_path, (original_mtime, original_mtime))
        return True

    except ffmpeg.Error as e:
        print(f"处理 {input_path} 时出错: {e.stderr.decode('utf8')}")
        return False

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='视频处理工具')
    parser.add_argument('input_dir', help='输入文件夹路径')
    parser.add_argument('output_dir', help='输出文件夹路径')
    parser.add_argument('--hwaccel', action='store_true', help='使用硬件加速')
    args = parser.parse_args()

    # 确保输出目录存在
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # 获取视频文件列表
    video_files = get_video_files(args.input_dir)
    if not video_files:
        print(f"错误: 输入目录 {args.input_dir} 中没有找到视频文件(mp4/mov)")
        return

    print(f"找到 {len(video_files)} 个视频文件，开始处理...")
    print(f"使用{'硬件加速' if args.hwaccel else '软件编码'}模式")

    # 处理每个视频文件
    success_count = 0
    for filename in video_files:
        input_path = os.path.join(args.input_dir, filename)
        output_path = os.path.join(args.output_dir, filename)
        
        print(f"正在处理: {filename} -> 分辨率减半并压缩...")
        if process_video(input_path, output_path, args.hwaccel):
            success_count += 1
            print(f"完成: {filename}")
        else:
            print(f"失败: {filename}")

    print(f"\n处理完成! 成功处理 {success_count}/{len(video_files)} 个文件")

if __name__ == '__main__':
    main()