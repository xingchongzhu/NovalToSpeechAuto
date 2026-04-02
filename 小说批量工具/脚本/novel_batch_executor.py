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
    
    def __init__(self, script_dir: str, output_dir: str, temp_dir: str, api_endpoint: str = "http://localhost:3000/api/v1/tts/generateJson", tts_engine: str = "qwen3-tts", qwen_model_path: str = None):
        self.script_dir = script_dir  # 小说剧本目录
        self.output_dir = output_dir  # 输出目录
        self.temp_dir = temp_dir      # 临时目录
        self.api_endpoint = api_endpoint  # API端点
        self.tts_engine = tts_engine  # TTS引擎类型
        self.qwen_model_path = qwen_model_path  # Qwen TTS模型路径
        self.script_path = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录
        
        # 创建目录
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 获取其他脚本路径
        self.audio_processing_module = os.path.join(self.script_path, "audio_processing_module.py")
        
    def check_and_start_service(self) -> bool:
        """检查并启动服务"""
        # 只有当使用easyvoice引擎时才需要启动Docker服务
        if self.tts_engine != "easyvoice":
            logger.info(f"使用{self.tts_engine}引擎，不需要启动Docker服务")
            return True
        
        try:
            # 检查是否有旧的Docker容器在运行
            result = subprocess.run(["docker", "ps", "-a", "--filter", "name=easyvoice"], 
                                  capture_output=True, text=True, check=False)
            if "easyvoice" in result.stdout:
                logger.warning("发现旧的easyvoice容器，尝试停止并删除")
                subprocess.run(["docker", "stop", "easyvoice"], capture_output=True, text=True)
                subprocess.run(["docker", "rm", "easyvoice"], capture_output=True, text=True)
                time.sleep(2)
            
            # 使用Docker启动服务
            logger.info("使用Docker启动easyVoice服务...")
            audio_dir = os.path.join(os.path.dirname(self.script_dir), "audio")
            os.makedirs(audio_dir, exist_ok=True)
            
            cmd = [
                "docker", "run", "-d", "--name", "easyvoice", "-p", "3000:3000", 
                "-v", f"{audio_dir}:/app/audio", "cosincox/easyvoice:latest"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                logger.info("easyVoice服务启动成功")
                return True
            else:
                logger.error(f"服务启动失败，请检查Docker容器日志: docker logs easyvoice")
                return False
                
        except Exception as e:
            logger.error(f"启动服务时发生错误: {e}")
            return False
    
    def find_novel_json_files(self) -> List[str]:
        """查找所有小说JSON文件"""
        novel_json_files = []
        
        # 遍历小说剧本目录
        for novel_name in os.listdir(self.script_dir):
            novel_path = os.path.join(self.script_dir, novel_name)
            if os.path.isdir(novel_path):
                # 遍历小说目录下的JSON文件
                for file_name in os.listdir(novel_path):
                    if file_name.endswith(".json"):
                        json_file = os.path.join(novel_path, file_name)
                        novel_json_files.append(json_file)
        
        return novel_json_files
    
    def process_single_novel(self, json_file: str) -> Optional[str]:
        """处理单个小说JSON文件"""
        try:
            logger.info(f"开始处理小说: {json_file}")
            
            # 使用audio_processing_module.py处理
            cmd = [
                sys.executable,  # 使用当前Python解释器
                self.audio_processing_module,
                "--json-path", json_file,
                "--output-dir", self.output_dir,
                "--api-endpoint", self.api_endpoint,
                "--tts-engine", self.tts_engine,
                "--qwen-model-path", self.qwen_model_path if self.qwen_model_path else "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-model"
            ]
            
            result = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True, check=False)
            if result.returncode == 0:
                logger.info(f"小说处理完成: {json_file}")
            else:
                logger.error(f"处理小说失败: {json_file}")
                return None
            
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
        """批量处理所有小说"""
        # 检查并启动服务
        if not self.check_and_start_service():
            logger.error("服务启动失败，无法继续执行")
            return []
        
        # 查找所有小说JSON文件
        novel_json_files = self.find_novel_json_files()
        if not novel_json_files:
            logger.warning("未找到小说JSON文件")
            return []
        
        logger.info(f"找到 {len(novel_json_files)} 个小说JSON文件")
        
        # 处理所有小说
        processed_files = []
        for json_file in novel_json_files:
            output_path = self.process_single_novel(json_file)
            if output_path:
                processed_files.append(output_path)
        
        return processed_files
    
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
    parser.add_argument("--api-endpoint", type=str, default="http://localhost:3000/api/v1/tts/generateJson", 
                       help="API端点")
    parser.add_argument("--tts-engine", type=str, default="qwen3-tts", 
                       help="TTS引擎类型 (easyvoice 或 qwen3-tts)")
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
        api_endpoint=args.api_endpoint,
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