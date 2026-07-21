#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Novel Batch Processor
结合audio_processing_module.py和novel_audio_synthesizer.sh的功能
自动解析小说剧本目录下的所有剧本文件，生成小说配音+音效+背景音，并完成自动混音拼接
"""

import os
import sys
import json
import time
import argparse
import logging
import subprocess
from typing import List, Dict, Any, Optional

# 添加脚本所在目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class NovelBatchGenerator:
    """小说批量生成器"""
    
    def __init__(self, script_dir: str, output_dir: str, temp_dir: str, tts_engine: str = "qwen3-tts", qwen_model_path: str = None, sfx_engine: str = "woosh", bgm_engine: str = "stable-audio-3", platform: str = "default", sort_mode: str = "pinyin", tts_mode: str = "voice_design"):
        self.script_dir = script_dir  # 小说剧本目录的上级目录
        self.output_dir = output_dir  # 音频输出目录
        self.temp_dir = temp_dir  # 临时目录
        self.tts_engine = tts_engine
        self.tts_mode = tts_mode  # "clone" | "voice_design"
        self.qwen_model_path = qwen_model_path  # None 时由 audio_processing_module 自动选
        self.sfx_engine = sfx_engine  # 音效引擎
        self.bgm_engine = bgm_engine  # 背景音引擎
        self.platform = platform  # 输出平台
        self.script_path = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录
        self.sort_mode = sort_mode    # 排序模式
        
        # 创建目录
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 获取其他脚本路径
        self.audio_processing_module = os.path.join(self.script_path, "audio_processing_module.py")
    
    def extract_chapter_number(self, file_name: str) -> int:
        """从文件名中提取章节号
        
        支持的格式:
        - 第1章、第1回、第1节、第1话
        - 第01章、第001回
        - 第壹章 (中文数字)
        
        Args:
            file_name: 文件名
            
        Returns:
            章节号，如果无法提取返回99999
        """
        import re
        
        # 尝试匹配各种章节格式
        patterns = [
            r'第(\d+)章',      # 第1章
            r'第(\d+)回',      # 第1回
            r'第(\d+)节',      # 第1节
            r'第(\d+)话',      # 第1话
            r'第(\d+)幕',      # 第1幕
            r'第(\d+)篇',      # 第1篇
            r'第(\d+)卷',      # 第1卷
            r'第(\d+)部',      # 第1部
            r'第(\d+)集',      # 第1集
            r'第(\d+)小节',    # 第1小节
            r'(\d+)章',        # 1章（无前缀）
            r'(\d+)回',        # 1回（无前缀）
        ]
        
        for pattern in patterns:
            match = re.search(pattern, file_name)
            if match:
                return int(match.group(1))
        
        # 尝试匹配中文数字
        chinese_nums = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
                       '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
                       '百': 100, '千': 1000, '万': 10000}
        
        # 匹配"第X章"格式（中文数字）
        chinese_pattern = r'第([零一二三四五六七八九十百千万]+)章'
        match = re.search(chinese_pattern, file_name)
        if match:
            chinese_num = match.group(1)
            total = 0
            current = 0
            for char in chinese_num:
                if char in chinese_nums:
                    value = chinese_nums[char]
                    if value >= 10:
                        total += current * value
                        current = 0
                    else:
                        current = value
            total += current
            return total if total > 0 else 99999
        
        # 无法提取章节号，返回一个很大的数放在最后
        return 99999
    
    def get_pinyin_key(self, text: str) -> str:
        """获取文本的拼音排序键（通用中文拼音排序）
        
        Args:
            text: 中文字符串
            
        Returns:
            拼音字符串，用于排序
        """
        try:
            from pypinyin import lazy_pinyin
            return ''.join(lazy_pinyin(text))
        except ImportError:
            import locale
            try:
                locale.setlocale(locale.LC_COLLATE, 'zh_CN.UTF-8')
                return locale.strxfrm(text)
            except:
                return text
    
    def find_novel_json_files(self) -> List[str]:
        """查找所有小说JSON文件并按指定方式排序（保留原有行为，供外部调用）"""
        groups = self.find_novel_json_files_by_album()
        novel_json_files = []
        for _, files in groups:
            novel_json_files.extend(files)
        return novel_json_files

    def find_novel_json_files_by_album(self) -> List[tuple]:
        """查找所有小说JSON文件，按专辑目录字母序分组，组内按章节号排序。

        Returns:
            list of (album_dir_name, [json_file_path, ...])，按目录名字母序排列。
        """
        # 收集各目录下的文件
        album_map: Dict[str, List[str]] = {}

        for item in sorted(os.listdir(self.script_dir)):
            item_path = os.path.join(self.script_dir, item)
            if os.path.isdir(item_path):
                files = [
                    os.path.join(item_path, f)
                    for f in os.listdir(item_path)
                    if f.endswith(".json")
                ]
                if files:
                    album_map[item] = files
            elif item.endswith(".json"):
                # 根目录下的散文件归入虚拟专辑 ""
                album_map.setdefault("", []).append(os.path.join(self.script_dir, item))

        # 按目录名字母序排列专辑
        sorted_albums = sorted(album_map.keys())

        result = []
        for album in sorted_albums:
            files = album_map[album]
            # 组内按章节号排序
            files.sort(key=lambda x: self.extract_chapter_number(os.path.basename(x)))
            result.append((album, files))

        return result
    
    def process_single_novel(self, json_file: str) -> Optional[str]:
        """处理单个小说JSON文件"""
        try:
            logger.info(f"开始处理小说: {json_file}")
            
            # 即使没有提取到输出路径，也返回一个默认的输出路径
            # 默认输出路径为：输出目录/小说名称/章节名称.格式
            novel_name = os.path.basename(os.path.dirname(json_file))
            chapter_name = os.path.splitext(os.path.basename(json_file))[0]
            output_ext = "mp3" if self.platform == "ximalaya" else "wav"
            default_output_path = os.path.join(self.output_dir, novel_name, f"{chapter_name}.{output_ext}")
            
            return default_output_path
            
        except Exception as e:
            logger.error(f"处理小说时发生错误: {e}")
            return None
    
    def batch_process(self) -> List[str]:
        """批量处理所有小说JSON文件。

        按专辑目录字母序逐专辑处理，每个专辑内部按章节号顺序处理，
        完成一个专辑的全部章节后再开始下一个专辑。
        """
        try:
            albums = self.find_novel_json_files_by_album()
            total = sum(len(files) for _, files in albums)
            logger.info(f"找到 {len(albums)} 个专辑，共 {total} 个剧本文件")

            if total == 0:
                logger.warning("未找到小说JSON文件")
                return []

            output_paths = []
            output_ext = "mp3" if self.platform == "ximalaya" else "wav"

            for album_name, json_files in albums:
                display = album_name if album_name else "(根目录)"
                logger.info(f"========== 开始处理专辑: {display} ({len(json_files)} 章) ==========")

                # audio_processing_module.py 的 process_all_novels 扫描
                # --script-dir 下的子目录，每个子目录里的 json 是章节。
                # 因此需要传专辑目录的父目录（小说剧本/），而不是专辑目录本身。
                album_script_dir = self.script_dir

                cmd = [
                    sys.executable,
                    self.audio_processing_module,
                    "--script-dir", album_script_dir,
                    "--output-dir", self.output_dir,
                    "--tts-engine", self.tts_engine,
                    "--sfx-engine", self.sfx_engine,
                    "--bgm-engine", self.bgm_engine,
                    "--platform", self.platform,
                    "--tts-mode", self.tts_mode,
                ]
                if self.qwen_model_path:
                    cmd.extend(["--qwen-model-path", self.qwen_model_path])

                result = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True, check=False)

                if result.returncode == 0:
                    logger.info(f"专辑 [{display}] 处理完成")
                else:
                    logger.error(f"专辑 [{display}] 处理失败，退出码: {result.returncode}")

                for json_file in json_files:
                    novel_name = os.path.basename(os.path.dirname(json_file))
                    chapter_name = os.path.splitext(os.path.basename(json_file))[0]
                    output_path = os.path.join(self.output_dir, novel_name, f"{chapter_name}.{output_ext}")
                    output_paths.append(output_path)

            return output_paths

        except Exception as e:
            logger.error(f"批量处理时发生错误: {e}")
            return []
    

    
    def cleanup(self, keep_segments: bool = False) -> None:
        """清理临时文件"""
        try:
            logger.info("清理临时文件...")
            
            if not keep_segments and os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.info(f"已清理临时目录: {self.temp_dir}")
            
        except Exception as e:
            logger.error(f"清理临时文件时发生错误: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="小说自动批量生成工具")
    # 获取脚本所在目录的绝对路径
    script_path = os.path.dirname(os.path.abspath(__file__))
    # 计算项目根目录的绝对路径（脚本目录的上两级）
    project_root = os.path.abspath(os.path.join(script_path, "../.."))
    
    parser.add_argument("--script-dir", type=str, default="./novel_scripts", 
                       help="小说剧本目录路径")
    parser.add_argument("--output-dir", type=str, default=os.path.join(project_root, "output"), 
                       help="输出目录路径")
    parser.add_argument("--temp-dir", type=str, default=os.path.join(script_path, "temp"), 
                       help="临时目录路径")
    parser.add_argument("--tts-engine", type=str, default="qwen3-tts", 
                       help="TTS引擎类型 (voxcpm | qwen3-tts)")
    parser.add_argument("--sfx-engine", type=str, default="woosh",
                       help="音效生成引擎: woosh | stable-audio-3 (默认: woosh)")
    parser.add_argument("--bgm-engine", type=str, default="stable-audio-3",
                       help="背景音生成引擎: stable-audio-3 | woosh (默认: stable-audio-3)")
    parser.add_argument("--qwen-model-path", type=str, default="Qwen/Qwen3-TTS-12Hz-1.7B-Base", 
                       help="Qwen TTS模型路径")
    parser.add_argument("--platform", type=str, default="ximalaya",
                       help="输出平台配置，如 default | ximalaya")
    parser.add_argument("--keep-segments", action="store_true", 
                       help="保留临时片段文件")
    parser.add_argument("--debug", action="store_true", 
                       help="启用调试日志")
    parser.add_argument("--sort-mode", type=str, default="pinyin",
                       help="排序模式: pinyin(拼音排序，默认) | chapter(章节号排序) | name(文件名排序)")
    parser.add_argument("--tts-mode", type=str, default="voice_design",
                       help="TTS 合成模式: voice_design(文字描述造音色，默认) | clone(克隆音频)")
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # 转换为绝对路径
    script_dir = os.path.abspath(args.script_dir)
    output_dir = os.path.abspath(args.output_dir)
    temp_dir = os.path.abspath(args.temp_dir)
    
    logger.info(f"小说剧本目录: {script_dir}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"临时目录: {temp_dir}")
    
    # 创建生成器
    generator = NovelBatchGenerator(
        script_dir=script_dir,
        output_dir=output_dir,
        temp_dir=temp_dir,
        tts_engine=args.tts_engine,
        qwen_model_path=args.qwen_model_path,
        sfx_engine=args.sfx_engine,
        bgm_engine=args.bgm_engine,
        platform=args.platform,
        sort_mode=args.sort_mode,
        tts_mode=args.tts_mode,
    )
    
    logger.info(f"排序模式: {args.sort_mode}")
    
    try:
        # 批量处理
        processed_files = generator.batch_process()
        
        if processed_files:
            logger.info(f"批量处理完成，共生成 {len(processed_files)} 个音频文件")
            for file_path in processed_files:
                logger.info(f"- {file_path}")
        else:
            logger.warning("未生成任何音频文件")
            
    finally:
        # 清理临时文件
        generator.cleanup(keep_segments=args.keep_segments)

if __name__ == "__main__":
    main()