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
    
    def __init__(self, script_dir: str, output_dir: str, temp_dir: str, tts_engine: str = "qwen3-tts", qwen_model_path: str = None):
        self.script_dir = script_dir  # 小说剧本目录
        self.output_dir = output_dir  # 输出目录
        self.temp_dir = temp_dir      # 临时目录
        self.tts_engine = tts_engine  # TTS引擎类型
        self.qwen_model_path = qwen_model_path  # Qwen TTS模型路径
        self.script_path = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录
        
        # 创建目录
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 获取其他脚本路径
        self.audio_processing_module = os.path.join(self.script_path, "audio_processing_module.py")
        
    def find_novel_json_files(self) -> List[str]:
        """查找所有小说JSON文件"""
        novel_json_files = []
        
        # 遍历小说剧本目录
        for item in os.listdir(self.script_dir):
            item_path = os.path.join(self.script_dir, item)
            if os.path.isdir(item_path):
                # 遍历子目录下的JSON文件
                for file_name in os.listdir(item_path):
                    if file_name.endswith(".json"):
                        json_file = os.path.join(item_path, file_name)
                        novel_json_files.append(json_file)
            elif item.endswith(".json"):
                # 直接处理当前目录中的JSON文件
                json_file = os.path.join(self.script_dir, item)
                novel_json_files.append(json_file)
        
        return novel_json_files
    
    def process_single_novel(self, json_file: str) -> Optional[str]:
        """处理单个小说JSON文件"""
        try:
            logger.info(f"开始处理小说: {json_file}")
            
            # 即使没有提取到输出路径，也返回一个默认的输出路径
            # 默认输出路径为：输出目录/小说名称/章节名称.wav
            novel_name = os.path.basename(os.path.dirname(json_file))
            chapter_name = os.path.splitext(os.path.basename(json_file))[0]
            default_output_path = os.path.join(self.output_dir, novel_name, f"{chapter_name}.wav")
            
            return default_output_path
            
        except Exception as e:
            logger.error(f"处理小说时发生错误: {e}")
            return None
    
    def batch_process(self) -> List[str]:
        """批量处理所有小说JSON文件"""
        try:
            # 查找所有小说JSON文件
            novel_json_files = self.find_novel_json_files()
            logger.info(f"找到 {len(novel_json_files)} 个小说JSON文件")
            
            if not novel_json_files:
                logger.warning("未找到小说JSON文件")
                return []
            
            # 使用audio_processing_module.py进行批处理
            cmd = [
                sys.executable,  # 使用当前Python解释器
                self.audio_processing_module,
                "--script-dir", self.script_dir,
                "--output-dir", self.output_dir,
                "--tts-engine", self.tts_engine,
                "--qwen-model-path", self.qwen_model_path if self.qwen_model_path else "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model"
            ]
            
            logger.info("开始批量处理小说...")
            result = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True, check=False)
            
            if result.returncode == 0:
                logger.info("批量处理完成")
            else:
                logger.error("批量处理失败")
                return []
            
            # 构建输出路径列表
            output_paths = []
            for json_file in novel_json_files:
                novel_name = os.path.basename(os.path.dirname(json_file))
                chapter_name = os.path.splitext(os.path.basename(json_file))[0]
                output_path = os.path.join(self.output_dir, novel_name, f"{chapter_name}.wav")
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
    
    parser.add_argument("--script-dir", type=str, default="./小说剧本", 
                       help="小说剧本目录路径")
    parser.add_argument("--output-dir", type=str, default=os.path.join(project_root, "output"), 
                       help="输出目录路径")
    parser.add_argument("--temp-dir", type=str, default=os.path.join(script_path, "temp"), 
                       help="临时目录路径")
    parser.add_argument("--tts-engine", type=str, default="qwen3-tts", 
                       help="TTS引擎类型 (qwen3-tts)")
    parser.add_argument("--qwen-model-path", type=str, default="/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model", 
                       help="Qwen TTS模型路径")
    parser.add_argument("--keep-segments", action="store_true", 
                       help="保留临时片段文件")
    parser.add_argument("--debug", action="store_true", 
                       help="启用调试日志")
    
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
        qwen_model_path=args.qwen_model_path
    )
    
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