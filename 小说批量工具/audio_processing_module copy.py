#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Processing Module
音频处理模块，提供语音合成、音频处理和混音功能

包含的主要功能：
- 定义音频参数数据结构
- 音频合成引擎接口
- 音频处理工具函数
- 音频混音功能
"""

import json
import os
import time
import requests
import sys
import logging
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import warnings
import multiprocessing
from functools import partial

# 导入generate_audio模块
try:
    from stabilityai_stable_generate_audio import generate_audio, generate_audio_batch
    GENERATE_AUDIO_AVAILABLE = True
except Exception as e:
    print(f"[AudioEngine] 导入generate_audio模块失败: {e}")
    GENERATE_AUDIO_AVAILABLE = False
    
    def generate_audio_batch(tasks):
        """批量生成的降级实现"""
        results = []
        for prompt, duration, output_path in tasks:
            try:
                print(f"[AudioEngine] 跳过批量生成（模块未导入）: {output_path}")
                results.append(None)
            except:
                results.append(None)
        return results

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 禁用输出缓冲，确保日志实时显示
sys.stdout.reconfigure(line_buffering=True)  # Python 3.7+
os.environ['PYTHONUNBUFFERED'] = '1'  # 环境变量方式，兼容所有Python版本
clone_audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"

# 忽略音频处理库的无关警告
warnings.filterwarnings("ignore")

try:
    import pydub
    from pydub import AudioSegment, effects
    from pydub.playback import play
except ImportError:
    logger.warning("⚠️ 未安装音频处理依赖，执行: pip install pydub ffmpeg-python")
    print("⚠️ 需安装 FFmpeg: https://ffmpeg.org/download.html")
    raise


# ======================== 数据结构定义 ========================
@dataclass
class VoiceParams:
    """语音参数数据类"""
    text: str
    role: str
    role_voice: str
    speed: str  # 百分比格式，如 "+35%"
    volume: str  # 百分比格式，如 "+0%"
    pitch: str   # 赫兹格式，如 "+0Hz"
    instruct: Optional[str] = None  # 可选的语音指令，用于控制语气和情绪

@dataclass
class BGMAudioParams:
    """BGM音频参数数据类"""
    scene: str
    scene_cn: str
    scene_en: str
    fade_in: float
    fade_out: float
    volume: str
    pitch: str
    play_mode: str  # cover_voice / keep / lower
    lower_db: Optional[float] = None

@dataclass
class EffectAudioParams:
    """音效参数数据类"""
    name: str
    sound_cn: str
    sound_en: str
    volume: str
    pitch: str
    trigger_delay: float
    duration: float

@dataclass
class MixConfig:
    """混音配置数据类"""
    mode: str  # bgm_fade_in_then_voice / voice_on_bgm / mix
    voice_delay: Optional[float] = None  # 语音延迟（秒）

@dataclass
class LineAudioConfig:
    """单句音频配置数据类"""
    id: int
    role: str
    voice_params: VoiceParams
    bgm_params: Optional[BGMAudioParams]
    effect_params: List[EffectAudioParams]
    mix_config: MixConfig


# ======================== 音频引擎接口（预留对接） ========================
class AudioEngine:
    """音频引擎基类，预留对接实际TTS/文生音频接口"""
    
    def __init__(self, temp_dir: str = "./temp_audio", sample_rate: int = 44100, channels: int = 1, api_endpoint: str = "http://localhost:3000/api/v1/tts/generateJson", tts_engine: str = "qwen3-tts", qwen_model_path: str = None):
        self.temp_dir = temp_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_format = "wav"
        self.api_endpoint = api_endpoint
        self.tts_engine = tts_engine
        self.qwen_model_path = qwen_model_path
        self.qwen_tts_model = None
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 初始化指定的TTS引擎
        if self.tts_engine == "qwen3-tts":
            self._init_qwen_tts_model()

    def _init_qwen_tts_model(self):
        """
        初始化Qwen3-TTS模型
        """
        try:
            # 导入前设置日志级别，抑制Qwen3-TTS库的INFO日志
            import logging
            logging.getLogger('qwen_tts').setLevel(logging.WARNING)
            logging.getLogger('transformers').setLevel(logging.WARNING)
            logging.getLogger('torch').setLevel(logging.WARNING)
            
            from qwen_tts import Qwen3TTSModel
            import torch
            
            print("[TTSEngine] 初始化Qwen3-TTS模型...")
            
            # 使用本地的base模型路径，支持语音克隆
            model_path = self.qwen_model_path if self.qwen_model_path else "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model"
            
            self.qwen_tts_model = Qwen3TTSModel.from_pretrained(
                model_path,
                device_map="cpu",  # 强制使用CPU，避免meta device问题
                dtype=torch.float32,  # 使用float32，更稳定
            )
            
            # 保存模型类型，以便后续使用
            self.qwen_model_type = getattr(self.qwen_tts_model.model, 'tts_model_type', 'unknown')
            print(f"[TTSEngine] Qwen3-TTS模型初始化成功! 使用模型路径: {model_path}")
            print(f"[TTSEngine] 模型类型: {self.qwen_model_type}")
        except Exception as e:
            print(f"[TTSEngine] 初始化Qwen3-TTS模型失败: {e}")
            self.qwen_model_type = "unknown"
            raise Exception("Qwen3-TTS模型初始化失败")

    def text_to_speech(self, params: VoiceParams) -> AudioSegment:
        """
        文本转语音接口，使用Qwen3-TTS引擎
        :param params: 语音参数
        :return: 生成的语音音频段
        """
        print(f"\n[TTSEngine] 使用引擎: {self.tts_engine}")
        print(f"[TTSEngine] 生成[{params.role}]语音: {params.text[:20]}...")
        print(f"  - 音色: {params.role_voice} | 语速: {params.speed} | 音量: {params.volume} | 音调: {params.pitch}")
        
        try:
            start_time = time.time()
            if self.tts_engine == "qwen3-tts":
                print("[TTSEngine] 开始生成语音，预计需要几秒钟...")
                audio = self._text_to_speech_qwen(params)
                elapsed_time = time.time() - start_time
                print(f"[TTSEngine] 语音生成完成，耗时: {elapsed_time:.2f} 秒")
                # 应用语速、音量、音调调整
                audio = self._adjust_audio_params(audio, params.speed, params.volume, params.pitch)
                return audio
            else:
                raise ValueError(f"未知的TTS引擎: {self.tts_engine}")
        except Exception as e:
            print(f"[TTSEngine] 语音生成失败: {e}")
            raise
            
    def _text_to_speech_qwen(self, params: VoiceParams) -> AudioSegment:
        """
        使用Qwen3-TTS引擎生成语音
        :param params: 语音参数
        :return: 生成的语音音频段
        """
        if self.qwen_tts_model is None:
            print("[TTSEngine] Qwen3-TTS模型未初始化，尝试初始化...")
            self._init_qwen_tts_model()
            if self.qwen_tts_model is None:
                raise Exception("Qwen3-TTS模型初始化失败")
        
        print("[TTSEngine] 使用Qwen3-TTS生成语音...")
        
        # 获取speaker参数，如果不存在则使用默认值
        qwen_speaker = params.role_voice if params.role_voice else "阿传-男声-低沉,浑厚"
        
        # 处理instruct参数
        # 1. 如果VoiceParams中有instruct字段且不为空，使用该instruct
        # 2. 否则，使用默认的语速指令
        if params.instruct and params.instruct.strip():
            instruct = params.instruct.strip()
        else:
            # 使用默认情绪
            instruct = "neutral"
        
        # 调试信息
        print(f"[DEBUG] 参数详情 - 角色: {params.role}, 文本: '{params.text}', 音色: {qwen_speaker}")
        print(f"[DEBUG] instruct参数: {instruct}")
        print(f"[DEBUG] 模型类型: {self.qwen_model_type}")
        
        # 辅助方法：查找音频文件
        def _find_audio_file(speaker_name):
            """查找指定speaker的音频文件"""
            for ext in ['.mp3', '.wav']:
                potential_path = os.path.join(clone_audio_dir, f"{speaker_name}{ext}")
                if os.path.exists(potential_path):
                    return potential_path
            return None
        
        # 辅助方法：生成语音
        def _generate_voice(ref_audio, x_vector_only_mode=True):
            """
            使用指定的参考音频生成语音
            
            参数说明:
                ref_audio: 参考音频路径，None表示使用内置speaker
                x_vector_only_mode: 是否仅使用x向量模式（True=只克隆音色，False=完整克隆）
                
            generate_voice_clone 参数说明:
                text: 要合成的文本
                language: 语言，固定为"chinese"
                ref_audio: 参考音频路径
                ref_text: 参考文本（留空即可）
                x_vector_only_mode: 是否仅使用x向量（推荐True，更稳定）
                style: 风格/情绪（如: neutral, happy, sad, angry等）
                temperature: 温度系数，控制随机性 (推荐范围: 0.1-0.5，越低越稳定)
                top_p: 核采样参数 (推荐范围: 0.5-0.9)
                repetition_penalty: 重复惩罚 (推荐范围: 1.0-1.2)
            """
            return self.qwen_tts_model.generate_voice_clone(
                text=params.text,
                language="chinese",
                ref_audio=ref_audio,
                ref_text="",
                x_vector_only_mode=x_vector_only_mode,
                style=params.instruct if params.instruct else "neutral",
                temperature=qwen_temperature,
                top_p=0.6,
                repetition_penalty=1.05
            )
        
        # 检查是否是克隆语音（总是使用克隆语音）
        # qwen_temperature: 语音生成温度参数，控制输出语音的随机性
        # 取值范围: 0.0-1.0，较低值(0.1-0.3)生成更稳定一致的语音，较高值(0.5-1.0)生成更多样化的语音
        qwen_temperature = 0.25
        wavs, sr = None, None
        
        try:
            # 尝试寻找参考音频文件
            print(f"[TTSEngine] 尝试使用克隆语音: {qwen_speaker}")
            ref_audio_path = _find_audio_file(qwen_speaker)
            
            if ref_audio_path:
                print(f"[TTSEngine] 找到克隆音频文件: {ref_audio_path}")
                # 检查模型是否支持语音克隆
                if hasattr(self.qwen_tts_model, 'generate_voice_clone'):
                    # 使用克隆语音生成
                    wavs, sr = _generate_voice(ref_audio_path)
                else:
                    print(f"[TTSEngine] 当前模型不支持语音克隆功能")
                    wavs = None
            else:
                print(f"[TTSEngine] 找不到参考音频文件: {qwen_speaker}.mp3 或 {qwen_speaker}.wav")
                # 使用默认克隆声音
                print(f"[TTSEngine] 使用默认克隆声音")
                # 根据角色性别选择默认克隆声音
                if "女" in params.role or "宁姚" in params.role or "稚圭" in params.role:
                    # 女生使用晓辰-女青年.mp3
                    default_clone_audio = os.path.join(clone_audio_dir, "晓辰-女青年.mp3")
                    print("[TTSEngine] 使用默认女声: 晓辰-女青年.mp3")
                else:
                    # 男生使用知浩-男青年.mp3
                    default_clone_audio = os.path.join(clone_audio_dir, "知浩-男青年.mp3")
                    print("[TTSEngine] 使用默认男声: 知浩-男青年.mp3")
                
                if os.path.exists(default_clone_audio):
                    print(f"[TTSEngine] 找到默认克隆音频文件: {default_clone_audio}")
                    wavs, sr = _generate_voice(default_clone_audio)
                else:
                    print(f"[TTSEngine] 找不到默认参考音频文件: {default_clone_audio}")
                    wavs = None
            
            # 如果前面的尝试都失败了，使用内置speaker
            if wavs is None:
                # 对于base模型，使用generate_voice_clone方法，即使是内置speaker
                print(f"[TTSEngine] 使用base模型，内置speaker: {qwen_speaker}")
                
                # 尝试使用默认的参考音频文件
                default_ref_audio = _find_audio_file(qwen_speaker)
                
                if default_ref_audio:
                    print(f"[TTSEngine] 使用默认参考音频: {default_ref_audio}")
                    wavs, sr = _generate_voice(default_ref_audio)
                else:
                    # 如果没有默认参考音频，使用内置speaker
                    print(f"[TTSEngine] 找不到默认参考音频: {qwen_speaker}.mp3 或 {qwen_speaker}.wav")
                    print(f"[TTSEngine] 使用内置speaker: {qwen_speaker}")
                    # 使用qwen3-tts的内置speaker
                    wavs, sr = _generate_voice(None, x_vector_only_mode=False)
        except Exception as e:
            print(f"[TTSEngine] 生成语音失败: {e}")
            raise
        
        print("[TTSEngine] Qwen3-TTS语音生成成功！")
        
        # 将numpy数组转换为AudioSegment
        audio_data = np.concatenate(wavs) if isinstance(wavs, list) else wavs
        
        # 确保音频数据在[-1, 1]范围内
        audio_data = np.clip(audio_data, -1, 1)
        
        # 归一化处理：确保音量稳定
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val * 0.9  # 归一化到最大幅度的90%
            print(f"[TTSEngine] 音频归一化处理，最大幅度: {max_val:.4f}")
        
        # 转换为16位整数
        audio_data_int16 = (audio_data * 32767).astype(np.int16)
        
        # 创建AudioSegment对象
        audio = AudioSegment(
            audio_data_int16.tobytes(),
            frame_rate=sr,
            sample_width=audio_data_int16.dtype.itemsize,
            channels=1
        )
        
        # 转换采样率和声道数
        audio = audio.set_frame_rate(self.sample_rate)
        audio = audio.set_channels(self.channels)
        
        # 优化：去除开头的奇怪声音
        # 1. 增加淡入时间到100ms
        audio = audio.fade_in(100)
        
        # 2. 去除开头的静音部分（如果有的话）
        # 找到第一个非静音点
        silent_threshold = -60  # 静音阈值（dB）
        for i in range(0, len(audio), 10):  # 每10ms检查一次
            if audio[i:i+10].dBFS > silent_threshold:
                audio = audio[i:]
                break
        
        # 3. 再次添加淡入效果确保平滑开始
        audio = audio.fade_in(100)
        return audio

    def text_to_audio(self, desc_en: str, volume: str, pitch: str, duration: float = 5.0, audio_type: str = "music") -> AudioSegment:
        """
        文生音频接口，调用stabilityai_stable_generate_audio.py生成BGM/音效
        :param desc_en: 英文描述（必须使用英文，模型对英文提示词效果最好）
        :param volume: 音量百分比
        :param pitch: 音调赫兹
        :param duration: 音频时长（秒）
        :param audio_type: 音频类型（music或sound）
        :return: 生成的音频段
        """
        print(f"[AudioEngine] 生成音频: {desc_en[:30]}...")
        print(f"[AudioEngine] 音频类型: {audio_type} | 时长: {duration}秒 | 音量: {volume} | 音调: {pitch}")
        
        # 检查是否有描述词
        if not desc_en:
            print("[AudioEngine] 没有获取到音频描述词，无法生成音频")
            # 返回静音音频
            silence = AudioSegment.silent(duration=int(duration*1000), frame_rate=self.sample_rate)
            return self._adjust_audio_params(silence, "+0%", volume, pitch)
        
        # 生成固定文件名（基于描述词、时长、音频类型），确保相同参数生成相同文件名
        import hashlib
        audio_params = f"{desc_en}_{duration}_{audio_type}"
        audio_hash = hashlib.md5(audio_params.encode()).hexdigest()[:16]
        fixed_file_name = f"{audio_type}_{audio_hash}_{int(duration)}"
        fixed_output_path = os.path.join(self.temp_dir, fixed_file_name)
        
        # 检查固定输出文件是否已存在
        actual_output_file = f"{fixed_output_path}.wav"
        if os.path.exists(actual_output_file) and os.path.getsize(actual_output_file) > 0:
            print(f"[AudioEngine] 音频文件已存在，跳过生成: {actual_output_file}")
            audio = AudioSegment.from_wav(actual_output_file)
            return audio
        
        # 使用stabilityai_stable_generate_audio生成音频
        print("[AudioEngine] 使用stabilityai_stable_generate_audio生成音频...")
        try:
            # 调整时长
            duration_int = max(1, int(round(duration)))
            print(f"[AudioEngine] 生成音频时长: {duration_int}秒")
            
            # 调用generate_audio接口
            generated_path = generate_audio(
                prompt=desc_en,
                duration=duration_int,
                output_path=fixed_output_path,
            )
            
            # 检查生成结果
            if generated_path and os.path.exists(generated_path) and os.path.getsize(generated_path) > 0:
                print(f"[AudioEngine] 音频生成成功: {generated_path}")
                
                # 读取生成的音频文件
                audio = AudioSegment.from_wav(generated_path)
                # 调整音频参数
                audio = self._adjust_audio_params(audio, "+0%", volume, pitch)
                return audio
        except requests.exceptions.RequestException as e:
            print(f"[AudioEngine] 网络连接失败，跳过BGM/音效生成: {e}")
        except Exception as e:
            print(f"[AudioEngine] 音频生成异常: {e}")
        
        # 生成失败时返回静音音频
        print("[AudioEngine] 返回静音音频")
        silence = AudioSegment.silent(duration=int(duration*1000), frame_rate=self.sample_rate)
        return self._adjust_audio_params(silence, "+0%", volume, pitch)
    
    def text_to_audio_batch(self, tasks: list, max_workers: int = 5) -> dict:
        """
        批量生成多个音频（多线程并行）
        :param tasks: 任务列表，每个任务是包含以下字段的字典:
                      - desc_en: 英文描述
                      - duration: 时长（秒）
                      - volume: 音量百分比
                      - pitch: 音调赫兹
                      - audio_type: 音频类型 (music/sound)
                      - output_path: 输出路径（不含扩展名）
        :param max_workers: 最大并行线程数（CPU上建议设为1）
        :return: 生成结果字典，key为output_path，value为AudioSegment或None
        """
        if not tasks or len(tasks) == 0:
            return {}
        
        print(f"\n[AudioEngine] 批量生成 {len(tasks)} 个音频...")
        
        # 构建批量任务
        batch_tasks = []
        for task in tasks:
            desc_en = task.get("desc_en", "")
            duration = task.get("duration", 5.0)
            output_path = task.get("output_path", None)
            
            if not desc_en or not output_path:
                print(f"[AudioEngine] 跳过无效任务: {task}")
                continue
            
            # 生成固定文件名（基于描述词、时长、音频类型）
            import hashlib
            audio_params = f"{desc_en}_{duration}_{task.get('audio_type', 'music')}"
            audio_hash = hashlib.md5(audio_params.encode()).hexdigest()[:16]
            fixed_file_name = f"{task.get('audio_type', 'music')}_{audio_hash}_{int(duration)}"
            
            # 检查是否已有文件
            actual_output_file = f"{output_path}.wav"
            if os.path.exists(actual_output_file) and os.path.getsize(actual_output_file) > 0:
                print(f"[AudioEngine] 音频文件已存在，跳过生成: {actual_output_file}")
                continue
            
            batch_tasks.append((desc_en, duration, output_path))
        
        # 执行批量生成
        if batch_tasks:
            print(f"[AudioEngine] 开始并行生成 {len(batch_tasks)} 个音频...")
            results = generate_audio_batch(batch_tasks)
            
            # 读取生成的音频文件
            output_dict = {}
            for (desc_en, duration, output_path), generated_path in zip(batch_tasks, results):
                actual_output_file = f"{output_path}.wav"
                if generated_path and os.path.exists(actual_output_file) and os.path.getsize(actual_output_file) > 0:
                    try:
                        audio = AudioSegment.from_wav(actual_output_file)
                        volume = next((t["volume"] for t in tasks if t.get("output_path") == output_path), "+0%")
                        pitch = next((t["pitch"] for t in tasks if t.get("output_path") == output_path), "+0Hz")
                        audio = self._adjust_audio_params(audio, "+0%", volume, pitch)
                        output_dict[output_path] = audio
                    except Exception as e:
                        print(f"[AudioEngine] 读取生成的音频失败 {actual_output_file}: {e}")
                        output_dict[output_path] = None
                else:
                    output_dict[output_path] = None
            return output_dict
        
        return {}

    def _adjust_audio_params(self, audio: AudioSegment, speed: str, volume: str, pitch: str) -> AudioSegment:
        """
        调整音频参数（语速/音量）
        :param audio: 原始音频段
        :param speed: 语速百分比
        :param volume: 音量百分比
        :param pitch: 音调赫兹（保留参数以保持兼容性）
        :return: 调整后的音频段
        """
        # 调整语速
        if speed and speed != "+0%":
            try:
                # 解析语速参数
                speed_value = int(speed.replace("%", ""))
                speed_factor = 1.0 + (speed_value / 100.0)
                
                # 确保速度因子在合理范围内
                if speed_factor <= 0:
                    print(f"[AudioEngine] 语速调整值过小，使用默认值")
                else:
                    print(f"[AudioEngine] 调整语速: {speed} -> 速度因子: {speed_factor}")
                    
                    # 使用FFmpeg来处理语速调整，这是最可靠的方法
                    import subprocess
                    import tempfile
                    import os
                    
                    # 创建临时文件
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_input:
                        audio.export(temp_input.name, format="wav")
                        temp_input_path = temp_input.name
                    
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_output:
                        temp_output_path = temp_output.name
                    
                    # 构建FFmpeg命令，使用atempo滤镜来调整语速
                    # atempo滤镜可以保持音调不变的同时调整速度
                    ffmpeg_cmd = [
                        "ffmpeg", "-i", temp_input_path,
                        "-filter:a", f"atempo={speed_factor}",
                        "-y", temp_output_path
                    ]
                    
                    # 执行命令
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        # 读取处理后的音频
                        audio = AudioSegment.from_wav(temp_output_path)
                        print(f"[AudioEngine] 语速调整成功，新时长: {len(audio)/1000:.2f}秒")
                    else:
                        print(f"[AudioEngine] FFmpeg处理失败: {result.stderr}")
                        # 如果FFmpeg失败，使用备用方法
                        print(f"[AudioEngine] 使用备用方法处理语速")
                        if speed_factor > 1:
                            # 快速处理
                            audio = audio.speedup(playback_speed=speed_factor, crossfade=25)
                        else:
                            # 慢速处理 - 使用简单的重复方法
                            new_duration = len(audio) / speed_factor
                            # 对于轻微的慢速，使用重复方法
                            if speed_factor >= 0.5:
                                # 计算需要重复的次数
                                repeat_times = int(1.0 / speed_factor)
                                # 重复音频并裁剪
                                audio = audio * repeat_times
                                audio = audio[:int(new_duration)]
                    
                    # 清理临时文件
                    os.unlink(temp_input_path)
                    os.unlink(temp_output_path)
            except Exception as e:
                print(f"[AudioEngine] 调整语速失败: {e}")
        
        # 调整音量
        if volume and volume != "+0%":
            try:
                # 解析音量参数
                volume_value = int(volume.replace("%", ""))
                # pydub的音量调整是按分贝的
                # 这里简化处理，假设+100%对应+10dB
                db_adjustment = volume_value * 0.1
                audio = audio + db_adjustment
                print(f"[AudioEngine] 调整音量: {volume} -> {db_adjustment}dB")
            except Exception as e:
                print(f"[AudioEngine] 调整音量失败: {e}")
        
        return audio

    def mix_audio(self, voice: AudioSegment, bgm: AudioSegment, effects: List[AudioSegment], 
                  mix_config: MixConfig, effect_params: List = None) -> AudioSegment:
        """
        按规则混音
        :param voice: 语音音频
        :param bgm: BGM音频 (可选)
        :param effects: 音效列表
        :param mix_config: 混音配置
        :param effect_params: 音效参数列表（包含trigger_delay信息）
        :return: 混音后的音频
        """
        print(f"[MixEngine] 混音模式: {mix_config.mode}")
        
        # 基础初始化
        voice_duration = len(voice)
        
        # 处理BGM为None的情况
        if bgm is None:
            bgm = AudioSegment.silent(duration=voice_duration)
        
        # 如果BGM存在且长度大于0，确保BGM时长与配音匹配
        if len(bgm) > 0:
            if len(bgm) < voice_duration:
                # BGM太短，循环播放以匹配语音时长
                loop_count = voice_duration // len(bgm)
                remaining = voice_duration % len(bgm)
                bgm = bgm * loop_count + bgm[:remaining]
            else:
                # BGM太长，裁剪到语音长度
                bgm = bgm[:voice_duration]

        # 只调整背景音音量（降低40%，约-12dB），不改变音效音量
        if len(bgm) > 0:
            # 确保背景音音量被正确降低
            bgm = bgm - 12  # 降低12dB
            print(f"🔊 背景音音量降低12dB")
        
        # 音效音量保持不变
        print(f"🔊 音效音量保持不变")

        # 按混音模式处理
        if mix_config.mode == "bgm_fade_in_then_voice":
            # BGM淡入后播放语音
            bgm = bgm.fade_in(int(mix_config.voice_delay * 1000))
            # 以BGM为基础，语音在指定延迟后叠加
            final_audio = bgm
            if voice_duration > len(bgm):
                # 如果语音更长，扩展BGM到语音长度
                final_audio = bgm + AudioSegment.silent(duration=voice_duration - len(bgm))
            final_audio = final_audio.overlay(voice, position=int(mix_config.voice_delay * 1000))
        
        elif mix_config.mode == "voice_on_bgm":
            # 以语音为基础，BGM叠加在上面，确保最终长度与语音一致
            final_audio = voice
            if len(bgm) > 0:
                final_audio = final_audio.overlay(bgm)
        
        elif mix_config.mode == "mix":
            # 以语音为基础，BGM和音效叠加在上面
            final_audio = voice
            if len(bgm) > 0:
                final_audio = final_audio.overlay(bgm)
            # 应用音效，考虑trigger_delay参数
            for i, effect in enumerate(effects):
                if effect_params and i < len(effect_params):
                    # 应用trigger_delay延迟
                    delay_ms = int(effect_params[i].trigger_delay * 1000)
                    if delay_ms > 0:
                        # 音效在指定延迟后播放
                        final_audio = final_audio.overlay(effect, position=delay_ms)
                        print(f"🔊 音效延迟 {delay_ms}ms 播放")
                    else:
                        final_audio = final_audio.overlay(effect)
                else:
                    final_audio = final_audio.overlay(effect)
        
        elif mix_config.mode == "voice_only":
            # 只有语音，没有BGM和音效
            final_audio = voice
        
        else:
            # 默认模式：只有语音
            final_audio = voice
        
        # 音效已经在上面的混音模式中处理过，不需要重复添加

        # 添加1秒停顿，使场景衔接更自然
        pause = AudioSegment.silent(duration=1000)  # 500毫秒 = 0.5秒
        final_audio = final_audio + pause
        print("[MixEngine] 添加0.5秒场景停顿")

        return final_audio

    def clean_temp_files(self):
        """清理临时音频文件"""
        for file in os.listdir(self.temp_dir):
            if file.endswith(self.audio_format):
                os.remove(os.path.join(self.temp_dir, file))


# ======================== 核心解析与生成逻辑 ========================
class AudioGenerator:
    """剑来有声小说音频生成器"""
    
    def __init__(self, json_path: str, output_dir: str = None, tts_engine: str = "qwen3-tts", qwen_model_path: str = None):
        # 设置默认输出目录为项目根目录
        if output_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(base_dir, "../../output")
        self.json_path = json_path
        self.tts_engine = tts_engine
        self.qwen_model_path = qwen_model_path
        
        # 加载JSON配置
        self.config = self.load_config()
        self.chapter_name = self.config["chapter"]
        
        # 提取小说名称和章节名称
        self.novel_name = os.path.basename(os.path.dirname(json_path))
        self.chapter_clean_name = self.chapter_name.replace("\n", "").replace(" ", "_").replace(":", "-")
        
        # 创建目录结构：output_dir/小说名称/章节名称
        self.output_dir = os.path.join(output_dir, self.novel_name)
        self.chapter_dir = os.path.join(self.output_dir, self.chapter_clean_name)
        
        # 创建子目录：配音、背景音、音效、混音、临时文件
        self.voice_dir = os.path.join(self.chapter_dir, "配音")
        self.bgm_dir = os.path.join(self.chapter_dir, "背景音")
        self.effect_dir = os.path.join(self.chapter_dir, "音效")
        self.mix_dir = os.path.join(self.chapter_dir, "混音")
        self.tmp_dir = os.path.join(self.chapter_dir, "tmp")
        
        # 创建所有目录（按顺序创建）
        os.makedirs(self.voice_dir, exist_ok=True)
        os.makedirs(self.bgm_dir, exist_ok=True)
        os.makedirs(self.effect_dir, exist_ok=True)
        os.makedirs(self.mix_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)
        
        # 初始化音频引擎，使用小说章节下的tmp目录作为临时目录
        self.audio_engine = AudioEngine(
            temp_dir=self.tmp_dir,
            sample_rate=44100,  # 可从global配置读取
            channels=self.config["global"]["channels"],
            tts_engine=self.tts_engine,
            qwen_model_path=self.qwen_model_path
        )

    def load_config(self) -> Dict[str, Any]:
        """加载JSON配置"""
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"✅ 成功加载JSON配置: {self.json_path}")
            print(f"📖 章节: {config['chapter']} | 总行数: {len(config['data'])}")
            
            # 保存角色定义
            self.roles_definition = config.get("roles_definition", {})
            print(f"👥 角色定义数量: {len(self.roles_definition)}")
            
            return config
        except Exception as e:
            print(f"❌ 加载JSON失败: {e}")
            raise

    def _parse_line_config(self, line: Dict[str, Any]) -> LineAudioConfig:
        """解析单句配置"""
        # 获取角色信息
        role = line["role"]
        
        # 根据引擎类型选择对应的语音参数
        if hasattr(self, 'audio_engine') and hasattr(self.audio_engine, 'tts_engine'):
            tts_engine = self.audio_engine.tts_engine
        else:
            tts_engine = "easyvoice"
        
        # 使用缓存避免重复打印相同的引擎和角色信息
        log_key = f"{tts_engine}_{role}"
        if not hasattr(self, '_last_logged_engine_role') or self._last_logged_engine_role != log_key:
            print(f"[ConfigParser] 当前引擎: {tts_engine} | 角色: {role}")
            self._last_logged_engine_role = log_key
        
        # 初始化语音参数
        voice_params_dict = None
        
        # 获取voice对象（新格式：参数直接在voice级别，没有params嵌套）
        voice_data = line["api"].get("voice", {})
        
        # 如果使用Qwen3-TTS引擎
        if tts_engine == "qwen3-tts":
            # 直接使用voice中的参数（新格式已移除params/qwen_params嵌套）
            if voice_data:
                voice_params_dict = voice_data.copy()
                # 避免重复打印
                if not hasattr(self, '_last_logged_voice_source') or self._last_logged_voice_source != 'line':
                    print(f"[ConfigParser] 使用台词条目自定义的voice参数")
                    self._last_logged_voice_source = 'line'
            # 如果voice为空，尝试从角色定义中获取
            elif hasattr(self, 'roles_definition') and role in self.roles_definition:
                role_def = self.roles_definition[role]
                if 'voice' in role_def:
                    voice_params_dict = role_def['voice'].copy()
                    # 避免重复打印
                    if not hasattr(self, '_last_logged_voice_source') or self._last_logged_voice_source != 'role':
                        print(f"[ConfigParser] 为角色'{role}'应用角色定义中的voice配置")
                        self._last_logged_voice_source = 'role'
        
        # 如果没有找到Qwen3-TTS参数或使用其他引擎，使用默认参数
        if voice_params_dict is None:
            if voice_data:
                voice_params_dict = voice_data.copy()
            elif hasattr(self, 'roles_definition') and role in self.roles_definition:
                role_def = self.roles_definition[role]
                if 'voice' in role_def:
                    voice_params_dict = role_def['voice'].copy()
            print(f"[ConfigParser] 使用默认参数")
        
        # 确保text字段存在（从line中获取）
        if voice_params_dict and 'text' not in voice_params_dict:
            voice_params_dict['text'] = line.get('text', '')
        
        # 解析语音参数
        voice_params = VoiceParams(**voice_params_dict)
        
        # 解析BGM参数（可选）（新格式：参数直接在bgm级别，没有params嵌套）
        bgm_params = None
        if "bgm" in line["api"]:
            bgm_data = line["api"]["bgm"]
            bgm_params = BGMAudioParams(
                scene=bgm_data.get("scene", ""),
                scene_cn=bgm_data.get("scene_cn", ""),
                scene_en=bgm_data.get("scene_en", ""),
                fade_in=bgm_data.get("fade_in", 0),
                fade_out=bgm_data.get("fade_out", 0),
                volume=bgm_data.get("volume", "+0%"),
                pitch=bgm_data.get("pitch", "+0Hz"),
                play_mode=bgm_data.get("play_mode", "keep"),
                lower_db=bgm_data.get("lower_db")
            )
        
        # 解析音效参数（可选）（新格式：参数直接在effect级别，没有params嵌套）
        effect_params = []
        if "effects" in line["api"]:
            for effect in line["api"]["effects"]:
                effect_params.append(EffectAudioParams(
                    name=effect.get("name", ""),
                    sound_cn=effect.get("sound_cn", ""),
                    sound_en=effect.get("sound_en", ""),
                    volume=effect.get("volume", "+0%"),
                    pitch=effect.get("pitch", "+0Hz"),
                    trigger_delay=effect.get("trigger_delay", 0),
                    duration=effect.get("duration", 1)
                ))
        
        # 解析混音配置
        mix_config = MixConfig(**line["mix"])
        
        return LineAudioConfig(
            id=line["id"],
            role=line["role"],
            voice_params=voice_params,
            bgm_params=bgm_params,
            effect_params=effect_params,
            mix_config=mix_config
        )

    _dirs_created = False
    
    def generate_single_line(self, line_config: LineAudioConfig) -> AudioSegment:
        print(f"\n===  处理章节: {self.chapter_name} 第 {line_config.id} 句 | 角色: {line_config.role} ===")
        
        # 确保目录存在
        try:
            os.makedirs(self.voice_dir, exist_ok=True)
            os.makedirs(self.bgm_dir, exist_ok=True)
            os.makedirs(self.effect_dir, exist_ok=True)
            os.makedirs(self.mix_dir, exist_ok=True)
            if not self._dirs_created:
                print(f"[DEBUG] 成功创建所有必要目录")
                print(f"[DEBUG] 配音目录: {self.voice_dir}")
                print(f"[DEBUG] 背景音目录: {self.bgm_dir}")
                print(f"[DEBUG] 音效目录: {self.effect_dir}")
                print(f"[DEBUG] 混音目录: {self.mix_dir}")
                self._dirs_created = True
        except Exception as e:
            print(f"[ERROR] 创建目录失败: {e}")
            # 如果目录创建失败，使用临时目录作为备选
            self.bgm_dir = self.tmp_dir
            self.voice_dir = self.tmp_dir
            self.effect_dir = self.tmp_dir
            self.mix_dir = self.tmp_dir
            print(f"[DEBUG] 已切换到临时目录: {self.tmp_dir}")
        
        # 1. 生成语音
        voice_output_path = os.path.join(self.voice_dir, f"voice_line_{line_config.id}.wav")
        if os.path.exists(voice_output_path):
            print(f"✅ 配音文件已存在，跳过生成: {voice_output_path}")
            voice_audio = AudioSegment.from_wav(voice_output_path)
        else:
            voice_audio = self.audio_engine.text_to_speech(line_config.voice_params)
            voice_audio.export(voice_output_path, format="wav")
            print(f"💾 单句配音已保存: {voice_output_path}")
        
        # 2. 使用generate_audio_batch多线程批量生成BGM和音效
        bgm_audio = None
        effect_audios = []
        bgm_output_path = None
        effect_output_paths = []
        
        # 准备批量生成任务
        batch_tasks = []

        MAX_DURATION = 47
        # 添加BGM任务
        if line_config.bgm_params is not None:
            bgm_duration = min(len(voice_audio) / 1000.0, MAX_DURATION)
            bgm_scene_cn = line_config.bgm_params.scene.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            bgm_output_path = os.path.join(self.bgm_dir, f"bgm_line_{bgm_scene_cn}_{line_config.id}.wav")
            
            if not os.path.exists(bgm_output_path):
                batch_tasks.append({
                    "prompt": line_config.bgm_params.scene_en,
                    "duration": bgm_duration,
                    "output_path": bgm_output_path
                })
            else:
                print(f"✅ 场景BGM文件已存在，跳过生成: {bgm_output_path}")
        
        # 添加音效任务
        for i, effect_param in enumerate(line_config.effect_params):
            effect_name = effect_param.name.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            effect_output_path = os.path.join(self.effect_dir, f"effect_line_{effect_name}_{line_config.id}.wav")
            effect_output_paths.append(effect_output_path)
            
            if not os.path.exists(effect_output_path):
                batch_tasks.append({
                    "prompt": effect_param.sound_en,
                    "duration": effect_param.duration,
                    "output_path": effect_output_path
                })
            else:
                print(f"✅ 特定音效文件已存在，跳过生成: {effect_output_path}")
        
        # 使用多线程批量生成音频
        if batch_tasks:
            print(f"🔄 开始多线程批量生成 {len(batch_tasks)} 个音频...")
            generate_audio_batch(batch_tasks)
        
        # 加载生成的BGM
        if bgm_output_path and os.path.exists(bgm_output_path):
            bgm_audio = AudioSegment.from_wav(bgm_output_path)
            if line_config.bgm_params.play_mode == "lower" and line_config.bgm_params.lower_db:
                bgm_audio = bgm_audio - line_config.bgm_params.lower_db
            bgm_global_reduce = 2.0
            bgm_audio = bgm_audio - bgm_global_reduce
            print(f"🔊 BGM全局降低 {bgm_global_reduce}dB")
        
        # 加载生成的音效
        for i, effect_output_path in enumerate(effect_output_paths):
            if os.path.exists(effect_output_path):
                effect_audio = AudioSegment.from_wav(effect_output_path)
                effect_param = line_config.effect_params[i]
                effect_audio = effect_audio[:int(effect_param.duration * 1000)]
                effect_audios.append(effect_audio)
        
        # 4. 混音
        mixed_audio = self.audio_engine.mix_audio(
            voice=voice_audio,
            bgm=bgm_audio,
            effects=effect_audios,
            mix_config=line_config.mix_config,
            effect_params=line_config.effect_params
        )
        
        # 5. 保存单句混合音频到混音目录
        single_output_path = os.path.join(self.mix_dir, f"mixed_line_{line_config.id}.wav")
        mixed_audio.export(single_output_path, format="wav")
        print(f"💾 单句混合音频已保存: {single_output_path}")
        
        return mixed_audio

    def generate_chapter_audio(self) -> str:
        """
        生成整章音频（合并所有句子）
        """
        # 检查整章音频是否已经存在，如果存在则直接返回
        chapter_output_path = os.path.join(self.chapter_dir, f"{self.chapter_clean_name}_full.wav")
        if os.path.exists(chapter_output_path):
            print(f"✅ 整章音频已存在，跳过生成: {chapter_output_path}")
            return chapter_output_path
        
        # 当使用Qwen3-TTS引擎时，使用串行处理以避免多进程导致的PyTorch MPS问题
        if self.tts_engine == "qwen3-tts":
            return self.generate_chapter_audio_serial()
        else:
            return self.generate_chapter_audio_parallel()
    
    def generate_chapter_audio_serial(self) -> str:
        """
        串行生成整章音频（合并所有句子）
        用于Qwen3-TTS引擎，避免多进程导致的PyTorch MPS问题
        """
        print(f"\n🚀 开始串行生成《{self.chapter_name}》完整音频")
        start_time = time.time()
        
        # 解析所有行配置
        line_configs = []
        for line in self.config["data"]:
            line_configs.append(self._parse_line_config(line))
        
        # 串行处理所有行配置，直接使用已初始化的audio_engine
        results = []
        total_lines = len(line_configs)
        for i, line_config in enumerate(line_configs):
            print(f"[进度] 处理第 {i+1}/{total_lines} 句 (角色: {line_config.role})")
            try:
                # 直接生成单句音频，使用同一个audio_engine实例
                line_audio = self.generate_single_line(line_config)
                results.append((line_config.id, line_audio))
            except Exception as e:
                print(f"❌ 处理第 {line_config.id} 句时发生异常: {e}")
                results.append((line_config.id, None))
        
        # 按ID排序结果
        results.sort(key=lambda x: x[0])
        
        # 合并所有音频
        merged_audio = AudioSegment.silent(duration=0, frame_rate=44100)
        for line_id, line_audio in results:
            if line_audio is not None:
                print(f"[DEBUG] 合并第 {line_id} 句音频 (时长: {len(line_audio)} ms)")
                merged_audio += line_audio
                print(f"[DEBUG] 合并后总时长: {len(merged_audio)} ms")
                
                # 在章节标题后添加1秒静音（id 0 是章节标题）
                if line_id == 0:
                    two_seconds_silence = AudioSegment.silent(duration=1000, frame_rate=44100)
                    merged_audio += two_seconds_silence
                    print(f"[DEBUG] 在章节标题后添加1秒静音，总时长: {len(merged_audio)} ms")
            else:
                print(f"[DEBUG] 跳过第 {line_id} 句音频 (生成失败)")
        
        # 保存整章音频
        chapter_output_path = os.path.join(self.chapter_dir, f"{self.chapter_clean_name}_full.wav")
        merged_audio.export(chapter_output_path, format="wav")
        
        # 清理临时文件
        self.audio_engine.clean_temp_files()
        
        end_time = time.time()
        print(f"\n🎉 整章音频串行生成完成！耗时: {end_time - start_time:.2f} 秒")
        print(f"📂 输出路径: {chapter_output_path}")
        
        return chapter_output_path

    def _process_single_line_worker(self, line_config: LineAudioConfig) -> AudioSegment:
        """
        单句音频生成的工作函数，用于并行处理
        :param line_config: 单句音频配置
        :return: 生成的音频段
        """
        try:
            # 创建一个新的AudioEngine实例，确保进程安全
            worker_audio_engine = AudioEngine(
                temp_dir=self.tmp_dir,
                sample_rate=44100,
                channels=self.config["global"]["channels"],
                api_endpoint=self.api_endpoint,
                easyvoice_temp_dir=self.easyvoice_temp_dir if hasattr(self, 'easyvoice_temp_dir') else None,
                tts_engine=self.tts_engine if hasattr(self, 'tts_engine') else "easyvoice",
                qwen_model_path=self.qwen_model_path if hasattr(self, 'qwen_model_path') else None
            )
            
            # 临时替换当前实例的audio_engine
            original_engine = self.audio_engine
            self.audio_engine = worker_audio_engine
            
            try:
                # 生成单句音频
                line_audio = self.generate_single_line(line_config)
                return line_config.id, line_audio
            finally:
                # 恢复原始的audio_engine
                self.audio_engine = original_engine
        except Exception as e:
            print(f"❌ 处理第 {line_config.id} 句时发生异常: {e}")
            return line_config.id, None

    def generate_chapter_audio_parallel(self) -> str:
        """
        并行生成整章音频（合并所有句子）
        """
        print(f"\n🚀 开始并行生成《{self.chapter_name}》完整音频")
        start_time = time.time()
        
        # 解析所有行配置
        line_configs = []
        for line in self.config["data"]:
            line_configs.append(self._parse_line_config(line))
        
        # 生成所有音频（并行处理）
        print(f"[DEBUG] 开始并行处理 {len(line_configs)} 句音频")
        
        # 创建进程池，只使用1个进程来避免资源争用
        # BGM生成依赖GPU资源，过多进程会导致资源争用和超时
        num_processes = 1
        print(f"[DEBUG] 使用 {num_processes} 个进程并行处理（避免资源争用）")
        
        # 使用functools.partial来创建一个可以在进程中安全执行的函数
        partial_process_line = partial(self._process_single_line_worker)
        
        # 并行处理所有行配置
        with multiprocessing.Pool(processes=num_processes) as pool:
            results = pool.map(partial_process_line, line_configs)
        
        # 按ID排序结果
        results.sort(key=lambda x: x[0])
        
        # 合并所有音频
        merged_audio = AudioSegment.silent(duration=0, frame_rate=44100)
        for line_id, line_audio in results:
            if line_audio is not None:
                print(f"[DEBUG] 合并第 {line_id} 句音频 (时长: {len(line_audio)} ms)")
                merged_audio += line_audio
                print(f"[DEBUG] 合并后总时长: {len(merged_audio)} ms")
                
                # 在章节标题后添加2秒静音（id 0 是章节标题）
                if line_id == 0:
                    two_seconds_silence = AudioSegment.silent(duration=2000, frame_rate=44100)
                    merged_audio += two_seconds_silence
                    print(f"[DEBUG] 在章节标题后添加2秒静音，总时长: {len(merged_audio)} ms")
            else:
                print(f"[DEBUG] 跳过第 {line_id} 句音频 (生成失败)")
        
        # 保存整章音频
        chapter_output_path = os.path.join(self.chapter_dir, f"{self.chapter_clean_name}_full.wav")
        merged_audio.export(chapter_output_path, format="wav")
        
        # 清理临时文件
        self.audio_engine.clean_temp_files()
        
        end_time = time.time()
        print(f"\n🎉 整章音频并行生成完成！耗时: {end_time - start_time:.2f} 秒")
        print(f"📂 输出路径: {chapter_output_path}")
        
        return chapter_output_path


# ======================== 小说音频合成器 ========================
class NovelAudioSynthesizer:
    """
    小说音频合成器，用于生成单个或多个小说章节的完整音频
    支持背景音、音效和配音的生成与混合
    """
    
    def __init__(self, script_dir: str = None, output_dir: str = None, temp_dir: str = None, tts_engine: str = "qwen3-tts", qwen_model_path: str = None):
        """
        初始化小说音频合成器
        :param script_dir: 小说剧本目录
        :param output_dir: 音频输出目录
        :param temp_dir: 临时文件目录
        :param tts_engine: TTS引擎类型
        :param qwen_model_path: Qwen TTS模型路径
        """
        # 获取脚本所在目录
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 设置默认目录
        self.script_dir = script_dir or os.path.join(self.base_dir, "../小说剧本")
        # 统一输出目录到项目根目录
        self.output_dir = output_dir or os.path.join(self.base_dir, "../../output")
        # 统一临时目录到项目根目录的output下
        self.temp_dir = temp_dir or os.path.join(self.output_dir, "temp")
        self.tts_engine = tts_engine
        # 支持两种模型类型：custom_voice（内置音色）和base（语音克隆）
        self.qwen_model_path = qwen_model_path if qwen_model_path else "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model"
        
        # 创建必要的目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("=== Novel Audio Synthesizer 初始化完成 ===")
        print(f"📁 剧本目录: {self.script_dir}")
        print(f"📁 输出目录: {self.output_dir}")
    
    def check_environment(self) -> bool:
        """
        检查环境
        :return: 环境是否正常
        """
        print("\n=== 环境检测 ===")
        
        # 检查FFmpeg
        try:
            import subprocess
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            print("✅ FFmpeg 已安装")
        except (ImportError, subprocess.CalledProcessError):
            print("❌ FFmpeg 未安装，请访问 https://ffmpeg.org/download.html 安装")
            return False
        
        # 检查pydub
        try:
            import pydub
            print("✅ pydub 已安装")
        except ImportError:
            print("❌ pydub 未安装，请运行: pip install pydub")
            return False
        
        # 检查requests
        try:
            import requests
            print("✅ requests 已安装")
        except ImportError:
            print("❌ requests 未安装，请运行: pip install requests")
            return False
        
        print("✅ 环境检测通过")
        return True
    
    def process_novel(self, json_file: str) -> str:
        """
        处理单个小说章节
        :param json_file: 小说JSON文件路径
        :return: 生成的音频文件路径
        """
        print(f"\n=== 处理小说章节: {json_file} ===")
        
        # 先检查整章音频是否已存在，如果存在则直接返回
        # 提取小说名称和章节名称
        novel_name = os.path.basename(os.path.dirname(json_file))
        
        # 加载JSON配置获取章节名称
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            chapter_name = config["chapter"]
            chapter_clean_name = chapter_name.replace("\n", "").replace(" ", "_").replace(":", "-")
            
            # 构建整章音频路径
            chapter_dir = os.path.join(self.output_dir, novel_name, chapter_clean_name)
            chapter_output_path = os.path.join(chapter_dir, f"{chapter_clean_name}_full.wav")
            
            if os.path.exists(chapter_output_path):
                print(f"✅ 整章音频已存在，跳过生成: {chapter_output_path}")
                return chapter_output_path
        except Exception as e:
            print(f"❌ 检查整章音频时发生错误: {e}")
            # 继续执行，让AudioGenerator处理
        
        # 生成音频
        generator = AudioGenerator(
            json_path=json_file,
            output_dir=self.output_dir,
            tts_engine=self.tts_engine,
            qwen_model_path=self.qwen_model_path
        )
        
        # 生成整章音频
        output_path = generator.generate_chapter_audio()
        
        return output_path
    
    def process_all_novels(self) -> List[str]:
        """
        处理所有小说章节
        :return: 生成的音频文件路径列表
        """
        print(f"\n=== 处理所有小说章节 ===")
        
        output_paths = []
        
        # 遍历小说剧本目录
        for novel_name in os.listdir(self.script_dir):
            novel_dir = os.path.join(self.script_dir, novel_name)
            if not os.path.isdir(novel_dir):
                continue
            
            print(f"\n📖 处理小说: {novel_name}")
            
            # 遍历小说目录下的JSON文件
            for json_file in os.listdir(novel_dir):
                if not json_file.endswith(".json"):
                    continue
                
                json_path = os.path.join(novel_dir, json_file)
                output_path = self.process_novel(json_path)
                output_paths.append(output_path)
        
        return output_paths
    

    
    def run(self, json_file: str = None) -> List[str]:
        """
        运行小说音频合成器
        :param json_file: 小说JSON文件路径，如果为None则处理所有小说
        :return: 生成的音频文件路径列表
        """
        # 检查环境
        if not self.check_environment():
            return []
        
        # 处理小说
        if json_file:
            # 处理单个小说
            output_path = self.process_novel(json_file)
            output_paths = [output_path] if output_path else []
        else:
            # 处理所有小说
            output_paths = self.process_all_novels()
        
        # 清理EasyVoice生成的临时文件
        print(f"\n🗑️ 清理EasyVoice临时文件...")
        audio_dir = os.path.join(self.base_dir, "../audio")
        
        # 检查目录是否存在
        if os.path.exists(audio_dir):
            # 遍历audio目录下的所有文件
            for file_name in os.listdir(audio_dir):
                file_path = os.path.join(audio_dir, file_name)
                # 检查是否是.mp3_tmp文件
                if file_name.endswith(".mp3_tmp"):
                    try:
                        # 如果是目录，递归删除
                        if os.path.isdir(file_path):
                            import shutil
                            shutil.rmtree(file_path)
                            print(f"✅ 删除临时目录: {file_path}")
                        else:
                            # 如果是文件，直接删除
                            os.remove(file_path)
                            print(f"✅ 删除临时文件: {file_path}")
                    except Exception as e:
                        print(f"⚠️ 删除临时文件/目录失败: {file_path} - {e}")
        else:
            print(f"📁 EasyVoice音频目录不存在: {audio_dir}")
        
        # 清理章节tmp目录下的临时文件
        print(f"\n🗑️ 清理章节临时文件...")
        # 检查目录是否存在
        if os.path.exists(audio_dir):
            for root, dirs, files in os.walk(audio_dir):
                for dir_name in dirs:
                    if dir_name == "tmp":
                        tmp_dir = os.path.join(root, dir_name)
                        try:
                            # 遍历tmp目录下的所有文件
                            for file_name in os.listdir(tmp_dir):
                                file_path = os.path.join(tmp_dir, file_name)
                                try:
                                    os.remove(file_path)
                                    print(f"✅ 删除章节临时文件: {file_path}")
                                except Exception as e:
                                    print(f"⚠️ 删除章节临时文件失败: {file_path} - {e}")
                        except Exception as e:
                            print(f"⚠️ 访问章节临时目录失败: {tmp_dir} - {e}")

        print(f"\n=== 处理完成 ===")
        print(f"📊 共生成 {len(output_paths)} 个音频文件")
        for path in output_paths:
            print(f"📄 {path}")
        
        return output_paths


# ======================== 运行入口 ========================
if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="小说有声书音频合成工具")
    parser.add_argument("--json-path", type=str, help="小说剧本JSON文件路径")
    parser.add_argument("--script-dir", type=str, help="小说剧本目录路径")
    parser.add_argument("--output-dir", type=str, help="音频输出目录")
    parser.add_argument("--tts-engine", type=str, default="qwen3-tts", help="TTS引擎类型 (qwen3-tts)")
    parser.add_argument("--qwen-model-path", type=str, default="/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model", help="Qwen TTS模型路径")
    
    args = parser.parse_args()
    
    # 初始化合成器
    synthesizer = NovelAudioSynthesizer(
        script_dir=args.script_dir,
        output_dir=args.output_dir,
        tts_engine=args.tts_engine,
        qwen_model_path=args.qwen_model_path
    )
    
    # 运行合成器
    if args.json_path:
        # 处理单个小说
        synthesizer.run(json_file=args.json_path)
    else:
        # 处理所有小说
        synthesizer.run()