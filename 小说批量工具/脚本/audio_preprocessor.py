#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
背景音和音效预处理工具
检查每个剧本目录下的背景音和音效是否已经生成，如果已经生成则放到正确的目录下
"""

import os
import json
import shutil
import argparse
from typing import Dict, List, Tuple
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_novel_json_files(script_dir: str) -> List[str]:
    """
    查找所有小说JSON文件
    :param script_dir: 小说剧本目录
    :return: 小说JSON文件列表
    """
    novel_json_files = []
    
    # 遍历小说剧本目录
    for novel_name in os.listdir(script_dir):
        novel_path = os.path.join(script_dir, novel_name)
        if os.path.isdir(novel_path):
            # 遍历小说目录下的JSON文件
            for file_name in os.listdir(novel_path):
                if file_name.endswith(".json"):
                    json_file = os.path.join(novel_path, file_name)
                    novel_json_files.append(json_file)
    
    return novel_json_files


def extract_audio_params(json_file: str) -> Tuple[List[Dict], List[Dict]]:
    """
    从JSON文件中提取BGM和音效参数
    :param json_file: 小说JSON文件路径
    :return: (bgm_params_list, effect_params_list)
    """
    bgm_params_list = []
    effect_params_list = []
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 遍历所有台词，记录场景序号（即data数组中的id）
        for line in config.get("data", []):
            scene_id = line.get("id", 0)  # 场景序号
            
            # 提取BGM参数
            if "bgm" in line["api"]:
                bgm_params = line["api"]["bgm"]["params"]
                bgm_params_list.append({
                    "scene": bgm_params["scene"],
                    "scene_en": bgm_params["scene_en"],
                    "volume": bgm_params["volume"],
                    "pitch": bgm_params["pitch"],
                    "scene_id": scene_id  # 添加场景序号
                })
            
            # 提取音效参数
            if "effects" in line["api"]:
                for effect in line["api"]["effects"]:
                    effect_params = effect["params"]
                    effect_params_list.append({
                        "name": effect_params["name"],
                        "sound_en": effect_params["sound_en"],
                        "volume": effect_params["volume"],
                        "pitch": effect_params["pitch"],
                        "duration": effect["duration"],
                        "scene_id": scene_id  # 添加场景序号
                    })
    
    except Exception as e:
        logger.error(f"提取音频参数失败: {json_file}, 错误: {e}")
    
    return bgm_params_list, effect_params_list


def generate_audio_filename(desc_en: str, duration: float, audio_type: str) -> str:
    """
    生成固定的音频文件名
    :param desc_en: 英文描述
    :param duration: 音频时长
    :param audio_type: 音频类型
    :return: 生成的文件名
    """
    # 简化版：直接使用描述词和时长，不使用哈希值
    # 用于生成临时文件名
    import hashlib
    audio_params = f"{desc_en}_{duration}_{audio_type}"
    audio_hash = hashlib.md5(audio_params.encode()).hexdigest()[:16]
    return f"{audio_type}_{audio_hash}_{int(duration)}"


def check_and_copy_audio_files(script_dir: str, output_dir: str, temp_dir: str):
    """
    检查并复制音频文件到正确的目录
    :param script_dir: 小说剧本目录
    :param output_dir: 输出目录
    :param temp_dir: 临时音频目录
    """
    # 获取所有小说JSON文件
    novel_json_files = get_novel_json_files(script_dir)
    logger.info(f"找到 {len(novel_json_files)} 个小说JSON文件")
    
    # 遍历每个小说JSON文件
    for json_file in novel_json_files:
        logger.info(f"处理小说: {json_file}")
        
        # 提取小说名称和章节信息
        novel_name = os.path.basename(os.path.dirname(json_file))
        json_filename = os.path.splitext(os.path.basename(json_file))[0]
        
        # 读取JSON文件获取实际章节名称
        with open(json_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        chapter_name = config.get("chapter", "")
        chapter_clean_name = chapter_name.replace("\n", "").replace(" ", "_").replace(":", "-")
        
        # 处理多种可能的目录命名
        possible_dir_names = [
            chapter_clean_name,  # 基于章节名称的目录（如：第一章_小镇少年）
            json_filename,       # 基于JSON文件名的目录（如：剑来第一章-入山门青峰山）
            os.path.splitext(os.path.basename(json_file))[0]  # 同样基于JSON文件名
        ]
        
        # 创建输出目录结构（使用正确的章节名称）
        chapter_dir = os.path.join(output_dir, novel_name, chapter_clean_name)
        bgm_dir = os.path.join(chapter_dir, "背景音")
        effect_dir = os.path.join(chapter_dir, "音效")
        
        # 确保目录存在
        os.makedirs(bgm_dir, exist_ok=True)
        os.makedirs(effect_dir, exist_ok=True)
        
        # 提取音频参数
        bgm_params_list, effect_params_list = extract_audio_params(json_file)
        
        # 处理BGM文件
        for bgm_params in bgm_params_list:
            # 生成固定文件名（使用场景序号替代时长）
            bgm_duration = 10.0  # 默认BGM时长
            bgm_filename = generate_audio_filename(bgm_params["scene_en"], bgm_duration, "music")
            src_bgm_file = os.path.join(temp_dir, f"{bgm_filename}.wav")
            
            # 生成目标文件名 - 格式：bgm_line_小镇街巷_1.wav（使用场景序号替代时长）
            bgm_scene_cn = bgm_params["scene"].replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            scene_id = bgm_params["scene_id"]  # 使用场景序号
            dst_bgm_file = os.path.join(bgm_dir, f"bgm_line_{bgm_scene_cn}_{scene_id}.wav")
            
            # 检查目标文件是否已经存在
            if os.path.exists(dst_bgm_file):
                logger.info(f"BGM文件已存在，跳过处理: {dst_bgm_file}")
                continue
            
            # 检查临时目录中是否存在源文件
            if os.path.exists(src_bgm_file):
                # 复制文件
                shutil.copy2(src_bgm_file, dst_bgm_file)
                logger.info(f"已复制BGM文件: {src_bgm_file} -> {dst_bgm_file}")
            else:
                logger.warning(f"BGM文件不存在，将自动生成: {src_bgm_file}")
                # 调用audio_engine生成BGM
                try:
                    from audio_processing_module import AudioEngine
                    
                    # 初始化音频引擎
                    audio_engine = AudioEngine(
                        temp_dir=temp_dir,
                        sample_rate=44100,
                        channels=1
                    )
                    
                    # 生成BGM音频
                    bgm_audio = audio_engine.text_to_audio(
                        desc_en=bgm_params["scene_en"],
                        volume=bgm_params["volume"],
                        pitch=bgm_params["pitch"],
                        duration=bgm_duration,
                        audio_type="music"
                    )
                    
                    # 保存到临时目录
                    bgm_audio.export(src_bgm_file, format="wav")
                    logger.info(f"已生成BGM文件: {src_bgm_file}")
                    
                    # 复制到目标目录
                    shutil.copy2(src_bgm_file, dst_bgm_file)
                    logger.info(f"已复制BGM文件: {src_bgm_file} -> {dst_bgm_file}")
                except Exception as e:
                    logger.error(f"生成BGM失败: {e}")
        
        # 处理音效文件
        for effect_params in effect_params_list:
            # 生成固定文件名
            effect_duration = effect_params["duration"]
            effect_filename = generate_audio_filename(effect_params["sound_en"], effect_duration, "sound")
            src_effect_file = os.path.join(temp_dir, f"{effect_filename}.wav")
            
            # 生成目标文件名 - 格式：effect_line_脚步声_1.wav（使用场景序号替代时长）
            effect_name = effect_params["name"].replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            scene_id = effect_params["scene_id"]  # 使用场景序号
            dst_effect_file = os.path.join(effect_dir, f"effect_line_{effect_name}_{scene_id}.wav")
            
            # 检查目标文件是否已经存在
            if os.path.exists(dst_effect_file):
                logger.info(f"音效文件已存在，跳过处理: {dst_effect_file}")
                continue
            
            # 检查临时目录中是否存在源文件
            if os.path.exists(src_effect_file):
                # 复制文件
                shutil.copy2(src_effect_file, dst_effect_file)
                logger.info(f"已复制音效文件: {src_effect_file} -> {dst_effect_file}")
            else:
                logger.warning(f"音效文件不存在，将自动生成: {src_effect_file}")
                # 调用audio_engine生成音效
                try:
                    from audio_processing_module import AudioEngine
                    
                    # 初始化音频引擎
                    audio_engine = AudioEngine(
                        temp_dir=temp_dir,
                        sample_rate=44100,
                        channels=1
                    )
                    
                    # 生成音效音频
                    effect_audio = audio_engine.text_to_audio(
                        desc_en=effect_params["sound_en"],
                        volume=effect_params["volume"],
                        pitch=effect_params["pitch"],
                        duration=effect_duration,
                        audio_type="sound"
                    )
                    
                    # 保存到临时目录
                    effect_audio.export(src_effect_file, format="wav")
                    logger.info(f"已生成音效文件: {src_effect_file}")
                    
                    # 复制到目标目录
                    shutil.copy2(src_effect_file, dst_effect_file)
                    logger.info(f"已复制音效文件: {src_effect_file} -> {dst_effect_file}")
                except Exception as e:
                    logger.error(f"生成音效失败: {e}")


def main():
    """
    主函数
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="背景音和音效预处理工具")
    parser.add_argument("--script-dir", type=str, default="./小说剧本", 
                       help="小说剧本目录路径")
    parser.add_argument("--output-dir", type=str, default="../../output", 
                       help="输出目录路径")
    parser.add_argument("--temp-dir", type=str, default="../../output/temp", 
                       help="临时音频目录路径")
    
    args = parser.parse_args()
    
    # 转换为绝对路径
    script_dir = os.path.abspath(args.script_dir)
    output_dir = os.path.abspath(args.output_dir)
    temp_dir = os.path.abspath(args.temp_dir)
    
    logger.info(f"小说剧本目录: {script_dir}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"临时音频目录: {temp_dir}")
    
    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    # 检查并复制音频文件
    check_and_copy_audio_files(script_dir, output_dir, temp_dir)
    
    logger.info("背景音和音效预处理完成")


if __name__ == "__main__":
    main()