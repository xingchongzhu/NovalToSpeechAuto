#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Processing Module
音频处理模块，提供语音合成、音频处理和混音功能

主要功能：
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
import hashlib
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import warnings

# 导入generate_audio模块
try:
    from stabilityai_stable_generate_audio import generate_audio_batch
    GENERATE_AUDIO_AVAILABLE = True
except Exception as e:
    print(f"[AudioEngine] 导入generate_audio模块失败: {e}")
    GENERATE_AUDIO_AVAILABLE = False
    
    def generate_audio_batch(tasks, max_workers=5):
        """批量生成的降级实现"""
        results = []
        for task in tasks:
            try:
                prompt = task["prompt"] if isinstance(task, dict) else task[0]
                output_path = task["output_path"] if isinstance(task, dict) else task[2]
                print(f"[AudioEngine] 跳过批量生成（模块未导入）: {output_path}")
                results.append(None)
            except:
                results.append(None)
        return results


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 禁用输出缓冲，确保日志实时显示
sys.stdout.reconfigure(line_buffering=True)
os.environ['PYTHONUNBUFFERED'] = '1'

# 忽略音频处理库的无关警告
warnings.filterwarnings("ignore")

try:
    from pydub import AudioSegment
except ImportError:
    logger.warning("⚠️ 未安装音频处理依赖，执行: pip install pydub")
    print("⚠️ 需安装 FFmpeg: https://ffmpeg.org/download.html")
    raise


# ======================== 数据结构定义 ========================
@dataclass
class VoiceParams:
    """语音参数数据类"""
    text: str
    role: str
    role_voice: str
    speed: str
    volume: str
    pitch: str
    instruct: Optional[str] = None

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
    play_mode: str
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
    mode: str
    voice_delay: Optional[float] = None

@dataclass
class LineAudioConfig:
    """单句音频配置数据类"""
    id: int
    role: str
    voice_params: VoiceParams
    bgm_params: Optional[BGMAudioParams]
    effect_params: List[EffectAudioParams]
    mix_config: MixConfig


# ======================== 音频引擎接口 ========================
class AudioEngine:
    """音频引擎类，提供语音合成和文生音频功能"""
    
    def __init__(self, temp_dir: str = "./temp_audio", sample_rate: int = 44100, 
                 channels: int = 1, tts_engine: str = "qwen3-tts", qwen_model_path: str = None):
        self.temp_dir = temp_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_format = "wav"
        self.tts_engine = tts_engine
        self.qwen_model_path = qwen_model_path
        self.qwen_tts_model = None
        
        os.makedirs(self.temp_dir, exist_ok=True)
        
        if self.tts_engine == "qwen3-tts":
            self._init_qwen_tts_model()

    def _init_qwen_tts_model(self):
        """初始化Qwen3-TTS模型"""
        try:
            import logging as py_logging
            py_logging.getLogger('qwen_tts').setLevel(py_logging.WARNING)
            py_logging.getLogger('transformers').setLevel(py_logging.WARNING)
            py_logging.getLogger('torch').setLevel(py_logging.WARNING)
            
            from qwen_tts import Qwen3TTSModel
            import torch
            
            print("[TTSEngine] 初始化Qwen3-TTS模型...")
            
            model_path = self.qwen_model_path if self.qwen_model_path else \
                "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model"
            
            self.qwen_tts_model = Qwen3TTSModel.from_pretrained(
                model_path,
                device_map="cpu",
                dtype=torch.float32,
            )
            
            self.qwen_model_type = getattr(self.qwen_tts_model.model, 'tts_model_type', 'unknown')
            print(f"[TTSEngine] Qwen3-TTS模型初始化成功!")
        except Exception as e:
            print(f"[TTSEngine] 初始化Qwen3-TTS模型失败: {e}")
            raise Exception("Qwen3-TTS模型初始化失败")

    def text_to_speech(self, params: VoiceParams) -> AudioSegment:
        """文本转语音接口"""
        print(f"\n[TTSEngine] 使用引擎: {self.tts_engine}")
        print(f"[TTSEngine] 生成[{params.role}]语音: {params.text[:20]}...")
        print(f"  - 音色: {params.role_voice} | 语速: {params.speed} | 音量: {params.volume}")
        
        try:
            start_time = time.time()
            if self.tts_engine == "qwen3-tts":
                audio = self._text_to_speech_qwen(params)
                elapsed_time = time.time() - start_time
                print(f"[TTSEngine] 语音生成完成，耗时: {elapsed_time:.2f} 秒")
                audio = self._adjust_audio_params(audio, params.speed, params.volume, params.pitch)
                return audio
            else:
                raise ValueError(f"未知的TTS引擎: {self.tts_engine}")
        except Exception as e:
            print(f"[TTSEngine] 语音生成失败: {e}")
            raise

    def _text_to_speech_qwen(self, params: VoiceParams) -> AudioSegment:
        """使用Qwen3-TTS引擎生成语音"""
        if self.qwen_tts_model is None:
            self._init_qwen_tts_model()
        
        import torch
        
        qwen_speaker = params.role_voice if params.role_voice else "阿传-男声-低沉,浑厚"
        instruct = params.instruct.strip() if params.instruct else "neutral"
        
        clone_audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"
        
        def _find_audio_file(speaker_name):
            for ext in ['.mp3', '.wav']:
                potential_path = os.path.join(clone_audio_dir, f"{speaker_name}{ext}")
                if os.path.exists(potential_path):
                    return potential_path
            return None
        
        def _generate_voice(ref_audio, x_vector_only_mode=True):
            return self.qwen_tts_model.generate_voice_clone(
                text=params.text,
                language="chinese",
                ref_audio=ref_audio,
                ref_text="",
                x_vector_only_mode=x_vector_only_mode,
                style=params.instruct if params.instruct else "neutral",
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.0
            )
        
        wavs, sr = None, None
        
        try:
            print(f"[TTSEngine] 尝试使用克隆语音: {qwen_speaker}")
            ref_audio_path = _find_audio_file(qwen_speaker)
            
            if ref_audio_path and hasattr(self.qwen_tts_model, 'generate_voice_clone'):
                wavs, sr = _generate_voice(ref_audio_path)
            else:
                print(f"[TTSEngine] 使用默认克隆声音")
                default_clone_audio = os.path.join(clone_audio_dir, 
                    "晓辰-女青年.mp3" if ("女" in params.role or "宁姚" in params.role or "稚圭" in params.role) 
                    else "知浩-男青年.mp3")
                
                if os.path.exists(default_clone_audio):
                    wavs, sr = _generate_voice(default_clone_audio)
                else:
                    wavs, sr = _generate_voice(None, x_vector_only_mode=False)
        except Exception as e:
            print(f"[TTSEngine] 生成语音失败: {e}")
            raise
        
        audio_data = np.concatenate(wavs) if isinstance(wavs, list) else wavs
        audio_data = np.clip(audio_data, -1, 1)
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val * 0.9
        
        audio_data_int16 = (audio_data * 32767).astype(np.int16)
        
        audio = AudioSegment(
            audio_data_int16.tobytes(),
            frame_rate=sr,
            sample_width=audio_data_int16.dtype.itemsize,
            channels=1
        )
        
        audio = audio.set_frame_rate(self.sample_rate).set_channels(self.channels)
        audio = audio.fade_in(100)
        
        silent_threshold = -60
        for i in range(0, len(audio), 10):
            if audio[i:i+10].dBFS > silent_threshold:
                audio = audio[i:]
                break
        
        audio = audio.fade_in(100)
        return audio

    def _adjust_audio_params(self, audio: AudioSegment, speed: str, volume: str, pitch: str) -> AudioSegment:
        """调整音频参数（语速/音量）"""
        if speed and speed != "+0%":
            try:
                speed_value = int(speed.replace("%", ""))
                speed_factor = 1.0 + (speed_value / 100.0)
                
                if speed_factor > 0:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_input:
                        audio.export(temp_input.name, format="wav")
                        temp_input_path = temp_input.name
                    
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_output:
                        temp_output_path = temp_output.name
                    
                    ffmpeg_cmd = [
                        "ffmpeg", "-i", temp_input_path,
                        "-filter:a", f"atempo={speed_factor}",
                        "-y", temp_output_path
                    ]
                    
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        audio = AudioSegment.from_wav(temp_output_path)
                    else:
                        if speed_factor > 1:
                            audio = audio.speedup(playback_speed=speed_factor, crossfade=25)
                    
                    os.unlink(temp_input_path)
                    os.unlink(temp_output_path)
            except Exception as e:
                print(f"[AudioEngine] 调整语速失败: {e}")
        
        if volume and volume != "+0%":
            try:
                volume_value = int(volume.replace("%", ""))
                db_adjustment = volume_value * 0.1
                audio = audio + db_adjustment
            except Exception as e:
                print(f"[AudioEngine] 调整音量失败: {e}")
        
        return audio

    def mix_audio(self, voice: AudioSegment, bgm: AudioSegment, effects: List[AudioSegment], 
                  mix_config: MixConfig, effect_params: List = None) -> AudioSegment:
        """按规则混音"""
        print(f"[MixEngine] 混音模式: {mix_config.mode}")
        
        voice_duration = len(voice)
        
        if bgm is None:
            bgm = AudioSegment.silent(duration=voice_duration)
        
        if len(bgm) > 0:
            if len(bgm) < voice_duration:
                loop_count = voice_duration // len(bgm)
                remaining = voice_duration % len(bgm)
                bgm = bgm * loop_count + bgm[:remaining]
            else:
                bgm = bgm[:voice_duration]
            bgm = bgm - 12
        
        if mix_config.mode == "bgm_fade_in_then_voice":
            bgm = bgm.fade_in(int(mix_config.voice_delay * 1000))
            final_audio = bgm
            if voice_duration > len(bgm):
                final_audio = bgm + AudioSegment.silent(duration=voice_duration - len(bgm))
            final_audio = final_audio.overlay(voice, position=int(mix_config.voice_delay * 1000))
        
        elif mix_config.mode == "voice_on_bgm":
            final_audio = voice
            if len(bgm) > 0:
                final_audio = final_audio.overlay(bgm)
        
        elif mix_config.mode == "mix":
            final_audio = voice
            if len(bgm) > 0:
                final_audio = final_audio.overlay(bgm)
            for i, effect in enumerate(effects):
                if effect_params and i < len(effect_params):
                    delay_ms = int(effect_params[i].trigger_delay * 1000)
                    if delay_ms > 0:
                        final_audio = final_audio.overlay(effect, position=delay_ms)
                    else:
                        final_audio = final_audio.overlay(effect)
                else:
                    final_audio = final_audio.overlay(effect)
        
        elif mix_config.mode == "voice_only":
            final_audio = voice
        
        else:
            final_audio = voice
        
        pause = AudioSegment.silent(duration=300)
        final_audio = final_audio + pause
        
        return final_audio

    def clean_temp_files(self):
        """清理临时音频文件"""
        for file in os.listdir(self.temp_dir):
            if file.endswith(self.audio_format):
                os.remove(os.path.join(self.temp_dir, file))


# ======================== 核心解析与生成逻辑 ========================
class AudioGenerator:
    """小说有声书音频生成器"""
    
    def __init__(self, json_path: str, output_dir: str = None, 
                 tts_engine: str = "qwen3-tts", qwen_model_path: str = None):
        if output_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(base_dir, "../../output")
        
        self.json_path = json_path
        self.tts_engine = tts_engine
        self.qwen_model_path = qwen_model_path
        
        self.config = self.load_config()
        self.chapter_name = self.config["chapter"]
        
        self.novel_name = os.path.basename(os.path.dirname(json_path))
        self.chapter_clean_name = self.chapter_name.replace("\n", "").replace(" ", "_").replace(":", "-")
        
        self.output_dir = os.path.join(output_dir, self.novel_name)
        self.chapter_dir = os.path.join(self.output_dir, self.chapter_clean_name)
        
        self.voice_dir = os.path.join(self.chapter_dir, "配音")
        self.bgm_dir = os.path.join(self.chapter_dir, "背景音")
        self.effect_dir = os.path.join(self.chapter_dir, "音效")
        self.mix_dir = os.path.join(self.chapter_dir, "混音")
        self.tmp_dir = os.path.join(self.chapter_dir, "tmp")
        
        os.makedirs(self.voice_dir, exist_ok=True)
        os.makedirs(self.bgm_dir, exist_ok=True)
        os.makedirs(self.effect_dir, exist_ok=True)
        os.makedirs(self.mix_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)
        
        self.audio_engine = AudioEngine(
            temp_dir=self.tmp_dir,
            sample_rate=44100,
            channels=self.config["global"]["channels"],
            tts_engine=self.tts_engine,
            qwen_model_path=self.qwen_model_path
        )

    def load_config(self) -> Dict[str, Any]:
        """加载JSON配置"""
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            self.roles_definition = config.get("roles_definition", {})
            return config
        except Exception as e:
            print(f"❌ 加载JSON失败: {e}")
            raise

    def _parse_line_config(self, line: Dict[str, Any]) -> LineAudioConfig:
        """解析单句配置"""
        role = line["role"]
        
        tts_engine = getattr(self.audio_engine, 'tts_engine', "qwen3-tts")
        
        voice_params_dict = None
        voice_data = line["api"].get("voice", {})
        
        if tts_engine == "qwen3-tts":
            if voice_data:
                voice_params_dict = voice_data.copy()
            elif hasattr(self, 'roles_definition') and role in self.roles_definition:
                role_def = self.roles_definition[role]
                if 'voice' in role_def:
                    voice_params_dict = role_def['voice'].copy()
        
        if voice_params_dict is None:
            if voice_data:
                voice_params_dict = voice_data.copy()
            elif hasattr(self, 'roles_definition') and role in self.roles_definition:
                role_def = self.roles_definition[role]
                if 'voice' in role_def:
                    voice_params_dict = role_def['voice'].copy()
        
        if voice_params_dict and 'text' not in voice_params_dict:
            voice_params_dict['text'] = line.get('text', '')
        
        voice_params = VoiceParams(**voice_params_dict)
        
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
        
        mix_config = MixConfig(**line["mix"])
        
        return LineAudioConfig(
            id=line["id"],
            role=role,
            voice_params=voice_params,
            bgm_params=bgm_params,
            effect_params=effect_params,
            mix_config=mix_config
        )

    def generate_single_line(self, line_config: LineAudioConfig) -> AudioSegment:
        """生成单句音频"""
        print(f"\n=== 处理章节: {self.chapter_name} 第 {line_config.id} 句 | 角色: {line_config.role} ===")
        
        voice_output_path = os.path.join(self.voice_dir, f"voice_line_{line_config.id}.wav")
        if os.path.exists(voice_output_path):
            print(f"✅ 配音文件已存在，跳过生成: {voice_output_path}")
            voice_audio = AudioSegment.from_wav(voice_output_path)
        else:
            voice_audio = self.audio_engine.text_to_speech(line_config.voice_params)
            voice_audio.export(voice_output_path, format="wav")
            print(f"💾 单句配音已保存: {voice_output_path}")
        
        bgm_audio = None
        effect_audios = []
        bgm_output_path = None
        effect_output_paths = []
        
        batch_tasks = []
        MAX_DURATION = 47
        
        if line_config.bgm_params is not None:
            bgm_duration = min(len(voice_audio) / 1000.0, MAX_DURATION)
            bgm_scene_cn = line_config.bgm_params.scene.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            bgm_output_path = os.path.join(self.bgm_dir, f"bgm_line_{bgm_scene_cn}_{line_config.id}.wav")
            
            #屏蔽背景音
            #if not os.path.exists(bgm_output_path):
            #    batch_tasks.append({
            #        "prompt": line_config.bgm_params.scene_en,
            #        "duration": bgm_duration,
            #        "output_path": bgm_output_path
            #    })
        
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
        
        if batch_tasks:
            print(f"🔄 开始多线程批量生成 {len(batch_tasks)} 个音频...")
            generate_audio_batch(batch_tasks)
        
        if bgm_output_path and os.path.exists(bgm_output_path):
            bgm_audio = AudioSegment.from_wav(bgm_output_path)
            if line_config.bgm_params.play_mode == "lower" and line_config.bgm_params.lower_db:
                bgm_audio = bgm_audio - line_config.bgm_params.lower_db
            bgm_audio = bgm_audio - 2.0
        
        for i, effect_output_path in enumerate(effect_output_paths):
            if os.path.exists(effect_output_path):
                effect_audio = AudioSegment.from_wav(effect_output_path)
                effect_param = line_config.effect_params[i]
                effect_audio = effect_audio[:int(effect_param.duration * 1000)]
                effect_audios.append(effect_audio)
        
        mixed_audio = self.audio_engine.mix_audio(
            voice=voice_audio,
            bgm=bgm_audio,
            effects=effect_audios,
            mix_config=line_config.mix_config,
            effect_params=line_config.effect_params
        )
        
        single_output_path = os.path.join(self.mix_dir, f"mixed_line_{line_config.id}.wav")
        mixed_audio.export(single_output_path, format="wav")
        print(f"💾 单句混合音频已保存: {single_output_path}")
        
        return mixed_audio

    def generate_chapter_audio(self) -> str:
        """生成整章音频"""
        chapter_output_path = os.path.join(self.chapter_dir, f"{self.chapter_clean_name}_full.wav")
        if os.path.exists(chapter_output_path):
            print(f"✅ 整章音频已存在，跳过生成: {chapter_output_path}")
            return chapter_output_path
        
        if self.tts_engine == "qwen3-tts":
            return self.generate_chapter_audio_serial()
        else:
            return self.generate_chapter_audio_parallel()

    def generate_chapter_audio_serial(self) -> str:
        """串行生成整章音频"""
        print(f"\n🚀 开始串行生成《{self.chapter_name}》完整音频")
        start_time = time.time()
        
        line_configs = [self._parse_line_config(line) for line in self.config["data"]]
        
        results = []
        total_lines = len(line_configs)
        for i, line_config in enumerate(line_configs):
            print(f"[进度] 处理第 {i+1}/{total_lines} 句 (角色: {line_config.role})")
            try:
                line_audio = self.generate_single_line(line_config)
                results.append((line_config.id, line_audio))
            except Exception as e:
                print(f"❌ 处理第 {line_config.id} 句时发生异常: {e}")
                results.append((line_config.id, None))
        
        results.sort(key=lambda x: x[0])
        
        merged_audio = AudioSegment.silent(duration=0, frame_rate=44100)
        for line_id, line_audio in results:
            if line_audio is not None:
                merged_audio += line_audio
                if line_id == 0:
                    merged_audio += AudioSegment.silent(duration=1000, frame_rate=44100)
        
        chapter_output_path = os.path.join(self.chapter_dir, f"{self.chapter_clean_name}_full.wav")
        merged_audio.export(chapter_output_path, format="wav")
        
        self.audio_engine.clean_temp_files()
        
        end_time = time.time()
        print(f"\n🎉 整章音频串行生成完成！耗时: {end_time - start_time:.2f} 秒")
        print(f"📂 输出路径: {chapter_output_path}")
        
        return chapter_output_path

    def generate_chapter_audio_parallel(self) -> str:
        """并行生成整章音频"""
        print(f"\n🚀 开始并行生成《{self.chapter_name}》完整音频")
        start_time = time.time()
        
        line_configs = [self._parse_line_config(line) for line in self.config["data"]]
        
        merged_audio = AudioSegment.silent(duration=0, frame_rate=44100)
        
        for line_config in line_configs:
            try:
                line_audio = self.generate_single_line(line_config)
                merged_audio += line_audio
                if line_config.id == 0:
                    merged_audio += AudioSegment.silent(duration=2000, frame_rate=44100)
            except Exception as e:
                print(f"❌ 处理第 {line_config.id} 句时发生异常: {e}")
        
        chapter_output_path = os.path.join(self.chapter_dir, f"{self.chapter_clean_name}_full.wav")
        merged_audio.export(chapter_output_path, format="wav")
        
        self.audio_engine.clean_temp_files()
        
        end_time = time.time()
        print(f"\n🎉 整章音频并行生成完成！耗时: {end_time - start_time:.2f} 秒")
        print(f"📂 输出路径: {chapter_output_path}")
        
        return chapter_output_path


# ======================== 小说音频合成器 ========================
class NovelAudioSynthesizer:
    """小说音频合成器，用于生成单个或多个小说章节的完整音频"""
    
    def __init__(self, script_dir: str = None, output_dir: str = None, 
                 tts_engine: str = "qwen3-tts", qwen_model_path: str = None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.script_dir = script_dir or os.path.join(self.base_dir, "../小说剧本")
        self.output_dir = output_dir or os.path.join(self.base_dir, "../../output")
        self.tts_engine = tts_engine
        self.qwen_model_path = qwen_model_path if qwen_model_path else \
            "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model"
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("=== Novel Audio Synthesizer 初始化完成 ===")
        print(f"📁 剧本目录: {self.script_dir}")
        print(f"📁 输出目录: {self.output_dir}")

    def check_environment(self) -> bool:
        """检查环境"""
        print("\n=== 环境检测 ===")
        
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            print("✅ FFmpeg 已安装")
        except (ImportError, subprocess.CalledProcessError):
            print("❌ FFmpeg 未安装")
            return False
        
        try:
            import pydub
            print("✅ pydub 已安装")
        except ImportError:
            print("❌ pydub 未安装")
            return False
        
        print("✅ 环境检测通过")
        return True

    def process_novel(self, json_file: str) -> str:
        """处理单个小说章节"""
        print(f"\n=== 处理小说章节: {json_file} ===")
        
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            chapter_name = config["chapter"]
            chapter_clean_name = chapter_name.replace("\n", "").replace(" ", "_").replace(":", "-")
            
            chapter_dir = os.path.join(self.output_dir, os.path.basename(os.path.dirname(json_file)), chapter_clean_name)
            chapter_output_path = os.path.join(chapter_dir, f"{chapter_clean_name}_full.wav")
            
            if os.path.exists(chapter_output_path):
                print(f"✅ 整章音频已存在，跳过生成: {chapter_output_path}")
                return chapter_output_path
        except Exception as e:
            print(f"❌ 检查整章音频时发生错误: {e}")
        
        generator = AudioGenerator(
            json_path=json_file,
            output_dir=self.output_dir,
            tts_engine=self.tts_engine,
            qwen_model_path=self.qwen_model_path
        )
        
        return generator.generate_chapter_audio()

    def process_all_novels(self) -> List[str]:
        """处理所有小说章节"""
        print(f"\n=== 处理所有小说章节 ===")
        
        output_paths = []
        
        for novel_name in os.listdir(self.script_dir):
            novel_dir = os.path.join(self.script_dir, novel_name)
            if not os.path.isdir(novel_dir):
                continue
            
            print(f"\n📖 处理小说: {novel_name}")
            
            for json_file in os.listdir(novel_dir):
                if not json_file.endswith(".json"):
                    continue
                
                json_path = os.path.join(novel_dir, json_file)
                output_path = self.process_novel(json_path)
                output_paths.append(output_path)
        
        return output_paths

    def run(self, json_file: str = None) -> List[str]:
        """运行小说音频合成器"""
        if not self.check_environment():
            return []
        
        if json_file:
            output_path = self.process_novel(json_file)
            output_paths = [output_path] if output_path else []
        else:
            output_paths = self.process_all_novels()
        
        print(f"\n🗑️ 清理临时文件...")
        audio_dir = os.path.join(self.base_dir, "../audio")
        if os.path.exists(audio_dir):
            for file_name in os.listdir(audio_dir):
                file_path = os.path.join(audio_dir, file_name)
                if file_name.endswith(".mp3_tmp"):
                    try:
                        if os.path.isdir(file_path):
                            import shutil
                            shutil.rmtree(file_path)
                        else:
                            os.remove(file_path)
                    except Exception as e:
                        pass
        
        print(f"\n=== 处理完成 ===")
        print(f"📊 共生成 {len(output_paths)} 个音频文件")
        for path in output_paths:
            print(f"📄 {path}")
        
        return output_paths


# ======================== 运行入口 ========================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="小说有声书音频合成工具")
    parser.add_argument("--json-path", type=str, help="小说剧本JSON文件路径")
    parser.add_argument("--script-dir", type=str, help="小说剧本目录路径")
    parser.add_argument("--output-dir", type=str, help="音频输出目录")
    parser.add_argument("--tts-engine", type=str, default="qwen3-tts", help="TTS引擎类型")
    parser.add_argument("--qwen-model-path", type=str, default="/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model", 
                        help="Qwen TTS模型路径")
    
    args = parser.parse_args()
    
    synthesizer = NovelAudioSynthesizer(
        script_dir=args.script_dir,
        output_dir=args.output_dir,
        tts_engine=args.tts_engine,
        qwen_model_path=args.qwen_model_path
    )
    
    if args.json_path:
        synthesizer.run(json_file=args.json_path)
    else:
        synthesizer.run()