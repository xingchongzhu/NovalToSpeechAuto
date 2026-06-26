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

import os
os.environ['HUGGINGFACE_HUB_DISABLE_REPO_ID_VALIDATION'] = '1'

import io
import json
import time
import requests
import sys
import logging
import numpy as np
import hashlib
import subprocess
import tempfile
import pickle
import base64
import concurrent.futures
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import re
import warnings
import gc
import psutil

# ======================== 音效/背景音生成引擎注册 ========================
# 支持 sfx_engine / bgm_engine 参数灵活切换: "woosh" | "stable-audio-3"

# Stable Audio 3 MLX 引擎
try:
    from stable_audio3_background_generate_audio import generate_audio_batch as _stable_audio3_generate_audio_batch
    _STABLE_AUDIO3_AVAILABLE = True
except Exception as e:
    print(f"[AudioEngine] 导入 stable-audio-3 模块失败: {e}")
    _STABLE_AUDIO3_AVAILABLE = False

# Woosh-DFlow 引擎
try:
    from woosh_generate_audio import generate_audio_batch as _woosh_generate_audio_batch
    _WOOSH_AVAILABLE = True
except Exception as e:
    print(f"[AudioEngine] 导入 woosh 模块失败: {e}")
    _WOOSH_AVAILABLE = False


def get_audio_engine(engine_name: str = "woosh", engine_role: str = "音效"):
    """获取音频生成引擎的 generate_audio_batch 函数，仅支持 woosh / stable-audio-3。"""
    if engine_name == "woosh":
        if _WOOSH_AVAILABLE:
            print(f"[AudioEngine] 使用{engine_role}引擎: Woosh-DFlow")
            return _woosh_generate_audio_batch
        print(f"[AudioEngine] {engine_role}引擎 Woosh 不可用，降级到空引擎")
    elif engine_name == "stable-audio-3":
        if _STABLE_AUDIO3_AVAILABLE:
            print(f"[AudioEngine] 使用{engine_role}引擎: Stable Audio 3 MLX")
            return _stable_audio3_generate_audio_batch
        print(f"[AudioEngine] {engine_role}引擎 stable-audio-3 不可用，降级到空引擎")
    else:
        print(f"[AudioEngine] 不支持的{engine_role}引擎: {engine_name}，仅支持 woosh | stable-audio-3")

    def _fallback_generate_audio_batch(tasks, max_workers=1):
        results = []
        for task in tasks:
            try:
                output_path = task["output_path"] if isinstance(task, dict) else task[2]
                print(f"[AudioEngine] 跳过{engine_role}生成（无可用引擎）: {output_path}")
                results.append(None)
            except Exception:
                results.append(None)
        return results
    return _fallback_generate_audio_batch


def get_sfx_engine(engine_name: str = "woosh"):
    """获取音效生成引擎，默认 Woosh。"""
    return get_audio_engine(engine_name, "音效")


def get_bgm_engine(engine_name: str = "stable-audio-3"):
    """获取背景音生成引擎，默认 Stable Audio 3。"""
    return get_audio_engine(engine_name, "背景音")

# 导入多音字处理模块
try:
    from polyphone_processor import process_polyphone_text
    POLYPHONE_PROCESSOR_AVAILABLE = True
except Exception as e:
    print(f"[AudioEngine] 导入多音字处理模块失败: {e}")
    POLYPHONE_PROCESSOR_AVAILABLE = False
    
    def process_polyphone_text(text):
        """多音字处理的降级实现"""
        return text


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
class SoundscapeLayer:
    """整章/场景级背景音层"""
    name: str
    prompt: str
    start_line: int
    end_line: int
    duration: float
    volume: str
    fade_in: float
    fade_out: float
    loop: bool = True
    target_dbfs: float = -34.0
    high_pass_hz: int = 80
    low_pass_hz: int = 5500

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
    process_mode: str = "overlay"

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

@dataclass
class AudioPlatformProfile:
    """平台音频产出配置"""
    name: str
    output_format: str = "wav"
    sample_rate: int = 44100
    channels: int = 1
    bitrate: Optional[str] = None
    intro_template: Optional[str] = None
    outro_template: Optional[str] = None
    min_chapter_ms: Optional[int] = None
    max_chapter_ms: Optional[int] = None
    max_silence_ms: Optional[int] = None
    target_voice_dbfs: Optional[float] = None


PLATFORM_PROFILES: Dict[str, AudioPlatformProfile] = {
    "default": AudioPlatformProfile(name="default"),
    "ximalaya": AudioPlatformProfile(
        name="ximalaya",
        output_format="mp3",
        sample_rate=44100,
        channels=2,
        bitrate="192k",
        #intro_template="欢迎您收听由喜马拉雅出品的《{novel_name}》，作者{author}，演播{speaker}，欢迎订阅。",
        intro_template="欢迎您收听由喜马拉雅出品的《{novel_name}》，欢迎订阅。",
        outro_template="听众朋友，本集已播讲完毕，请订阅专辑，下集精彩继续。",
        min_chapter_ms=5 * 60 * 1000,
        max_chapter_ms=15 * 60 * 1000,
        max_silence_ms=5000,
        target_voice_dbfs=-18.0,
    ),
}


def get_platform_profile(platform_name: Optional[str]) -> AudioPlatformProfile:
    """获取平台配置，未知平台回退到 default。"""
    normalized = (platform_name or "default").strip().lower()
    return PLATFORM_PROFILES.get(normalized, PLATFORM_PROFILES["default"])


# ======================== 音频引擎接口 ========================
class AudioEngine:
    """音频引擎类，提供语音合成和文生音频功能"""
    
    def __init__(self, temp_dir: str = "./temp_audio", sample_rate: int = 44100, 
                 channels: int = 1, tts_engine: str = "qwen3-tts", qwen_model_path: str = None,
                 fish_api_url: str = "http://localhost:8080",
                 target_voice_dbfs: Optional[float] = None):
        self.temp_dir = temp_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_format = "wav"
        self.tts_engine = tts_engine
        self.qwen_model_path = qwen_model_path
        self.fish_api_url = fish_api_url.rstrip("/") if fish_api_url else "http://localhost:8080"
        self.target_voice_dbfs = target_voice_dbfs
        self.qwen_tts_model = None
        self._voice_clone_prompt_cache = {}  # 进程内缓存，避免当前运行重复编码参考音频
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.clone_audio_dir = os.path.join(project_root, "clone-audio")
        self.voice_prompt_cache_dir = os.path.join(self.clone_audio_dir, ".qwen_prompt_cache")
        
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.voice_prompt_cache_dir, exist_ok=True)
        
        if self.tts_engine == "qwen3-tts":
            self._init_qwen_tts_model()
        elif self.tts_engine == "fish-speech":
            print("[TTSEngine] 使用 Fish Speech API 引擎，地址: " + self.fish_api_url)

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
                "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
            
            # 自动选择最优设备：MPS(Apple GPU) > CUDA > CPU
            if torch.backends.mps.is_available():
                device = "mps"
                dtype = torch.float16
                print(f"[TTSEngine] 检测到Apple MPS，使用GPU加速 + float16")
            elif torch.cuda.is_available():
                device = "cuda:0"
                dtype = torch.bfloat16
                print(f"[TTSEngine] 检测到CUDA GPU，使用GPU加速 + bfloat16")
            else:
                device = "cpu"
                dtype = torch.float32
                print(f"[TTSEngine] 未检测到GPU，使用CPU + float32（速度较慢）")
            
            self.qwen_tts_model = Qwen3TTSModel.from_pretrained(
                model_path,
                device_map=device,
                dtype=dtype,
            )
            
            self.qwen_model_type = getattr(self.qwen_tts_model.model, 'tts_model_type', 'unknown')
            print(f"[TTSEngine] Qwen3-TTS模型初始化成功!")
        except Exception as e:
            print(f"[TTSEngine] 初始化Qwen3-TTS模型失败: {e}")
            raise Exception("Qwen3-TTS模型初始化失败")

    @staticmethod
    def _split_long_tts_text(text: str) -> list:
        """长文本保守语义断句（Fish Speech 复用）"""
        hard_splits = "。！？；!?;"
        max_chunk = 200

        stripped = text.strip()
        if len(stripped) <= max_chunk:
            return [stripped]

        segments = []
        current = ""
        for ch in stripped:
            current += ch
            if ch in hard_splits and len(current) >= 60:
                segments.append(current)
                current = ""
        if current.strip():
            segments.append(current.strip())

        # 合并过短的尾段
        merged = []
        for seg in segments:
            if merged and len(seg) < 30:
                merged[-1] += seg
            else:
                merged.append(seg)
        return merged if merged else [stripped]

    def text_to_speech(self, params: VoiceParams) -> AudioSegment:
        """文本转语音接口"""
        print(f"\n[TTSEngine] 使用引擎: {self.tts_engine}")
        print(f"[TTSEngine] 生成[{params.role}]语音: {params.text[:20]}...")
        print(f"  - 音色: {params.role_voice} | 语速: {params.speed} | 音量: {params.volume}")
        
        try:
            start_time = time.time()
            if self.tts_engine == "qwen3-tts":
                audio = self._text_to_speech_qwen(params)
            elif self.tts_engine == "fish-speech":
                audio = self._text_to_speech_fish(params)
            else:
                raise ValueError(f"未知的TTS引擎: {self.tts_engine}")
            elapsed_time = time.time() - start_time
            print(f"[TTSEngine] 语音生成完成，耗时: {elapsed_time:.2f} 秒")
            audio = self._adjust_audio_params(audio, params.speed, params.volume, params.pitch)
            return audio
        except Exception as e:
            print(f"[TTSEngine] 语音生成失败: {e}")
            raise

    def _text_to_speech_qwen(self, params: VoiceParams) -> AudioSegment:
        """使用Qwen3-TTS引擎生成语音"""
        if self.qwen_tts_model is None:
            self._init_qwen_tts_model()
        
        import torch
        
        qwen_speaker = params.role_voice if params.role_voice else "麦克-纪录片之王,麦克阿瑟"
        instruct = params.instruct.strip() if params.instruct else "neutral"
        
        clone_audio_dir = self.clone_audio_dir
        
        def _find_audio_file(speaker_name):
            for ext in ['.mp3', '.wav']:
                potential_path = os.path.join(clone_audio_dir, f"{speaker_name}{ext}")
                if os.path.exists(potential_path):
                    return potential_path
            return None
        
        def _get_prompt_cache_paths(ref_audio_path, x_vector_only_mode=True):
            file_stat = os.stat(ref_audio_path)
            model_name = self.qwen_model_path if self.qwen_model_path else "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
            cache_fingerprint = "|".join([
                os.path.abspath(ref_audio_path),
                str(file_stat.st_mtime_ns),
                str(file_stat.st_size),
                str(x_vector_only_mode),
                model_name,
            ])
            cache_name = hashlib.md5(cache_fingerprint.encode("utf-8")).hexdigest()
            return cache_fingerprint, os.path.join(self.voice_prompt_cache_dir, f"{cache_name}.pkl")

        def _get_cached_prompt(ref_audio_path, x_vector_only_mode=True):
            """获取缓存的voice_clone_prompt，优先读内存，其次读磁盘，最后现算并写回"""
            cache_key, cache_file_path = _get_prompt_cache_paths(ref_audio_path, x_vector_only_mode)
            if cache_key in self._voice_clone_prompt_cache:
                return self._voice_clone_prompt_cache[cache_key]

            if os.path.exists(cache_file_path):
                try:
                    with open(cache_file_path, "rb") as cache_file:
                        prompt_dict = pickle.load(cache_file)
                    self._voice_clone_prompt_cache[cache_key] = prompt_dict
                    print(f"[TTSEngine] 从磁盘加载voice_clone_prompt缓存: {ref_audio_path}")
                    return prompt_dict
                except Exception as e:
                    print(f"[TTSEngine] 读取voice_clone_prompt缓存失败，将重新生成: {e}")

            prompt_items = self.qwen_tts_model.create_voice_clone_prompt(
                ref_audio=ref_audio_path,
                ref_text="",
                x_vector_only_mode=x_vector_only_mode,
            )
            prompt_dict = self.qwen_tts_model._prompt_items_to_voice_clone_prompt(prompt_items)
            self._voice_clone_prompt_cache[cache_key] = prompt_dict

            try:
                with open(cache_file_path, "wb") as cache_file:
                    pickle.dump(prompt_dict, cache_file, protocol=pickle.HIGHEST_PROTOCOL)
                print(f"[TTSEngine] 已写入voice_clone_prompt磁盘缓存: {ref_audio_path}")
            except Exception as e:
                print(f"[TTSEngine] 写入voice_clone_prompt缓存失败: {e}")

            return prompt_dict
        
        def _clean_tts_text(text: str) -> str:
            """清理TTS文本：去除中文引号等TTS模型不支持的标点"""
            # 去除中文引号 "" '' — 这些是排版符号，不应被朗读
            text = text.replace('\u201c', '').replace('\u201d', '')
            text = text.replace('\u2018', '').replace('\u2019', '')
            return text

        def _split_long_qwen_text(text: str) -> List[str]:
            """对超长文本做保守语义断句，避免长句TTS过慢。"""
            hard_split_chars = "。！？；!?;"
            soft_split_chars = "，、：,:"
            preferred_soft_tokens = ["但是", "不过", "然后", "于是", "所以", "只是", "而且", "因为", "如果", "虽然", "然而", "并且", "同时", "并非", "只是说", "况且", "此外"]
            protected_prefix_tokens = ["就像", "这也是", "比如", "例如", "即便", "哪怕", "如果", "虽然", "但是", "不过", "而且", "并且", "于是", "所以", "只是", "然而", "同时", "却", "却会", "也会", "都", "就", "便", "还会", "仍然"]
            protected_suffix_tokens = ["来说", "的话", "而言", "之一", "那边", "位置", "原因"]
            min_split_length = 80
            target_chunk_length = 180
            max_chunk_length = 240
            absolute_max_chunk_length = 300
            min_tail_merge_length = 18

            stripped_text = text.strip()
            if len(stripped_text) <= max_chunk_length:
                return [stripped_text]

            def _is_protected_boundary(source_text: str, split_at: int) -> bool:
                left_context = source_text[max(0, split_at - 12):split_at]
                right_context = source_text[split_at:min(len(source_text), split_at + 12)]
                if any(right_context.startswith(token) for token in protected_prefix_tokens):
                    return True
                if any(left_context.endswith(token) for token in protected_suffix_tokens):
                    return True
                if right_context[:1] in "）)]】」』":
                    return True
                return False

            def _find_best_split_index(source_text: str) -> int:
                candidate_ranges = [
                    [idx for idx, ch in enumerate(source_text) if ch in hard_split_chars],
                    [idx for idx, ch in enumerate(source_text) if ch in "，：,:"] ,
                    [idx for idx, ch in enumerate(source_text) if ch == '、'],
                ]
                lower_bound = max(min_split_length - 1, len(source_text) // 3)
                upper_bound = len(source_text) - min_tail_merge_length
                for candidates in candidate_ranges:
                    valid_candidates = [
                        idx for idx in candidates
                        if lower_bound <= idx < upper_bound and not _is_protected_boundary(source_text, idx + 1)
                    ]
                    if valid_candidates:
                        return min(valid_candidates, key=lambda idx: abs((idx + 1) - target_chunk_length)) + 1

                for token in preferred_soft_tokens:
                    token_index = source_text.rfind(token, lower_bound, upper_bound)
                    if token_index > 0 and not _is_protected_boundary(source_text, token_index):
                        return token_index
                return -1

            segments: List[str] = []
            current = ""

            def _flush_current(force: bool = False):
                nonlocal current
                candidate = current.strip()
                if candidate and (force or len(candidate) >= min_split_length or not segments):
                    segments.append(candidate)
                    current = ""

            for char in stripped_text:
                current += char
                current_length = len(current.strip())
                if current_length < min_split_length:
                    continue

                if char in hard_split_chars and current_length >= target_chunk_length * 0.7:
                    if not _is_protected_boundary(current, len(current)):
                        _flush_current(force=True)
                        continue

                if char in "，：,:" and current_length >= target_chunk_length:
                    if not _is_protected_boundary(current, len(current)):
                        _flush_current(force=True)
                        continue

                if current_length >= max_chunk_length:
                    split_at = _find_best_split_index(current)
                    if split_at > 0:
                        left = current[:split_at].strip()
                        right = current[split_at:].strip()
                        if left:
                            segments.append(left)
                        current = right
                    elif current_length >= absolute_max_chunk_length:
                        fallback_candidates = [idx for idx, ch in enumerate(current) if ch in hard_split_chars + soft_split_chars]
                        if fallback_candidates:
                            split_at = fallback_candidates[-1] + 1
                            left = current[:split_at].strip()
                            right = current[split_at:].strip()
                            if left:
                                segments.append(left)
                            current = right
                        else:
                            _flush_current(force=True)

            if current.strip():
                if segments and len(current.strip()) < min_tail_merge_length:
                    segments[-1] += current.strip()
                else:
                    segments.append(current.strip())

            merged_segments: List[str] = []
            for segment in segments:
                if merged_segments and len(segment) < min_tail_merge_length:
                    merged_segments[-1] += segment
                else:
                    merged_segments.append(segment)

            normalized_segments: List[str] = []
            for segment in merged_segments:
                if normalized_segments and len(segment) < min_tail_merge_length:
                    normalized_segments[-1] += segment
                else:
                    normalized_segments.append(segment)

            if len(normalized_segments) <= 1:
                return [stripped_text]

            print(f"[TTSEngine] 长句切分: {len(stripped_text)}字 -> {len(normalized_segments)}段")
            print(f"[TTSEngine] 长句原文: {stripped_text}")
            for index, segment in enumerate(normalized_segments, start=1):
                print(f"[TTSEngine]   分段{index}/{len(normalized_segments)} ({len(segment)}字): {segment}")
            return normalized_segments

        def _generate_voice_chunk(processed_text: str, ref_audio, x_vector_only_mode=True):
            text_len = len(processed_text)
            max_tokens = min(2048, max(512, text_len * 8))

            # 优先使用缓存的prompt，避免重复编码参考音频
            if ref_audio is not None:
                cached_prompt = _get_cached_prompt(ref_audio, x_vector_only_mode)
                return self.qwen_tts_model.generate_voice_clone(
                    text=processed_text,
                    language="chinese",
                    voice_clone_prompt=cached_prompt,
                    style=params.instruct if params.instruct else "neutral",
                    temperature=0.7,
                    top_p=0.9,
                    top_k=50,
                    repetition_penalty=1.05,
                    max_new_tokens=max_tokens
                )

            return self.qwen_tts_model.generate_voice_clone(
                text=processed_text,
                language="chinese",
                ref_audio=ref_audio,
                ref_text="",
                x_vector_only_mode=x_vector_only_mode,
                style=params.instruct if params.instruct else "neutral",
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                repetition_penalty=1.05,
                max_new_tokens=max_tokens
            )

        def _generate_voice(ref_audio, x_vector_only_mode=True):
            # 多音字处理
            processed_text = process_polyphone_text(params.text)
            if processed_text != params.text and POLYPHONE_PROCESSOR_AVAILABLE:
                print(f"[TTSEngine] 多音字处理: {params.text[:30]}... -> {processed_text[:30]}...")
            # 清理中文引号等特殊标点
            processed_text = _clean_tts_text(processed_text)
            if processed_text != process_polyphone_text(params.text):
                print(f"[TTSEngine] 文本清理: 去除中文引号等特殊标点")

            text_segments = _split_long_qwen_text(processed_text)
            all_wavs = []
            sample_rate = None
            for index, text_segment in enumerate(text_segments, start=1):
                if len(text_segments) > 1:
                    print(f"[TTSEngine] 分段生成 {index}/{len(text_segments)}: {text_segment[:24]}...")
                wavs, sr = _generate_voice_chunk(text_segment, ref_audio, x_vector_only_mode)
                chunk_audio = np.concatenate(wavs) if isinstance(wavs, list) else wavs
                all_wavs.append(chunk_audio)
                sample_rate = sr

            if len(all_wavs) == 1:
                return all_wavs[0], sample_rate

            merged_audio = np.concatenate(all_wavs)
            return merged_audio, sample_rate
        
        wavs, sr = None, None

        try:
            print(f"[TTSEngine] 尝试使用克隆语音: {qwen_speaker}")
            ref_audio_path = _find_audio_file(qwen_speaker)

            if not ref_audio_path:
                raise FileNotFoundError(
                    f"找不到克隆音频文件: clone-audio/ 下未找到 '{qwen_speaker}.mp3' 或 '{qwen_speaker}.wav'。"
                    f"请检查 role_voice='{params.role_voice}' 是否与 clone-audio/ 中的音频文件名完全一致。"
                )

            wavs, sr = _generate_voice(ref_audio_path)
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
        if self.target_voice_dbfs is not None and audio.rms > 0:
            gain_change = self.target_voice_dbfs - audio.dBFS
            audio = audio.apply_gain(gain_change)
        audio = audio.fade_in(100)

        return audio


    def _text_to_speech_fish(self, params: VoiceParams) -> AudioSegment:
        """使用 Fish Speech API 引擎生成语音"""
        
        # 查找参考音频
        def _find_audio_file(speaker_name):
            import glob as _glob
            # 精确匹配
            for ext in ['.mp3', '.wav']:
                potential_path = os.path.join(self.clone_audio_dir, f"{speaker_name}{ext}")
                if os.path.exists(potential_path):
                    return potential_path
            # 前缀匹配
            pattern = os.path.join(self.clone_audio_dir, f"{speaker_name}-*.mp3")
            matches = _glob.glob(pattern)
            if matches:
                return matches[0]
            return None
        
        voice_name = params.role_voice if params.role_voice else "麦克-纪录片之王,麦克阿瑟"
        ref_audio_path = _find_audio_file(voice_name)
        if not ref_audio_path:
            print(f"[TTSEngine][Fish] ⚠️ 未找到参考音频 '{voice_name}'，使用零样本生成")
        
        # 读取参考音频 + 查找参考文本
        ref_audio_b64 = ""
        ref_text = ""
        if ref_audio_path:
            with open(ref_audio_path, "rb") as f:
                ref_audio_b64 = base64.b64encode(f.read()).decode("utf-8")
            prompt_file = os.path.join(self.clone_audio_dir, "prompt_texts.json")
            if os.path.exists(prompt_file):
                with open(prompt_file, "r", encoding="utf-8") as f:
                    prompts = json.load(f)
                for key in [voice_name, f"{voice_name}.mp3", f"{voice_name}.wav"]:
                    if key in prompts:
                        ref_text = prompts[key]
                        break
                if not ref_text:
                    for key in prompts:
                        if key.startswith(voice_name):
                            ref_text = prompts[key]
                            break
        
        text = params.text.strip()
        if not text:
            raise ValueError("合成文本为空")
        
        text_len = len(text)
        if text_len > 200:
            segments = _split_long_tts_text(text)
        else:
            segments = [text]
        
        full_audio = AudioSegment.silent(duration=0)
        total_segments = len(segments)
        
        for i, segment in enumerate(segments):
            print(f"[TTSEngine][Fish] 分段 {i+1}/{total_segments}: {segment[:30]}...")
            
            payload = {
                "text": segment,
                "reference_audio": ref_audio_b64,
                "reference_text": ref_text,
            }
            
            api_url = f"{self.fish_api_url}/v1/tts"
            start = time.time()
            
            try:
                resp = requests.post(api_url, json=payload, timeout=300)
                elapsed = time.time() - start
                
                if resp.status_code != 200:
                    raise RuntimeError(f"API 返回 {resp.status_code}: {resp.text[:200]}")
                
                result = resp.json()
                
                # 解码返回的音频
                if "audio" in result:
                    wav_bytes = base64.b64decode(result["audio"])
                elif "data" in result:
                    wav_bytes = base64.b64decode(result["data"])
                else:
                    raise RuntimeError(f"JSON missing audio: {list(result.keys())}")
                
                print(f"[TTSEngine][Fish] 分段 {i+1} 完成，耗时 {elapsed:.1f}s")
                
            except requests.exceptions.ConnectionError:
                raise RuntimeError(f"无法连接到 {api_url}，请确保 Fish Speech 服务已启动")
            except Exception as e:
                raise RuntimeError(f"Fish Speech API 失败: {e}")
            
            tmp_wav = os.path.join(self.temp_dir, f"_fish_{os.getpid()}_{i}.wav")
            with open(tmp_wav, "wb") as f:
                f.write(wav_bytes)
            
            seg_audio = AudioSegment.from_file(tmp_wav, format="wav")
            os.remove(tmp_wav)
            
            full_audio += seg_audio
        
        if full_audio.frame_rate != self.sample_rate:
            full_audio = full_audio.set_frame_rate(self.sample_rate)
        if full_audio.channels != self.channels:
            full_audio = full_audio.set_channels(self.channels)
        
        if self.target_voice_dbfs is not None and full_audio.rms > 0:
            gain_change = self.target_voice_dbfs - full_audio.dBFS
            full_audio = full_audio.apply_gain(gain_change)
        full_audio = full_audio.fade_in(100)
        
        return full_audio

    def _adjust_audio_params(self, audio: AudioSegment, speed: str, volume: str, pitch: str) -> AudioSegment:
        """调整音频参数（语速/音量）"""
        if speed and speed != "+0%":
            try:
                speed_value = int(speed.replace("%", ""))
                speed_factor = 1.0 + (speed_value / 100.0)
                
                if speed_factor > 0:
                    input_buffer = io.BytesIO()
                    audio.export(input_buffer, format="wav")
                    input_bytes = input_buffer.getvalue()

                    ffmpeg_cmd = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel", "error",
                        "-i", "pipe:0",
                        "-filter:a", f"atempo={speed_factor}",
                        "-f", "wav",
                        "pipe:1",
                    ]

                    result = subprocess.run(ffmpeg_cmd, input=input_bytes, capture_output=True)
                    if result.returncode == 0 and result.stdout:
                        audio = AudioSegment.from_file(io.BytesIO(result.stdout), format="wav")
                    else:
                        if result.stderr:
                            print(f"[AudioEngine] ffmpeg atempo处理失败: {result.stderr.decode('utf-8', errors='ignore')}")
                        if speed_factor > 1:
                            audio = audio.speedup(playback_speed=speed_factor, crossfade=25)
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
            bgm = bgm - 6
        
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
                process_mode = "overlay"
                delay_ms = 0
                if effect_params and i < len(effect_params):
                    delay_ms = max(0, int(effect_params[i].trigger_delay * 1000))
                    process_mode = getattr(effect_params[i], "process_mode", "overlay") or "overlay"

                if process_mode == "insert":
                    insert_position = min(delay_ms, len(final_audio))
                    prefix_audio = final_audio[:insert_position]
                    suffix_audio = final_audio[insert_position:]
                    final_audio = prefix_audio + effect + suffix_audio
                elif delay_ms > 0:
                    final_audio = final_audio.overlay(effect, position=delay_ms)
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
                 tts_engine: str = "qwen3-tts", qwen_model_path: str = None,
                 sfx_engine: str = "woosh", bgm_engine: str = "stable-audio-3",
                 persist_intermediate_audio: bool = False,
                 platform: str = "default"):
        if output_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(base_dir, "../../output")
        
        self.json_path = json_path
        self.tts_engine = tts_engine
        self.qwen_model_path = qwen_model_path
        self.sfx_engine = sfx_engine
        self.bgm_engine = bgm_engine
        self.persist_intermediate_audio = persist_intermediate_audio
        self.platform_profile = get_platform_profile(platform)
        self.platform_name = self.platform_profile.name

        # 初始化音效与背景音生成引擎
        self._generate_sfx_batch = get_sfx_engine(self.sfx_engine)
        self._generate_bgm_batch = get_bgm_engine(self.bgm_engine)
        
        self.config = self.load_config()
        self.chapter_name = self.config["chapter"]
        
        self.novel_name = os.path.basename(os.path.dirname(json_path))
        self.chapter_clean_name = self.chapter_name.replace("\n", "").replace(" ", "_").replace(":", "-")
        
        self.output_dir = os.path.join(output_dir, self.novel_name)
        self.chapter_dir = os.path.join(self.output_dir, self.chapter_clean_name)
        self.intro_outro_dir = os.path.join(self.output_dir, "片头片尾")
        
        self.voice_dir = os.path.join(self.chapter_dir, "配音")
        self.bgm_dir = os.path.join(self.chapter_dir, "背景音")
        self.effect_dir = os.path.join(self.chapter_dir, "音效")
        self.mix_dir = os.path.join(self.chapter_dir, "混音")
        self.tmp_dir = os.path.join(self.chapter_dir, "tmp")

        os.makedirs(self.intro_outro_dir, exist_ok=True)
        os.makedirs(self.voice_dir, exist_ok=True)
        os.makedirs(self.bgm_dir, exist_ok=True)
        os.makedirs(self.effect_dir, exist_ok=True)
        os.makedirs(self.mix_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)

        # 错误段落追踪：记录本章合成失败的行 {line_id: {role, text, error, timestamp}}
        self.failed_lines: Dict[int, Dict[str, Any]] = {}
        # 已持久化到磁盘的失败记录路径
        self.failed_lines_log_path = os.path.join(self.chapter_dir, "failed_lines.json")
        
        platform_channels = self.platform_profile.channels or 1
        self.audio_engine = AudioEngine(
            temp_dir=self.tmp_dir,
            sample_rate=self.platform_profile.sample_rate,
            channels=platform_channels,
            tts_engine=self.tts_engine,
            qwen_model_path=self.qwen_model_path,
            target_voice_dbfs=self.platform_profile.target_voice_dbfs,
        )
        self.total_lines = len(self.config.get("data", []))

    @staticmethod
    def _sanitize_metadata_value(value: Optional[str], fallback: str) -> str:
        text = str(value).strip() if value is not None else ""
        return text if text else fallback

    def _extract_platform_metadata(self) -> Dict[str, str]:
        metadata = self.config.get("metadata") or {}
        intro_config = self.config.get("片头") or {}
        chapter_label = self.chapter_name
        chapter_match = re.search(r"第[^\s，。,:：]*[章节回小节集卷部篇幕话]", self.chapter_name)
        if chapter_match:
            chapter_label = chapter_match.group(0)

        return {
            "novel_name": self._sanitize_metadata_value(
                intro_config.get("novel_name") or metadata.get("novel_name") or self.novel_name,
                self.novel_name,
            ),
            "author": self._sanitize_metadata_value(
                intro_config.get("author") or metadata.get("author"),
                "佚名",
            ),
            "speaker": self._sanitize_metadata_value(
                intro_config.get("speaker") or metadata.get("speaker") or metadata.get("narrator"),
                "AI演播",
            ),
            "role_voice": self._sanitize_metadata_value(
                intro_config.get("role_voice") or self.roles_definition.get("旁白", {}).get("role_voice"),
                "麦克-纪录片之王,麦克阿瑟",
            ),
            "chapter_label": self._sanitize_metadata_value(
                intro_config.get("chapter_label") or metadata.get("chapter_label") or chapter_label,
                self.chapter_name,
            ),
        }

    def _platform_asset_path(self, asset_type: str, text: str) -> str:
        output_ext = self.platform_profile.output_format
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
        return os.path.join(self.intro_outro_dir, f"{asset_type}_{text_hash}.{output_ext}")

    def _generate_platform_asset(self, asset_type: str, text: str) -> Optional[str]:
        if not text:
            return None

        asset_path = self._platform_asset_path(asset_type, text)
        if os.path.exists(asset_path):
            return asset_path

        platform_metadata = self._extract_platform_metadata()
        platform_role_voice = platform_metadata.get("role_voice", "麦克-纪录片之王,麦克阿瑟")

        if asset_type == "片头":
            voice_params = VoiceParams(
                text=text,
                role="平台片头",
                role_voice=platform_role_voice,
                speed="-8%",
                volume="+0%",
                pitch="+0Hz",
                instruct="庄重开场",
            )
        else:
            voice_params = VoiceParams(
                text=text,
                role="平台片尾",
                role_voice=platform_role_voice,
                speed="-5%",
                volume="+0%",
                pitch="+0Hz",
                instruct="温和收束",
            )

        asset_audio = self.audio_engine.text_to_speech(voice_params)
        export_kwargs = {"format": self.platform_profile.output_format}
        if self.platform_profile.bitrate:
            export_kwargs["bitrate"] = self.platform_profile.bitrate
        asset_audio.export(asset_path, **export_kwargs)
        print(f"💾 已生成固定{asset_type}: {asset_path}")
        return asset_path

    def _load_platform_asset_audio(self, asset_type: str, text: str) -> Optional[AudioSegment]:
        asset_path = self._generate_platform_asset(asset_type, text)
        if not asset_path or not os.path.exists(asset_path):
            return None
        return AudioSegment.from_file(asset_path).set_frame_rate(self.platform_profile.sample_rate).set_channels(self.platform_profile.channels)

    def _build_platform_audio(self, merged_audio: AudioSegment) -> AudioSegment:
        print(f"\n📻 开始拼接平台音频（{self.platform_profile.name}）...")
        result = merged_audio.set_frame_rate(self.platform_profile.sample_rate).set_channels(self.platform_profile.channels)
        metadata = self._extract_platform_metadata()
        intro_text = None
        outro_text = None
        if self.platform_profile.intro_template:
            intro_text = self.platform_profile.intro_template.format(**metadata)
        if self.platform_profile.outro_template:
            outro_text = self.platform_profile.outro_template.format(**metadata)

        intro_audio = self._load_platform_asset_audio("片头", intro_text)
        if intro_audio is not None:
            print(f"  ✅ 片头已加载（{len(intro_audio) / 1000:.1f}s），拼接到正文前")
            result = intro_audio + AudioSegment.silent(duration=300, frame_rate=self.platform_profile.sample_rate) + result
        else:
            print(f"  ⚠️ 片头未生成，跳过")

        outro_audio = self._load_platform_asset_audio("片尾", outro_text)
        if outro_audio is not None:
            print(f"  ✅ 片尾已加载（{len(outro_audio) / 1000:.1f}s），拼接到正文后")
            result = result + AudioSegment.silent(duration=300, frame_rate=self.platform_profile.sample_rate) + outro_audio
        else:
            print(f"  ⚠️ 片尾未生成，跳过")

        duration_ms = len(result)
        print(f"  📏 最终音频总时长: {duration_ms / 1000:.1f}s / {duration_ms / 60000:.2f}min")
        if self.platform_profile.min_chapter_ms and duration_ms < self.platform_profile.min_chapter_ms:
            print(f"⚠️ 当前章节总时长约 {duration_ms / 60000:.2f} 分钟，低于 {self.platform_profile.name} 要求的 5 分钟下限")
        if self.platform_profile.max_chapter_ms and duration_ms > self.platform_profile.max_chapter_ms:
            print(f"⚠️ 当前章节总时长约 {duration_ms / 60000:.2f} 分钟，超过 {self.platform_profile.name} 建议的 15 分钟上限")

        return result

    def _export_chapter_audio(self, merged_audio: AudioSegment) -> str:
        print(f"\n📦 开始导出最终章节音频...")
        final_audio = self._build_platform_audio(merged_audio)
        output_ext = self.platform_profile.output_format
        chapter_output_path = os.path.join(self.chapter_dir, f"{self.chapter_clean_name}.{output_ext}")
        export_kwargs = {"format": output_ext}
        if self.platform_profile.bitrate:
            export_kwargs["bitrate"] = self.platform_profile.bitrate
        print(f"  📡 正在编码导出，格式: {output_ext.upper()}/{self.platform_profile.channels}ch/{self.platform_profile.sample_rate}Hz...")
        final_audio.export(chapter_output_path, **export_kwargs)
        print(f"  💾 导出完成: {chapter_output_path}")
        return chapter_output_path

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

    def record_failed_line(self, line_config: LineAudioConfig, error: Exception):
        """记录合成失败的单句段落

        Why: 整章合成时若个别行失败，需要保留现场便于事后排查；同时用于在最后合成整章音频前判断是否允许继续。
        How to apply: 在 generate_chapter_audio_serial / parallel 的 except 分支中调用。
        """
        text_preview = (line_config.voice_params.text or "").replace('\n', ' ')[:80]
        entry = {
            "line_id": line_config.id,
            "role": line_config.role,
            "text": text_preview,
            "error": str(error),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.failed_lines[line_config.id] = entry
        print(
            f"⚠️ [失败记录] 第{line_config.id + 1}/{self.total_lines}句 | 角色: {line_config.role} | "
            f"文本: {text_preview}... | 错误: {error}"
        )

    def persist_failed_lines(self):
        """把当前章节的错误段落记录写入 failed_lines.json

        无错误段落时若日志文件已存在则清理，避免历史脏数据。
        """
        if not self.failed_lines:
            if os.path.exists(self.failed_lines_log_path):
                try:
                    os.remove(self.failed_lines_log_path)
                except Exception:
                    pass
            return

        try:
            payload = {
                "novel_name": self.novel_name,
                "chapter": self.chapter_name,
                "total_lines": self.total_lines,
                "failed_count": len(self.failed_lines),
                "failed_lines": list(self.failed_lines.values()),
            }
            os.makedirs(self.chapter_dir, exist_ok=True)
            with open(self.failed_lines_log_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"💾 失败段落记录已保存: {self.failed_lines_log_path}")
        except Exception as e:
            print(f"⚠️ 保存失败段落记录时出错: {e}")

    def has_failed_lines(self) -> bool:
        """是否记录到失败的段落"""
        return bool(self.failed_lines)

    def summarize_failed_lines(self) -> str:
        """生成失败段落的可读摘要（用于提示用户）"""
        if not self.failed_lines:
            return ""
        sorted_entries = sorted(self.failed_lines.values(), key=lambda x: x["line_id"])
        lines = [
            f"  - 第{e['line_id'] + 1}句 [{e['role']}]: {e['text']} ({e['error']})"
            for e in sorted_entries
        ]
        return "\n".join(lines)

    def _parse_soundscape_layers(self) -> List[SoundscapeLayer]:
        """解析顶层 soundscape 背景音配置"""
        soundscape = self.config.get("soundscape") or {}
        layers = []

        chapter_bed = soundscape.get("chapter_bed")
        if chapter_bed:
            chapter_start_line = int(chapter_bed.get("start_line", 0))
            chapter_end_line = int(chapter_bed.get("end_line", self.config["data"][-1]["id"]))
            layers.append(SoundscapeLayer(
                name=chapter_bed.get("name", "chapter_bed"),
                prompt=chapter_bed.get("prompt", ""),
                start_line=chapter_start_line,
                end_line=chapter_end_line,
                duration=float(chapter_bed.get("duration", self._estimate_soundscape_duration(chapter_start_line, chapter_end_line))),
                volume=chapter_bed.get("volume", "-16%"),
                fade_in=float(chapter_bed.get("fade_in", 3)),
                fade_out=float(chapter_bed.get("fade_out", 3)),
                loop=bool(chapter_bed.get("loop", True)),
                target_dbfs=float(chapter_bed.get("target_dbfs", -34.0)),
                high_pass_hz=int(chapter_bed.get("high_pass_hz", 80)),
                low_pass_hz=int(chapter_bed.get("low_pass_hz", 5500))
            ))

        for scene_layer in soundscape.get("scene_layers", []):
            scene_start_line = int(scene_layer.get("start_line", 0))
            scene_end_line = int(scene_layer.get("end_line", scene_layer.get("start_line", 0)))
            layers.append(SoundscapeLayer(
                name=scene_layer.get("name", "scene_layer"),
                prompt=scene_layer.get("prompt", ""),
                start_line=scene_start_line,
                end_line=scene_end_line,
                duration=float(scene_layer.get("duration", self._estimate_soundscape_duration(scene_start_line, scene_end_line))),
                volume=scene_layer.get("volume", "-17%"),
                fade_in=float(scene_layer.get("fade_in", 2)),
                fade_out=float(scene_layer.get("fade_out", 2)),
                loop=bool(scene_layer.get("loop", True)),
                target_dbfs=float(scene_layer.get("target_dbfs", -34.0)),
                high_pass_hz=int(scene_layer.get("high_pass_hz", 80)),
                low_pass_hz=int(scene_layer.get("low_pass_hz", 5500))
            ))

        return [layer for layer in layers if layer.prompt]

    def _estimate_soundscape_duration(self, start_line: int, end_line: int) -> float:
        """根据段落文字量和语速估算 soundscape 背景音时长，优先贴合当前场景跨度"""
        if not self.config.get("data"):
            return 30.0

        def _parse_speed_multiplier(speed_value: Any) -> float:
            try:
                speed_text = str(speed_value).strip()
                if not speed_text.endswith('%'):
                    return 1.0
                speed_percent = float(speed_text[:-1])
                multiplier = 1.0 + (speed_percent / 100.0)
                return max(0.4, multiplier)
            except Exception:
                return 1.0

        clamped_start = max(0, start_line)
        clamped_end = max(clamped_start, end_line)
        selected_lines = [
            item for item in self.config.get("data", [])
            if clamped_start <= int(item.get("id", -1)) <= clamped_end
        ]
        if not selected_lines:
            return 30.0

        line_count = len(selected_lines)
        estimated_voice_seconds = 0.0
        total_chars = 0

        for item in selected_lines:
            voice_data = (item.get("api") or {}).get("voice", {})
            text = str(voice_data.get("text") or item.get("text", "")).strip()
            char_count = len(text)
            total_chars += char_count

            speed_multiplier = _parse_speed_multiplier(voice_data.get("speed", "0%"))
            base_chars_per_second = 4.6
            estimated_voice_seconds += char_count / (base_chars_per_second * speed_multiplier)

        line_transition_padding = max(2.0, line_count * 0.8)
        estimated_seconds = estimated_voice_seconds + line_transition_padding

        if total_chars <= 60:
            estimated_seconds = min(estimated_seconds, 18.0)
        elif line_count <= 2:
            estimated_seconds = min(estimated_seconds, 28.0)
        elif line_count <= 6:
            estimated_seconds = min(estimated_seconds, 42.0)

        estimated_seconds = max(10.0, estimated_seconds)
        return round(estimated_seconds + 1.5, 2)

    def _soundscape_layer_path(self, layer: SoundscapeLayer) -> str:
        """获取 soundscape 背景音文件路径"""
        safe_name = layer.name.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
        cache_key = json.dumps({
            "prompt": layer.prompt,
            "duration": layer.duration,
            "target_dbfs": layer.target_dbfs,
            "high_pass_hz": layer.high_pass_hz,
            "low_pass_hz": layer.low_pass_hz
        }, ensure_ascii=False, sort_keys=True)
        prompt_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()[:8]
        return os.path.join(self.bgm_dir, f"soundscape_{safe_name}_{layer.start_line}_{layer.end_line}_{prompt_hash}.wav")

    def _prepare_soundscape_layers(self, layers: List[SoundscapeLayer]):
        """预生成 soundscape 背景音层"""
        tasks = []
        for layer in layers:
            output_path = self._soundscape_layer_path(layer)
            if not os.path.exists(output_path):
                tasks.append({
                    "prompt": layer.prompt,
                    "duration": layer.duration,
                    "output_path": output_path
                })

        if tasks:
            print(f"🔄 开始批量生成 {len(tasks)} 个 soundscape 背景音 (引擎: {self.bgm_engine}, max_workers=2)...")
            self._generate_bgm_batch(tasks, max_workers=2)

        for layer in layers:
            output_path = self._soundscape_layer_path(layer)
            if os.path.exists(output_path):
                try:
                    layer_audio = AudioSegment.from_wav(output_path)
                    processed_audio = self._soften_soundscape_audio(layer_audio, layer)
                    processed_audio.export(output_path, format="wav")
                except Exception as e:
                    print(f"⚠️ soundscape 背景音后处理失败: {layer.name}, {e}")

    def _soften_soundscape_audio(self, audio: AudioSegment, layer: SoundscapeLayer) -> AudioSegment:
        """柔化背景音，降低突兀杂音和整体响度"""
        result = audio.set_frame_rate(self.audio_engine.sample_rate).set_channels(self.audio_engine.channels)
        if layer.high_pass_hz > 0:
            try:
                result = result.high_pass_filter(layer.high_pass_hz)
            except (IndexError, Exception):
                pass
        if layer.low_pass_hz > 0:
            try:
                result = result.low_pass_filter(layer.low_pass_hz)
            except (IndexError, Exception):
                pass
        if result.dBFS != float("-inf") and result.dBFS > layer.target_dbfs:
            result = result + (layer.target_dbfs - result.dBFS)
        return result.fade_in(800).fade_out(800)

    def _fit_audio_duration(self, audio: AudioSegment, duration_ms: int, loop: bool = True) -> AudioSegment:
        """循环或裁剪音频到指定时长"""
        if duration_ms <= 0 or len(audio) <= 0:
            return AudioSegment.silent(duration=0, frame_rate=self.audio_engine.sample_rate)
        if len(audio) >= duration_ms:
            return audio[:duration_ms]
        if not loop:
            return audio + AudioSegment.silent(duration=duration_ms - len(audio), frame_rate=audio.frame_rate)
        repeat_count = duration_ms // len(audio)
        remainder = duration_ms % len(audio)
        return audio * repeat_count + audio[:remainder]

    def _apply_soundscape(self, merged_audio: AudioSegment, line_ranges: Dict[int, tuple], layers: List[SoundscapeLayer]) -> AudioSegment:
        """将 soundscape 背景音按行号范围叠加到整章音频"""
        if not layers:
            return merged_audio

        result = merged_audio
        for layer in layers:
            start_ms = line_ranges.get(layer.start_line, (0, 0))[0]
            end_ms = line_ranges.get(layer.end_line, (len(merged_audio), len(merged_audio)))[1]
            if end_ms <= start_ms:
                print(f"⚠️ 跳过无效 soundscape 范围: {layer.name} {layer.start_line}-{layer.end_line}")
                continue

            layer_path = self._soundscape_layer_path(layer)
            if not os.path.exists(layer_path):
                print(f"⚠️ soundscape 背景音不存在，跳过: {layer_path}")
                continue

            duration_ms = end_ms - start_ms
            layer_audio = AudioSegment.from_wav(layer_path)
            layer_audio = self._soften_soundscape_audio(layer_audio, layer)
            layer_audio = self._fit_audio_duration(layer_audio, duration_ms, layer.loop)
            layer_audio = self.audio_engine._adjust_audio_params(
                layer_audio,
                speed="+0%",
                volume=layer.volume,
                pitch="+0Hz"
            )
            if layer.fade_in > 0:
                layer_audio = layer_audio.fade_in(int(layer.fade_in * 1000))
            if layer.fade_out > 0:
                layer_audio = layer_audio.fade_out(int(layer.fade_out * 1000))

            result = result.overlay(layer_audio, position=start_ms)
            print(f"🎼 已叠加 soundscape: {layer.name} ({layer.start_line}-{layer.end_line})")

        return result

    def _parse_line_config(self, line: Dict[str, Any]) -> LineAudioConfig:
        """解析单句配置"""
        role = line["role"]
        
        tts_engine = getattr(self.audio_engine, 'tts_engine', "qwen3-tts")
        
        voice_params_dict = None
        voice_data = line["api"].get("voice", {})

        if tts_engine == "qwen3-tts":
            if isinstance(voice_data, dict):
                voice_params_dict = (voice_data.get("qwen_params") or voice_data).copy()
            elif hasattr(self, 'roles_definition') and role in self.roles_definition:
                role_def = self.roles_definition[role]
                voice_params_dict = (role_def.get('qwen_voice') or role_def.get('voice') or role_def).copy()

        if voice_params_dict is None:
            if isinstance(voice_data, dict) and voice_data:
                voice_params_dict = voice_data.copy()
            elif hasattr(self, 'roles_definition') and role in self.roles_definition:
                role_def = self.roles_definition[role]
                voice_params_dict = (role_def.get('voice') or role_def).copy()
        
        if voice_params_dict and 'text' not in voice_params_dict:
            voice_params_dict['text'] = line.get('text', '')
        
        voice_params = VoiceParams(**voice_params_dict)
        
        bgm_params = None
        if "bgm" in line["api"] and not self.config.get("soundscape"):
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
                    duration=effect.get("duration", 1),
                    process_mode=effect.get("process_mode", "overlay")
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
        text_preview = line_config.voice_params.text[:40].replace('\n', ' ')
        current_index = line_config.id + 1
        print(
            f"\n🎙️ [{self.novel_name} / {self.chapter_name}] 第{current_index}/{self.total_lines}句 | 角色: {line_config.role} | 文本: {text_preview}..."
        )
        
        voice_output_path = os.path.join(self.voice_dir, f"voice_line_{line_config.id}.wav")
        single_output_path = os.path.join(self.mix_dir, f"mixed_line_{line_config.id}.wav")
        generated_new_audio = False
        remixed_audio = False
        
        if os.path.exists(voice_output_path):
            print(
                f"🟢 [{self.novel_name} / {self.chapter_name}] 第{current_index}/{self.total_lines}句 命中 voice 缓存，重新混音: {voice_output_path}"
            )
            remixed_audio = True
            voice_audio = AudioSegment.from_wav(voice_output_path)
        elif os.path.exists(single_output_path):
            print(
                f"🟡 [{self.novel_name} / {self.chapter_name}] 第{current_index}/{self.total_lines}句 未命中 voice，命中 mixed 缓存，直接复用: {single_output_path}"
            )
            return AudioSegment.from_wav(single_output_path)
        else:
            print(
                f"🔴 [{self.novel_name} / {self.chapter_name}] 第{current_index}/{self.total_lines}句 未命中缓存，开始生成 TTS"
            )
            generated_new_audio = True
            voice_audio = self.audio_engine.text_to_speech(line_config.voice_params)
            voice_audio.export(voice_output_path, format="wav")
            if self.persist_intermediate_audio:
                print(f"💾 单句配音已保存: {voice_output_path}")
            else:
                print(f"💾 新生成单句配音已保存: {voice_output_path}")
        
        bgm_audio = None
        effect_audios = []
        bgm_output_path = None
        effect_output_paths = []
        
        bgm_tasks = []
        sfx_tasks = []
        
        if line_config.bgm_params is not None and not self.config.get("soundscape"):
            bgm_duration = len(voice_audio) / 1000.0
            bgm_scene_cn = line_config.bgm_params.scene.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            bgm_output_path = os.path.join(self.bgm_dir, f"bgm_line_{bgm_scene_cn}_{line_config.id}.wav")
            if not os.path.exists(bgm_output_path):
                bgm_tasks.append({
                    "prompt": line_config.bgm_params.scene_en,
                    "duration": bgm_duration,
                    "output_path": bgm_output_path
                })
        
        for i, effect_param in enumerate(line_config.effect_params):
            effect_name = effect_param.name.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            effect_output_path = os.path.join(self.effect_dir, f"effect_line_{effect_name}_{line_config.id}.wav")
            effect_output_paths.append(effect_output_path)
            #屏蔽音效
            if not os.path.exists(effect_output_path):
                # 直接使用AI生成音效
                sfx_tasks.append({
                    "prompt": effect_param.sound_en,
                    "duration": effect_param.duration,
                    "output_path": effect_output_path
                })
        
        if bgm_tasks:
            print(f"🔄 开始批量生成 {len(bgm_tasks)} 个背景音 (引擎: {self.bgm_engine}, max_workers=2)...")
            self._generate_bgm_batch(bgm_tasks, max_workers=2)

        if sfx_tasks:
            print(f"🔄 开始批量生成 {len(sfx_tasks)} 个音效 (引擎: {self.sfx_engine})...")
            self._generate_sfx_batch(sfx_tasks)
        
        if bgm_output_path and os.path.exists(bgm_output_path):
            bgm_audio = AudioSegment.from_wav(bgm_output_path)
            if line_config.bgm_params.volume:
                bgm_audio = self.audio_engine._adjust_audio_params(
                    bgm_audio,
                    speed="+0%",
                    volume=line_config.bgm_params.volume,
                    pitch=line_config.bgm_params.pitch
                )
            if line_config.bgm_params.play_mode == "lower" and line_config.bgm_params.lower_db:
                bgm_audio = bgm_audio - min(line_config.bgm_params.lower_db, 6)
        
        for i, effect_output_path in enumerate(effect_output_paths):
            if os.path.exists(effect_output_path):
                effect_audio = AudioSegment.from_wav(effect_output_path)
                effect_param = line_config.effect_params[i]
                effect_audio = effect_audio[:int(effect_param.duration * 1000)]
                effect_audio = self.audio_engine._adjust_audio_params(
                    effect_audio,
                    speed="+0%",
                    volume=effect_param.volume,
                    pitch=effect_param.pitch
                )
                if effect_audio.dBFS < -22:
                    effect_audio = effect_audio + 4
                effect_audios.append(effect_audio)
        
        mixed_audio = self.audio_engine.mix_audio(
            voice=voice_audio,
            bgm=bgm_audio,
            effects=effect_audios,
            mix_config=line_config.mix_config,
            effect_params=line_config.effect_params
        )
        
        if self.persist_intermediate_audio or generated_new_audio or remixed_audio:
            mixed_audio.export(single_output_path, format="wav")
            if generated_new_audio and not self.persist_intermediate_audio:
                print(f"💾 新生成单句混合音频已保存: {single_output_path}")
            elif remixed_audio and not self.persist_intermediate_audio:
                print(f"💾 重混单句混合音频已保存: {single_output_path}")
            else:
                print(f"💾 单句混合音频已保存: {single_output_path}")
        
        return mixed_audio

    def generate_chapter_audio(self) -> str:
        """生成整章音频"""
        chapter_output_path = os.path.join(
            self.chapter_dir,
            f"{self.chapter_clean_name}.{self.platform_profile.output_format}",
        )
        if os.path.exists(chapter_output_path):
            print(f"✅ 整章音频已存在，跳过生成: {chapter_output_path}")
            return chapter_output_path
        
        if self.tts_engine == "qwen3-tts":
            return self.generate_chapter_audio_serial()
        return self.generate_chapter_audio_parallel()

    def _cleanup_chapter_intermediate_dirs(self):
        """清理整章的中间产物目录（配音、背景音、音效、混音），节省磁盘存储"""
        import shutil
        intermediate_dirs = [
            self.mix_dir,
            self.bgm_dir
        ]
        for d in intermediate_dirs:
            if os.path.isdir(d):
                try:
                    shutil.rmtree(d)
                    print(f"  🗑️ 已清理目录: {os.path.basename(d)}/")
                except Exception as e:
                    print(f"  ⚠️ 清理目录失败 {os.path.basename(d)}/: {e}")

    def generate_chapter_audio_serial(self) -> str:
        """串行生成整章音频（流式写入优化）"""
        print(f"\n🚀 开始串行生成 | 小说: {self.novel_name} | 章节: {self.chapter_name} | 共{self.total_lines}句")
        start_time = time.time()

        line_configs = [self._parse_line_config(line) for line in self.config["data"]]
        soundscape_layers = []  # self._parse_soundscape_layers()  # 已屏蔽背景音解析

        # 创建临时目录存放每句音频
        stream_tmp_dir = os.path.join(self.chapter_dir, "stream_tmp")
        os.makedirs(stream_tmp_dir, exist_ok=True)

        line_ranges = {}
        current_ms = 0
        tmp_files = []

        for line_config in line_configs:
            try:
                print(f"📊 当前进度: 第{line_config.id + 1}/{self.total_lines}句")
                line_audio = self.generate_single_line(line_config)
                
                # 记录时间范围
                start_ms = current_ms
                duration_ms = len(line_audio)
                end_ms = start_ms + duration_ms
                line_ranges[line_config.id] = (start_ms, end_ms)
                current_ms = end_ms
                
                # 流式写入临时文件
                tmp_file = os.path.join(stream_tmp_dir, f"line_{line_config.id}.wav")
                line_audio.export(tmp_file, format="wav")
                tmp_files.append((line_config.id, tmp_file))
                
                # 第一句后添加1秒静音
                if line_config.id == 0:
                    silent_audio = AudioSegment.silent(duration=600, frame_rate=44100)
                    silent_file = os.path.join(stream_tmp_dir, f"silent_0.wav")
                    silent_audio.export(silent_file, format="wav")
                    tmp_files.append((-1, silent_file))
                    current_ms += 600
                
                # 释放内存
                del line_audio
                
            except Exception as e:
                print(f"❌ 处理第 {line_config.id} 句时发生异常: {e}")
                self.record_failed_line(line_config, e)

        # 持久化失败段落记录
        self.persist_failed_lines()

        if self.has_failed_lines():
            failed_count = len(self.failed_lines)
            print(f"\n🛑 检测到 {failed_count}/{self.total_lines} 句合成失败，跳过整章合成")
            print(f"📋 失败段落明细:\n{self.summarize_failed_lines()}")
            self.audio_engine.clean_temp_files()
            return None

        # 合并所有临时文件
        print(f"\n� 合并 {len(tmp_files)} 个音频片段...")
        merged_audio = AudioSegment.silent(duration=0, frame_rate=44100)
        tmp_files.sort(key=lambda x: x[0])
        
        for line_id, tmp_file in tmp_files:
            segment = AudioSegment.from_wav(tmp_file)
            merged_audio += segment
            del segment  # 释放内存

        if soundscape_layers:
            print("\n🎼 开始叠加 soundscape 背景音...")
            self._prepare_soundscape_layers(soundscape_layers)
            merged_audio = self._apply_soundscape(merged_audio, line_ranges, soundscape_layers)

        chapter_output_path = self._export_chapter_audio(merged_audio)

        # 清理临时文件
        print(f"\n🗑️ 清理流式临时文件...")
        for _, tmp_file in tmp_files:
            try:
                os.remove(tmp_file)
            except:
                pass
        try:
            os.rmdir(stream_tmp_dir)
        except:
            pass

        self.audio_engine.clean_temp_files()

        # 清理整章中间产物目录（配音、背景音、音效、混音），节省存储
        self._cleanup_chapter_intermediate_dirs()

        end_time = time.time()
        print(f"\n🎉 整章音频串行生成完成！耗时: {end_time - start_time:.2f} 秒")
        print(f"📂 输出路径: {chapter_output_path}")

        return chapter_output_path

    def generate_chapter_audio_parallel(self) -> str:
        """并行生成整章音频（流式写入优化）"""
        print(f"\n🚀 开始并行生成 | 小说: {self.novel_name} | 章节: {self.chapter_name} | 共{self.total_lines}句")
        start_time = time.time()

        line_configs = [self._parse_line_config(line) for line in self.config["data"]]
        soundscape_layers = []  # self._parse_soundscape_layers()  # 已屏蔽背景音解析

        # 创建临时目录存放每句音频
        stream_tmp_dir = os.path.join(self.chapter_dir, "stream_tmp")
        os.makedirs(stream_tmp_dir, exist_ok=True)

        tmp_files = []
        total_lines = len(line_configs)
        max_workers = min(3, total_lines)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_line = {
                executor.submit(self.generate_single_line, line_config): line_config
                for line_config in line_configs
            }
            for index, future in enumerate(concurrent.futures.as_completed(future_to_line), 1):
                line_config = future_to_line[future]
                print(f"\n📊 [{self.novel_name} / {self.chapter_name}] 已完成 {index}/{total_lines} 句 | 当前返回: 第{line_config.id + 1}句")
                try:
                    line_audio = future.result()
                    # 流式写入临时文件
                    tmp_file = os.path.join(stream_tmp_dir, f"line_{line_config.id}.wav")
                    line_audio.export(tmp_file, format="wav")
                    tmp_files.append((line_config.id, tmp_file))
                    # 释放内存
                    del line_audio
                except Exception as e:
                    print(f"❌ 处理第 {line_config.id} 句时发生异常: {e}")
                    self.record_failed_line(line_config, e)

        # 持久化失败段落记录
        self.persist_failed_lines()

        if self.has_failed_lines():
            failed_count = len(self.failed_lines)
            print(f"\n🛑 检测到 {failed_count}/{self.total_lines} 句合成失败，跳过整章合成")
            print(f"📋 失败段落明细:\n{self.summarize_failed_lines()}")
            self.audio_engine.clean_temp_files()
            return None

        # 合并所有临时文件
        print(f"\n📦 合并 {len(tmp_files)} 个音频片段...")
        tmp_files.sort(key=lambda x: x[0])
        
        merged_audio = AudioSegment.silent(duration=0, frame_rate=44100)
        line_ranges = {}
        current_ms = 0
        
        for line_id, tmp_file in tmp_files:
            segment = AudioSegment.from_wav(tmp_file)
            start_ms = current_ms
            duration_ms = len(segment)
            end_ms = start_ms + duration_ms
            line_ranges[line_id] = (start_ms, end_ms)
            current_ms = end_ms
            
            merged_audio += segment
            
            # 第一句后添加1秒静音
            if line_id == 0:
                silent_audio = AudioSegment.silent(duration=600, frame_rate=44100)
                merged_audio += silent_audio
                current_ms += 600
                del silent_audio
            
            del segment  # 释放内存

        if soundscape_layers:
            print("\n🎼 开始叠加 soundscape 背景音...")
            self._prepare_soundscape_layers(soundscape_layers)
            merged_audio = self._apply_soundscape(merged_audio, line_ranges, soundscape_layers)

        chapter_output_path = self._export_chapter_audio(merged_audio)

        # 清理临时文件
        print(f"\n🗑️ 清理流式临时文件...")
        for _, tmp_file in tmp_files:
            try:
                os.remove(tmp_file)
            except:
                pass
        try:
            os.rmdir(stream_tmp_dir)
        except:
            pass

        self.audio_engine.clean_temp_files()

        # 清理整章中间产物目录（配音、背景音、音效、混音），节省存储
        self._cleanup_chapter_intermediate_dirs()

        end_time = time.time()
        print(f"\n🎉 整章音频并行生成完成！耗时: {end_time - start_time:.2f} 秒")
        print(f"📂 输出路径: {chapter_output_path}")

        return chapter_output_path


# ======================== 小说音频合成器 ========================
class NovelAudioSynthesizer:
    """小说音频合成器，用于生成单个或多个小说章节的完整音频"""
    
    def __init__(self, script_dir: str = None, output_dir: str = None,
                 tts_engine: str = "qwen3-tts", qwen_model_path: str = None,
                 sfx_engine: str = "woosh", bgm_engine: str = "stable-audio-3",
                 persist_intermediate_audio: bool = False,
                 platform: str = "default"):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.script_dir = script_dir or os.path.join(self.base_dir, "../小说剧本")
        self.output_dir = output_dir or os.path.join(self.base_dir, "../../output")
        self.tts_engine = tts_engine
        self.qwen_model_path = qwen_model_path if qwen_model_path else \
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
        self.sfx_engine = sfx_engine
        self.bgm_engine = bgm_engine
        self.persist_intermediate_audio = persist_intermediate_audio
        self.platform = platform
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("=== Novel Audio Synthesizer 初始化完成 ===")
        print(f"📁 剧本目录: {self.script_dir}")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"🔊 音效引擎: {self.sfx_engine}")
        print(f"🎼 背景音引擎: {self.bgm_engine}")
        print(f"📺 输出平台: {self.platform}")

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
        print(f"\n=== 开始处理章节文件: {json_file} ===")
        
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            chapter_name = config["chapter"]
            chapter_clean_name = chapter_name.replace("\n", "").replace(" ", "_").replace(":", "-")
            
            chapter_dir = os.path.join(self.output_dir, os.path.basename(os.path.dirname(json_file)), chapter_clean_name)
            output_ext = get_platform_profile(self.platform).output_format
            chapter_output_path = os.path.join(chapter_dir, f"{chapter_clean_name}.{output_ext}")
            
            if os.path.exists(chapter_output_path):
                print(f"✅ 整章音频已存在，跳过生成: {chapter_output_path}")
                return chapter_output_path
        except Exception as e:
            print(f"❌ 检查整章音频时发生错误: {e}")
        
        generator = AudioGenerator(
            json_path=json_file,
            output_dir=self.output_dir,
            tts_engine=self.tts_engine,
            qwen_model_path=self.qwen_model_path,
            sfx_engine=self.sfx_engine,
            bgm_engine=self.bgm_engine,
            persist_intermediate_audio=self.persist_intermediate_audio,
            platform=self.platform,
        )
        
        return generator.generate_chapter_audio()

    def _extract_chapter_number(self, file_name: str) -> int:
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
    
    def _get_pinyin_key(self, text: str) -> str:
        """获取文本的拼音排序键（通用中文拼音排序）"""
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
    
    def _check_memory_usage(self) -> float:
        """检查系统内存使用情况
        
        Returns:
            可用内存百分比 (0-100)
        """
        try:
            memory = psutil.virtual_memory()
            available_percent = (memory.available / memory.total) * 100
            return available_percent
        except Exception as e:
            print(f"⚠️ 获取内存信息失败: {e}")
            return 100.0
    
    def _garbage_collect(self):
        """执行垃圾回收，释放内存"""
        print("\n🗑️ 内存不足，执行垃圾回收...")
        
        gc.collect()
        
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                print("  🧹 已清理 CUDA 缓存")
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                torch.mps.empty_cache()
                print("  🧹 已清理 MPS 缓存")
        except Exception:
            pass
        
        gc.collect()
        
        memory = psutil.virtual_memory()
        available_percent = (memory.available / memory.total) * 100
        print(f"  ✅ 回收后可用内存: {available_percent:.1f}%")
    
    def process_all_novels(self, sort_mode: str = "pinyin") -> List[str]:
        """处理所有小说章节（按指定方式排序）
        
        Args:
            sort_mode: 排序模式: pinyin(拼音) | chapter(章节号) | name(文件名)
        """
        print(f"\n=== 处理所有小说章节 (排序模式: {sort_mode}) ===")
        
        output_paths = []
        
        for novel_name in os.listdir(self.script_dir):
            novel_dir = os.path.join(self.script_dir, novel_name)
            if not os.path.isdir(novel_dir):
                continue
            
            print(f"\n📖 处理小说: {novel_name}")
            
            json_files = []
            for json_file in os.listdir(novel_dir):
                if json_file.endswith(".json"):
                    json_files.append(json_file)
            
            if sort_mode == "chapter":
                json_files.sort(key=lambda x: self._extract_chapter_number(x))
            elif sort_mode == "pinyin":
                json_files.sort(key=lambda x: self._get_pinyin_key(x))
            else:
                json_files.sort()
            
            for json_file in json_files:
                json_path = os.path.join(novel_dir, json_file)
                output_path = self.process_novel(json_path)
                output_paths.append(output_path)
                
                available_percent = self._check_memory_usage()
                print(f"\n📊 当前可用内存: {available_percent:.1f}%")
                
                if available_percent < 10.0:
                    self._garbage_collect()
        
        return output_paths

    def run(self, json_file: str = None, sort_mode: str = "pinyin") -> List[str]:
        """运行小说音频合成器"""
        if not self.check_environment():
            return []
        
        if json_file:
            output_path = self.process_novel(json_file)
            output_paths = [output_path] if output_path else []
        else:
            output_paths = self.process_all_novels(sort_mode=sort_mode)
        
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
    parser.add_argument("--tts-engine", type=str, default="qwen3-tts", help="TTS引擎类型: qwen3-tts")
    parser.add_argument("--sfx-engine", type=str, default="woosh",
                        help="音效生成引擎: woosh | stable-audio-3 (默认: woosh)")
    parser.add_argument("--bgm-engine", type=str, default="stable-audio-3",
                        help="背景音生成引擎: stable-audio-3 | woosh (默认: stable-audio-3)")
    parser.add_argument("--qwen-model-path", type=str, default="Qwen/Qwen3-TTS-12Hz-1.7B-Base", 
                        help="Qwen TTS模型路径")
    parser.add_argument("--persist-intermediate-audio", action="store_true",
                        help="保留单句配音/混音等中间音频文件，默认尽量减少落盘")
    parser.add_argument("--platform", type=str, default="ximalaya",
                        help="输出平台配置，如 default | ximalaya")
    parser.add_argument("--sort-mode", type=str, default="pinyin",
                        help="排序模式: pinyin(拼音排序，默认) | chapter(章节号排序) | name(文件名排序)")
    
    args = parser.parse_args()
    
    synthesizer = NovelAudioSynthesizer(
        script_dir=args.script_dir,
        output_dir=args.output_dir,
        tts_engine=args.tts_engine,
        qwen_model_path=args.qwen_model_path,
        sfx_engine=args.sfx_engine,
        bgm_engine=args.bgm_engine,
        persist_intermediate_audio=args.persist_intermediate_audio,
        platform=args.platform,
    )
    
    if args.json_path:
        synthesizer.run(json_file=args.json_path, sort_mode=args.sort_mode)
    else:
        synthesizer.run(sort_mode=args.sort_mode)