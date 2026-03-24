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
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import warnings
import multiprocessing
from functools import partial

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
    bgm_params: BGMAudioParams
    effect_params: List[EffectAudioParams]
    mix_config: MixConfig


# ======================== 音频引擎接口（预留对接） ========================
class AudioEngine:
    """音频引擎基类，预留对接实际TTS/文生音频接口"""
    
    def __init__(self, temp_dir: str = "./temp_audio", sample_rate: int = 44100, channels: int = 1, api_endpoint: str = "http://localhost:3000/api/v1/tts/generateJson", easyvoice_temp_dir: str = None):
        self.temp_dir = temp_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_format = "wav"
        self.api_endpoint = api_endpoint
        self.easyvoice_temp_dir = easyvoice_temp_dir or "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/audio"
        os.makedirs(self.temp_dir, exist_ok=True)

    def text_to_speech(self, params: VoiceParams) -> AudioSegment:
        """
        文本转语音接口，调用TTS API生成语音
        :param params: 语音参数
        :return: 生成的语音音频段
        """
        print(f"\n[TTSEngine] 生成[{params.role}]语音: {params.text[:20]}...")
        print(f"  - 音色: {params.role_voice} | 语速: {params.speed} | 音量: {params.volume} | 音调: {params.pitch}")
        
        # 构建API请求JSON - 匹配EasyVoice API格式
        request_data = {
            "data": [
                {
                    "desc": params.role,
                    "text": params.text,
                    "voice": params.role_voice,
                    "rate": params.speed,
                    "volume": params.volume,
                    "pitch": params.pitch
                }
            ]
        }
        
        # 生成临时输出文件路径
        temp_output = os.path.join(self.temp_dir, f"temp_tts_{time.time()}.mp3")
        
        max_retries = 3
        retry_delay = 5  # 重试间隔秒数
        
        # 重试机制
        for retry in range(max_retries):
            try:
                print(f"[TTSEngine] 第 {retry+1}/{max_retries} 次尝试生成语音...")
                # 发送请求并保存响应，增加超时时间
                response = requests.post(
                    self.api_endpoint,
                    headers={"Content-Type": "application/json"},
                    json=request_data,
                    timeout=60  # 增加超时时间到60秒
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    with open(temp_output, "wb") as f:
                        f.write(response.content)
                    
                    # 读取生成的音频文件
                    audio = AudioSegment.from_mp3(temp_output)
                    
                    # 调整音频格式
                    audio = audio.set_frame_rate(self.sample_rate)
                    audio = audio.set_channels(self.channels)
                    
                    # 清理临时文件
                    os.remove(temp_output)
                    
                    print("[TTSEngine] 语音生成成功！")
                    
                    # 清理EasyVoice服务在挂载目录生成的临时文件
                    # 这些文件以音色+文本+时间戳命名，格式如：zh-CN-YunxiNeural-又是一天。-1772722007715.mp3
                    try:
                        # 生成EasyVoice可能创建的文件名模式
                        import re
                        safe_text = re.sub(r'[\/:*?"<>|]', '-', params.text[:10])
                        file_pattern = f"{params.role_voice}-{safe_text}-*.mp3"
                        
                        # 使用glob查找匹配的文件
                        import glob
                        matching_files = glob.glob(os.path.join(self.easyvoice_temp_dir, file_pattern))
                        
                        # 将文件移动到tmp目录
                        for file_path in matching_files:
                            # 获取文件名
                            file_name = os.path.basename(file_path)
                            # 生成目标路径
                            target_path = os.path.join(self.temp_dir, file_name)
                            # 移动文件
                            os.rename(file_path, target_path)
                            print(f"📁 将临时文件移动到tmp目录: {target_path}")
                    except Exception as e:
                        print(f"⚠️ 清理EasyVoice临时文件失败: {e}")
                        
                    return audio
                else:
                    print(f"[TTSEngine] 语音生成失败: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"[TTSEngine] 语音生成异常: {e}")
            
            # 如果不是最后一次尝试，等待后重试
            if retry < max_retries - 1:
                print(f"[TTSEngine] {retry_delay}秒后重试...")
                time.sleep(retry_delay)
        
        # 所有重试都失败时返回静音（备用方案）
        print("[TTSEngine] 所有重试都失败，返回静音音频")
        silence = AudioSegment.silent(duration=len(params.text)*80, frame_rate=self.sample_rate)
        return self._adjust_audio_params(silence, params.speed, params.volume, params.pitch)

    def text_to_audio(self, desc_en: str, volume: str, pitch: str, duration: float = 5.0, audio_type: str = "music") -> AudioSegment:
        """
        文生音频接口，调用AudioCraft的magnet_test_tool.py生成BGM/音效
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
        
        # 确保使用英文提示词
        import re
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', desc_en))
        if has_chinese:
            print("[AudioEngine] 警告：检测到中文提示词，MAGNeT模型对英文提示词效果更好")
            # 可以考虑添加自动翻译功能
        
        # 生成临时输出文件路径
        import uuid
        temp_file_name = f"temp_audio_{uuid.uuid4().hex}"
        temp_output_path = os.path.join(self.temp_dir, temp_file_name)
        
        try:
            # 检查输出文件是否已存在
            actual_output_file = f"{temp_output_path}.wav"
            if os.path.exists(actual_output_file) and os.path.getsize(actual_output_file) > 0:
                print(f"[AudioEngine] 音频文件已存在，跳过生成: {actual_output_file}")
                audio = AudioSegment.from_wav(actual_output_file)
                return self._adjust_audio_params(audio, "+0%", volume, pitch)
            
            # 获取magnet_test_tool.py脚本路径
            magnet_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "AudioCraft", "magnet_test_tool.py")
            if not os.path.exists(magnet_script):
                print(f"[AudioEngine] 未找到magnet_test_tool.py脚本: {magnet_script}")
                # 返回静音音频
                silence = AudioSegment.silent(duration=int(duration*1000), frame_rate=self.sample_rate)
                return self._adjust_audio_params(silence, "+0%", volume, pitch)
            
            # 调整时长（默认1秒，根据音频类型设置不同限制）
            duration_int = int(round(duration))
            # 根据音频类型设置最大时长限制（不超过模型支持的max_duration）
            if audio_type == "music":
                # BGM最长10秒（模型实际限制）
                if duration_int > 10:
                    duration_int = 10
                    print("[AudioEngine] BGM最长10秒，已调整时长为10秒")
            elif audio_type == "sound":
                # 音效最长10秒
                if duration_int > 10:
                    duration_int = 10
                    print("[AudioEngine] 音效最长10秒，已调整时长为10秒")
            # 设置最小时长
            if duration_int < 1:
                duration_int = 1
                print("[AudioEngine] 使用默认时长1秒")
            
            print("[AudioEngine] 生成音频可能需要几分钟时间，请耐心等待...")
            
            # 调用magnet_test_tool.py生成音频
            import subprocess
            try:
                # magnet_test_tool.py默认生成3个变体，文件会有_1、_2、_3后缀
                cmd = ["python3", magnet_script, desc_en, "--type", audio_type, "--duration", str(duration_int), "--output-path", temp_output_path]
                
                result = subprocess.run(
                    cmd,
                    capture_output=False,
                    text=True,
                    timeout=300,  # 增加超时时间到5分钟
                    bufsize=0  # 禁用缓冲
                )
                
                # 打印magnet_test_tool.py脚本的输出
                if result.stdout:
                    print(f"[AudioEngine] magnet_test_tool输出: {result.stdout.strip()}")
                if result.stderr:
                    print(f"[AudioEngine] magnet_test_tool错误: {result.stderr.strip()}")
                
                # 检查生成结果
                actual_output_file = f"{temp_output_path}.wav"
                if result.returncode == 0 and os.path.exists(actual_output_file) and os.path.getsize(actual_output_file) > 0:
                    print(f"[AudioEngine] 音频生成成功: {actual_output_file}")
                    print(f"[AudioEngine] 文件大小: {os.path.getsize(actual_output_file)} 字节")
                    
                    # 读取生成的音频文件
                    audio = AudioSegment.from_wav(actual_output_file)
                    
                    # 调整音频格式
                    audio = audio.set_frame_rate(self.sample_rate)
                    audio = audio.set_channels(self.channels)
                    
                    # 调整音频参数
                    audio = self._adjust_audio_params(audio, "+0%", volume, pitch)
                    return audio
                else:
                    print(f"[AudioEngine] 音频生成失败")
                    if result.stderr:
                        print(f"[AudioEngine] 错误信息: {result.stderr}")
                    if result.stdout:
                        print(f"[AudioEngine] 标准输出: {result.stdout}")
            except Exception as e:
                print(f"[AudioEngine] 调用magnet_test_tool.py异常: {e}")
        except Exception as e:
            print(f"[AudioEngine] 音频生成过程中发生异常: {e}")
        
        # 生成失败时返回静音（备用方案）
        print("[AudioEngine] 使用静音音频作为备用方案")
        silence = AudioSegment.silent(duration=int(duration*1000), frame_rate=self.sample_rate)
        return self._adjust_audio_params(silence, "+0%", volume, pitch)

    def _adjust_audio_params(self, audio: AudioSegment, speed: str, volume: str, pitch: str) -> AudioSegment:
        """
        调整音频参数（语速/音量/音调）
        :param audio: 原始音频段
        :param speed: 语速百分比
        :param volume: 音量百分比
        :param pitch: 音调赫兹
        :return: 调整后的音频段
        """
        # 1. 调整音量
        # 解析音量百分比（支持正负值）
        vol_value = float(volume.replace("%", ""))
        
        # 处理音量：
        # - 正数表示增加音量（dB）
        # - 负数表示降低音量（dB）
        # - 0% 保持原始音量
        if vol_value < -50:
            # 音量过低，返回静音
            return AudioSegment.silent(duration=len(audio), frame_rate=self.sample_rate)
        
        # 改进的音量转换逻辑：
        # 1. 正数百分比：直接转换为dB增益（1% = 1dB）
        # 2. 负数百分比：使用对数缩放，避免降低过多导致几乎无声
        #    -10% → -3dB, -20% → -6dB, -30% → -9dB, -40% → -12dB, -50% → -15dB
        if vol_value >= 0:
            gain_db = vol_value
        else:
            # 使用对数转换，让负数音量降低更自然
            # 公式：gain_db = vol_value / 3.333
            # 这样-18% → 约-5.4dB，而不是之前的-18dB
            gain_db = vol_value / 3.333
        
        audio = audio + gain_db

        # 2. 调整语速（简单实现，实际可使用pydub.speedup）
        speed_pct = float(speed.replace("%", "")) / 100
        new_frame_rate = int(self.sample_rate * (1 + speed_pct))
        audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_frame_rate})
        audio = audio.set_frame_rate(self.sample_rate)

        # 3. 调整音调（需安装ffmpeg，复杂调整可使用librosa）
        pitch_hz = float(pitch.replace("Hz", ""))
        if pitch_hz != 0:
            audio = effects.pitch_shift(audio, self.sample_rate, n_steps=pitch_hz/10)

        return audio

    def mix_audio(self, voice: AudioSegment, bgm: AudioSegment, effects: List[AudioSegment], 
                  mix_config: MixConfig) -> AudioSegment:
        """
        按规则混音
        :param voice: 语音音频
        :param bgm: BGM音频
        :param effects: 音效列表
        :param mix_config: 混音配置
        :return: 混音后的音频
        """
        print(f"[MixEngine] 混音模式: {mix_config.mode}")
        
        # 基础初始化
        voice_duration = len(voice)
        
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
            for effect in effects:
                final_audio = final_audio.overlay(effect)
        
        # 音效已经在上面的混音模式中处理过，不需要重复添加

        return final_audio

    def clean_temp_files(self):
        """清理临时音频文件"""
        for file in os.listdir(self.temp_dir):
            if file.endswith(self.audio_format):
                os.remove(os.path.join(self.temp_dir, file))


# ======================== 核心解析与生成逻辑 ========================
class AudioGenerator:
    """剑来有声小说音频生成器"""
    
    def __init__(self, json_path: str, output_dir: str = "./output_audio", api_endpoint: str = "http://localhost:3000/api/v1/tts/generateJson"):
        self.json_path = json_path
        self.api_endpoint = api_endpoint
        
        # 加载JSON配置
        self.config = self._load_json_config()
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
        
        # 创建EasyVoice临时文件章节目录
        self.easyvoice_temp_dir = os.path.join("/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/audio", self.novel_name, self.chapter_clean_name)
        os.makedirs(self.easyvoice_temp_dir, exist_ok=True)
        
        # 初始化音频引擎，使用小说章节下的tmp目录作为临时目录
        self.audio_engine = AudioEngine(
            temp_dir=self.tmp_dir,
            sample_rate=44100,  # 可从global配置读取
            channels=self.config["global"]["channels"],
            api_endpoint=api_endpoint,
            easyvoice_temp_dir=self.easyvoice_temp_dir
        )

    def _load_json_config(self) -> Dict[str, Any]:
        """
        加载并解析JSON配置文件
        """
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"✅ 成功加载JSON配置: {self.json_path}")
            print(f"📖 章节: {config['chapter']} | 总行数: {len(config['data'])}")
            return config
        except Exception as e:
            print(f"❌ 加载JSON失败: {e}")
            raise

    def _parse_line_config(self, line: Dict[str, Any]) -> LineAudioConfig:
        """解析单句配置"""
        # 解析语音参数
        voice_params = VoiceParams(**line["api"]["voice"]["params"])
        
        # 解析BGM参数
        bgm_params = BGMAudioParams(
            **line["api"]["bgm"]["params"],
            play_mode=line["api"]["bgm"]["play_mode"],
            lower_db=line["api"]["bgm"].get("lower_db")
        )
        
        # 解析音效参数
        effect_params = []
        for effect in line["api"]["effects"]:
            effect_params.append(EffectAudioParams(**effect["params"],
                                                  trigger_delay=effect["trigger_delay"],
                                                  duration=effect["duration"]))
        
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

    def generate_single_line(self, line_config: LineAudioConfig) -> AudioSegment:
        """生成单句音频"""
        print(f"\n=== 处理第 {line_config.id} 句 | 角色: {line_config.role} ===")
        
        # 确保目录存在
        try:
            os.makedirs(self.voice_dir, exist_ok=True)
            os.makedirs(self.bgm_dir, exist_ok=True)
            os.makedirs(self.effect_dir, exist_ok=True)
            os.makedirs(self.mix_dir, exist_ok=True)
            print(f"[DEBUG] 成功创建所有必要目录")
            print(f"[DEBUG] 配音目录: {self.voice_dir}")
            print(f"[DEBUG] 背景音目录: {self.bgm_dir}")
            print(f"[DEBUG] 音效目录: {self.effect_dir}")
            print(f"[DEBUG] 混音目录: {self.mix_dir}")
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
        
        # 2. 生成BGM，使用英文提示词
        # BGM时长使用语音时长，但最多30秒
        bgm_duration = min(len(voice_audio) / 1000.0, 30.0)
        bgm_scene_cn = line_config.bgm_params.scene.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
        bgm_output_path = os.path.join(self.bgm_dir, f"bgm_line_{bgm_scene_cn}_{line_config.id}.wav")
        if os.path.exists(bgm_output_path):
            print(f"✅ BGM文件已存在，跳过生成: {bgm_output_path}")
            bgm_audio = AudioSegment.from_wav(bgm_output_path)
        else:
            bgm_audio = self.audio_engine.text_to_audio(
                desc_en=line_config.bgm_params.scene_en,  # 使用英文提示词
                volume=line_config.bgm_params.volume,
                pitch=line_config.bgm_params.pitch,
                duration=bgm_duration,  # BGM时长为语音时长或最多10秒
                audio_type="music"  # 音频类型为音乐
            )
            # 处理BGM播放模式
            if line_config.bgm_params.play_mode == "lower" and line_config.bgm_params.lower_db:
                bgm_audio = bgm_audio - line_config.bgm_params.lower_db
            bgm_audio.export(bgm_output_path, format="wav")
            print(f"💾 单句BGM已保存: {bgm_output_path}")
        
        # 全局降低BGM音量 2dB（让所有BGM都更低一点）
        bgm_global_reduce = 2.0  # 降低的dB数
        bgm_audio = bgm_audio - bgm_global_reduce
        print(f"🔊 BGM全局降低 {bgm_global_reduce}dB")
        
        # 3. 生成音效，使用英文提示词
        effect_audios = []
        for i, effect_param in enumerate(line_config.effect_params):
            effect_name = effect_param.name.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            effect_output_path = os.path.join(self.effect_dir, f"effect_line_{effect_name}_{line_config.id}.wav")
            if os.path.exists(effect_output_path):
                print(f"✅ 音效文件已存在，跳过生成: {effect_output_path}")
                effect_audio = AudioSegment.from_wav(effect_output_path)
            else:
                effect_audio = self.audio_engine.text_to_audio(
                    desc_en=effect_param.sound_en,  # 使用英文提示词
                    volume=effect_param.volume,
                    pitch=effect_param.pitch,
                    duration=effect_param.duration,  # 使用音效参数中的时长
                    audio_type="sound"  # 音频类型为音效
                )
                # 裁剪音效时长
                effect_audio = effect_audio[:int(effect_param.duration * 1000)]
                effect_audio.export(effect_output_path, format="wav")
                print(f"💾 单句音效已保存: {effect_output_path}")
            effect_audios.append(effect_audio)
        
        # 4. 混音
        mixed_audio = self.audio_engine.mix_audio(
            voice=voice_audio,
            bgm=bgm_audio,
            effects=effect_audios,
            mix_config=line_config.mix_config
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
        return self.generate_chapter_audio_parallel()

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
                easyvoice_temp_dir=self.easyvoice_temp_dir if hasattr(self, 'easyvoice_temp_dir') else None
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
    
    def __init__(self, script_dir: str = None, output_dir: str = None, temp_dir: str = None, api_endpoint: str = "http://localhost:3000/api/v1/tts/generateJson"):
        """
        初始化小说音频合成器
        :param script_dir: 小说剧本目录
        :param output_dir: 音频输出目录
        :param temp_dir: 临时文件目录
        :param api_endpoint: TTS API端点
        """
        # 获取脚本所在目录
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 设置默认目录
        self.script_dir = script_dir or os.path.join(self.base_dir, "../小说剧本")
        self.output_dir = output_dir or os.path.join(self.base_dir, "../audio")
        self.temp_dir = temp_dir or os.path.join(self.base_dir, "temp")
        self.api_endpoint = api_endpoint
        
        # 创建必要的目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("=== Novel Audio Synthesizer 初始化完成 ===")
        print(f"📁 剧本目录: {self.script_dir}")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"🌐 API端点: {self.api_endpoint}")
    
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
    
    def check_and_start_service(self) -> bool:
        """
        检查并启动服务
        :return: 服务是否正常启动
        """
        print("\n=== 服务管理 ===")
        
        # 检查Docker是否安装
        try:
            import subprocess
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
            print("✅ Docker 已安装")
        except (ImportError, subprocess.CalledProcessError):
            print("⚠️ Docker 未安装，跳过服务启动")
            return True
        
        # 检查并停止旧容器
        try:
            result = subprocess.run(["docker", "ps", "-a", "--filter", "name=easyvoice"], capture_output=True, text=True, check=True)
            if "easyvoice" in result.stdout:
                print("⚠️ 发现旧的easyvoice容器，尝试停止并删除")
                subprocess.run(["docker", "stop", "easyvoice"], capture_output=True, check=False)
                subprocess.run(["docker", "rm", "easyvoice"], capture_output=True, check=False)
                print("✅ 旧容器已删除")
        except subprocess.CalledProcessError:
            print("⚠️ 检查Docker容器失败")
        
        # 启动新容器
        try:
            print("📦 启动 easyVoice Docker 容器...")
            audio_dir = os.path.join(self.base_dir, "../audio")
            # 启动容器时设置工作目录为/app/audio，让EasyVoice直接在audio目录下生成文件
            result = subprocess.run([
                "docker", "run", "-d", "--name", "easyvoice", "-p", "3000:3000", 
                "-v", f"{audio_dir}:/app/audio", "--workdir", "/app/audio", 
                "cosincox/easyvoice:latest"
            ], capture_output=True, text=True, check=True)
            print("✅ easyVoice 服务启动成功")
            
            # 检查服务是否正常运行
            print("🔍 检查服务是否正常运行...")
            time.sleep(5)  # 等待服务启动
            
            response = requests.get("http://localhost:3000/api/v1/tts/health", timeout=10)
            if response.status_code == 200:
                print("✅ 服务健康检查通过")
                return True
            else:
                print(f"❌ 服务健康检查失败 (状态码: {response.status_code})")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"❌ 启动Docker容器失败: {e.stderr}")
            return False
        except requests.RequestException as e:
            print(f"❌ 服务连接失败: {e}")
            return False
    
    def process_novel(self, json_file: str) -> str:
        """
        处理单个小说章节
        :param json_file: 小说JSON文件路径
        :return: 生成的音频文件路径
        """
        print(f"\n=== 处理小说章节: {json_file} ===")
        
        # 生成音频
        generator = AudioGenerator(
            json_path=json_file,
            output_dir=self.output_dir,
            api_endpoint=self.api_endpoint
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
        
        # 检查并启动服务
        self.check_and_start_service()
        
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
    parser.add_argument("--output-dir", type=str, help="音频输出目录")
    parser.add_argument("--api-endpoint", type=str, default="http://localhost:3000/api/v1/tts/generateJson", help="TTS API端点")
    
    args = parser.parse_args()
    
    # 初始化合成器
    synthesizer = NovelAudioSynthesizer(
        output_dir=args.output_dir,
        api_endpoint=args.api_endpoint
    )
    
    # 运行合成器
    synthesizer.run(json_file=args.json_path)