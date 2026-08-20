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
# ── 将所有 HF 模型统一指向项目 models/ 目录，离线运行，不依赖系统缓存 ──
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
os.environ['HF_HOME'] = os.path.join(_project_root, "models")
os.environ['HUGGINGFACE_HUB_CACHE'] = os.path.join(_project_root, "models", "hub")
os.environ['HUGGINGFACE_HUB_DISABLE_REPO_ID_VALIDATION'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
del _project_root

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
import math
import threading
import warnings
import gc
import psutil
from pathlib import Path

from check_audio_quality import check_audio_segment

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

# ======================== 全局常量配置 ========================
# 标题播报（片头片尾、chunk标题）的固定配音角色
TITLE_VOICE_ROLE = "云紫绡"


def sanitize_chapter_dir_name(json_path: str) -> str:
    """由剧本 JSON 文件名推导章节输出目录/音频文件名，保证与剧本名一致

    例如 蜀山剑侠传第2回-舞长剑.json -> 蜀山剑侠传第2回-舞长剑
    兼容历史上误命名的 xxx.json.json / xxx..json
    """
    stem = os.path.basename(json_path)
    while stem.lower().endswith(".json"):
        stem = stem[:-5]
    stem = stem.strip().rstrip(".")
    return stem.replace("\n", "").replace(" ", "_").replace(":", "-").replace("/", "_")


# ── macOS malloc zone pressure relief ──
# Python 释放大块内存后，macOS 的 malloc zone 不会主动归还给 OS，
# 导致 RSS / physical footprint 虚高。调用此函数强制归还已释放页面。
def _release_malloc_memory():
    """强制 Python 将已释放的内存归还操作系统（macOS）"""
    try:
        import ctypes
        import ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        if hasattr(libc, "malloc_zone_pressure_relief"):
            libc.malloc_zone_pressure_relief(0, 0)
    except Exception:
        pass  # 非 macOS 或调用失败则静默跳过

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
    tts_mode: str = "voice_design"  # "clone" 克隆音频 | "voice_design" 文字描述造音色
    voice_design_prompt: Optional[str] = None  # VoiceDesign 音色描述提示词（可为空，自动从配音表查找）

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
    trigger_keyword: str = ""        # 音效对应的文本关键字（2~6字），用于精确对齐
    trigger_offset: float = 0.0      # 相对关键字的偏移秒数，负数=提前触发

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
        #intro_template="欢迎收听《{novel_name}》",
        intro_template="",
        outro_template="本集播讲完毕，请订阅专辑，下集精彩继续。",
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
                 target_voice_dbfs: Optional[float] = None,
                 enable_transcribe_check: bool = False, tts_mode: str = "voice_design",
                 stability_prefix: str = ""):
        self.temp_dir = temp_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_format = "wav"
        self.tts_engine = tts_engine
        self.stability_prefix = stability_prefix  # TTS 合成起始稳定化前缀文本，空字符串表示禁用

        # 自动选模型：VoiceDesign 模式且未显式指定路径 → 使用 VoiceDesign 模型
        if qwen_model_path:
            self.qwen_model_path = qwen_model_path
        elif tts_mode == "voice_design":
            self.qwen_model_path = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
            print(f"[AudioEngine] VoiceDesign 模式，模型: {self.qwen_model_path}")
        else:
            self.qwen_model_path = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
        self.fish_api_url = fish_api_url.rstrip("/") if fish_api_url else "http://localhost:8080"
        self.target_voice_dbfs = target_voice_dbfs
        self.enable_transcribe_check = enable_transcribe_check  # TTS质检 + 音效精确定位总开关
        self.qwen_tts_model = None
        self._voice_clone_prompt_cache = {}  # 进程内缓存，避免当前运行重复编码参考音频（上限 32 条）
        self._voice_clone_prompt_cache_max_size = 32  # 限制缓存条数，防止内存膨胀
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.clone_audio_dir = os.path.join(project_root, "clone-audio")
        self.voice_prompt_cache_dir = os.path.join(self.clone_audio_dir, ".qwen_prompt_cache")
        
        # ── VoiceDesign 角色配音表 ──
        self._voice_design_table = None  # lazy-loaded JSON 配音表
        self._voice_design_table_path = os.path.join(
            project_root, "novel_tool", "character_voice_tables", "蜀山剑侠传角色配音表.json"
        )
        self._voice_table_missing = set()  # VoiceDesign 模式下配音表缺失的角色名，供上层记录
        self._quality_warnings = []  # TTS 质量异常记录
        self._vd_prefix_cache = {}  # VoiceDesign 起始前缀长度缓存，key=full_instruct → (sample_count, sr)，上限 64 条

        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.voice_prompt_cache_dir, exist_ok=True)

        if self.tts_engine == "qwen3-tts":
            self._init_qwen_tts_model()
        elif self.tts_engine == "fish-speech":
            print("[TTSEngine] 使用 Fish Speech API 引擎，地址: " + self.fish_api_url)

    def release(self):
        """释放 AudioEngine 持有的所有资源（TTS 模型、缓存等），防止跨章节内存泄漏"""
        print("[TTSEngine] 🔓 释放 AudioEngine 资源...")
        if self.qwen_tts_model is not None:
            del self.qwen_tts_model
            self.qwen_tts_model = None
        self._voice_clone_prompt_cache.clear()
        self._vd_prefix_cache.clear()
        self._voice_table_missing.clear()
        self._quality_warnings.clear()
        import gc as _gc
        _gc.collect()
        try:
            import torch as _t
            if hasattr(_t.backends, 'mps') and _t.backends.mps.is_available():
                _t.mps.empty_cache()
            elif _t.cuda.is_available():
                _t.cuda.empty_cache()
        except Exception:
            pass
        _gc.collect()
        _release_malloc_memory()  # macOS: 将 Python 已释放的内存归还系统
        print("[TTSEngine] ✅ AudioEngine 资源已释放")

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

            # 识别模型类型并标记
            if "VoiceDesign" in model_path:
                mode_tag = "🎤 VoiceDesign 文字造音色"
            elif "CustomVoice" in model_path:
                mode_tag = "🎙 CustomVoice 预设音色"
            else:
                mode_tag = "🎙 克隆音频 (Base)"

            short_name = model_path.split("/")[-1] if "/" in model_path else model_path
            print(f"[TTSEngine] 模型: {short_name}  |  模式: {mode_tag}")
            
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

    def _load_voice_design_table(self) -> dict:
        """加载角色配音表 JSON，供 VoiceDesign 模式查找角色 Prompt"""
        if self._voice_design_table is not None:
            return self._voice_design_table
        try:
            if os.path.exists(self._voice_design_table_path):
                with open(self._voice_design_table_path, "r", encoding="utf-8") as f:
                    self._voice_design_table = json.load(f)
                total = self._voice_design_table.get("统计", {}).get("总计", 0)
                print(f"[TTSEngine] 已加载角色配音表: {total} 个角色")
            else:
                print(f"[TTSEngine] ⚠️ 角色配音表不存在: {self._voice_design_table_path}")
                self._voice_design_table = {}
        except Exception as e:
            print(f"[TTSEngine] ⚠️ 加载角色配音表失败: {e}")
            self._voice_design_table = {}
        return self._voice_design_table

    def _lookup_voice_name(self, role_name: str) -> Optional[str]:
        """根据角色名在配音表中查找配音名（用于 clone 模式的参考音频文件名匹配）"""
        # 特殊角色：标题播报、平台片头、平台片尾 使用固定标题配音角色
        if role_name in ("标题播报", "平台片头", "平台片尾"):
            print(f"[TTSEngine] 角色「{role_name}」使用固定标题配音 -> 「{TITLE_VOICE_ROLE}」")
            return TITLE_VOICE_ROLE

        entry = self._lookup_character_entry(role_name)
        if entry:
            voice_name = entry.get("配音名", "")
            if voice_name:
                print(f"[TTSEngine] 角色「{role_name}」clone 配音名 -> 「{voice_name}」")
                return voice_name
        return None

    def _lookup_character_entry(self, role_name: str) -> Optional[dict]:
        """根据角色名在配音表中查找完整角色条目"""
        table = self._load_voice_design_table()
        levels = ["旁白", "主要角色", "重要角色", "次要角色", "临时角色"]
        for level in levels:
            for c in table.get(level, []):
                if c.get("角色名") == role_name:
                    print(f"[TTSEngine] 角色「{role_name}」匹配配音表 (from {level})")
                    return c
        # 模糊匹配
        for level in levels:
            for c in table.get(level, []):
                if role_name in c.get("角色名", ""):
                    print(f"[TTSEngine] 角色「{role_name}」模糊匹配配音表「{c.get('角色名')}」(from {level})")
                    return c
        return None

    def _resolve_voice_design_prompt(self, role_name: str, explicit_prompt: Optional[str] = None) -> str:
        """统一解析 VoiceDesign Prompt，逐级回退，只查一次配音表：
        1. 调用方显式传入的 prompt
        2. 配音表中的 VoiceDesign_Prompt 字段
        3. 配音表中的年龄+性别+性格构造
        4. 角色名兜底 / 不在表中则抛异常
        """
        if explicit_prompt:
            return explicit_prompt.strip()

        prompt = None
        entry = self._lookup_character_entry(role_name)
        if entry is not None:
            prompt = entry.get("VoiceDesign_Prompt", "")

        if not prompt:
            if entry is not None:
                age = entry.get("年龄", "")
                gender = entry.get("性别", "")
                persona = entry.get("性格", "")
                parts = []
                if age:
                    parts.append(age)
                if gender:
                    parts.append(f"{gender}声")
                if persona and persona != "自动分配":
                    parts.append(persona)
                if parts:
                    prompt = "，".join(parts) + "，语速中等，声音清晰自然"
                    print(f"[TTSEngine] 从角色属性构造 VoiceDesign Prompt: {prompt}")
                    return prompt
                # 角色在表中但没有有效语音属性
                print(f"[TTSEngine] ⚠️ 角色「{role_name}」在配音表中但无有效语音属性，使用兜底 Prompt")
                self._voice_table_missing.add(role_name)
                return f"{role_name}角色声音"
            # 角色完全不在配音表中 → 抛异常，跳过该句合成
            print(f"[TTSEngine] ⚠️ 角色「{role_name}」不在配音表中，跳过该句合成")
            raise RuntimeError(f"missing_from_voice_table: 角色「{role_name}」不在配音表中")

        return prompt

    def get_voice_table_missing(self) -> list:
        """返回并清空 VoiceDesign 模式下配音表缺失的角色列表"""
        missing = sorted(self._voice_table_missing)
        self._voice_table_missing.clear()
        return missing

    def get_quality_warnings(self) -> list:
        """返回并清空 TTS 质量异常记录"""
        warnings = self._quality_warnings[:]
        self._quality_warnings.clear()
        return warnings

    @staticmethod
    def _strip_silence(audio: AudioSegment, threshold_db: float = -40, min_silence_ms: int = 400) -> AudioSegment:
        """去除首尾静音（pydub 原生方法，超轻量）"""
        try:
            trimmed = audio.strip_silence(silence_thresh=threshold_db, padding=50, min_silence_len=min_silence_ms)
            if len(trimmed) > 0:
                return trimmed
        except Exception:
            pass
        return audio

    @staticmethod
    def _split_qwen_text(text: str, max_chunk_length: int = 380) -> List[str]:
        """统一语义断句：Qwen TTS 克隆模式和 VoiceDesign 模式共用"""
        hard_split_chars = "。！？；!?;"
        soft_split_chars = "，、：,:"
        preferred_soft_tokens = ["但是", "不过", "然后", "于是", "所以", "只是", "而且", "因为", "如果", "虽然", "然而", "并且", "同时", "并非", "只是说", "况且", "此外"]
        protected_prefix_tokens = ["就像", "这也是", "比如", "例如", "即便", "哪怕", "如果", "虽然", "但是", "不过", "而且", "并且", "于是", "所以", "只是", "然而", "同时", "却", "却会", "也会", "都", "就", "便", "还会", "仍然"]
        protected_suffix_tokens = ["来说", "的话", "而言", "之一", "那边", "位置", "原因"]
        _max_chunk = max_chunk_length
        min_split_length = max(80, _max_chunk // 3)
        target_chunk_length = _max_chunk * 3 // 4
        absolute_max_chunk_length = _max_chunk + 120
        min_tail_merge_length = 24

        stripped_text = text.strip()
        if len(stripped_text) <= _max_chunk:
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

            if current_length >= _max_chunk:
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
        for index, segment in enumerate(normalized_segments, start=1):
            print(f"[TTSEngine]   分段{index}/{len(normalized_segments)} ({len(segment)}字): {segment[:50]}...")
        return normalized_segments

    @staticmethod
    def _check_segment_quality(chunk: 'np.ndarray', sr: int, seg_text: str) -> 'tuple':
        """逐段质检，使用 check_audio_quality 统一逻辑。
        Returns: (is_good: bool, reason: str)
        """
        import numpy as np
        from pydub import AudioSegment

        # numpy → AudioSegment
        if chunk.dtype == np.float32 or chunk.dtype == np.float64:
            chunk_int16 = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16)
        else:
            chunk_int16 = chunk.astype(np.int16)
        audio = AudioSegment(
            chunk_int16.tobytes(),
            frame_rate=sr,
            sample_width=2,
            channels=1,
        )

        issues = check_audio_segment(audio, text_len=len(seg_text))
        if issues:
            return False, "; ".join(issues)
        return True, ""

    def _detect_and_trim_prefix_by_asr(self, chunk: 'np.ndarray', sr: int, prefix_text: str = "话说，") -> 'np.ndarray':
        """使用 asr_prefix_detector 模块检测并裁剪前缀。

        Args:
            chunk: 音频数据 (numpy array)
            sr: 采样率
            prefix_text: 要检测的前缀文本，默认 "话说，"

        Returns:
            裁剪后的音频数据
        """
        try:
            from asr_prefix_detector import detect_and_trim_prefix
            project_root = Path(__file__).resolve().parent.parent.parent
            print(f"[AudioProcessing] 🔍 ASR检测前缀 '{prefix_text}'，音频长度: {len(chunk)/sr:.2f}s")
            result = detect_and_trim_prefix(
                chunk, sr, prefix_text=prefix_text, project_root=project_root, search_seconds=3.0
            )
            if len(result) < len(chunk):
                print(f"[AudioProcessing] ✓ 前缀已裁剪，原长度: {len(chunk)}, 新长度: {len(result)}")
            else:
                print(f"[AudioProcessing] ⚠ 前缀未找到或裁剪失败")
            return result
        except Exception as e:
            print(f"[AudioProcessing] ✗ ASR裁剪失败: {e}")
            import traceback
            traceback.print_exc()
            return chunk

    def text_to_speech(self, params: VoiceParams) -> AudioSegment:
        """文本转语音接口"""
        print(f"\n[TTSEngine] 使用引擎: {self.tts_engine} (模式: {params.tts_mode})")
        print(f"[TTSEngine] 生成[{params.role}]语音 ({len(params.text)}字): {params.text[:20]}...")
        print(f"  - 音色: {params.role_voice} | 语速: {params.speed} | 音量: {params.volume}")
        
        try:
            start_time = time.time()
            if self.tts_engine == "qwen3-tts":
                if params.tts_mode == "voice_design":
                    audio = self._text_to_speech_qwen_voice_design(params)
                else:
                    audio = self._text_to_speech_qwen(params)
            elif self.tts_engine == "fish-speech":
                audio = self._text_to_speech_fish(params)
            else:
                raise ValueError(f"未知的TTS引擎: {self.tts_engine}")
            elapsed_time = time.time() - start_time
            print(f"[TTSEngine] 语音生成完成，耗时: {elapsed_time:.2f} 秒")
            audio = self._adjust_audio_params(audio, params.speed, params.volume, params.pitch)
            audio = self._strip_silence(audio)  # 统一去静音

            # 快速质检：仅未拆分的短句做，长句已在各段生成时逐段质检过
            _split_threshold = 280 if params.tts_mode == "voice_design" else 380
            _was_split = len(params.text.strip()) > _split_threshold

            if not _was_split:
                issues = check_audio_segment(audio, text_len=len(params.text))
                for issue in issues:
                    self._quality_warnings.append({"role": params.role, "text": params.text[:50], "issue": issue})
                    print(f"[TTSEngine] ⚠️ {issue}")

            return audio
        except Exception as e:
            print(f"[TTSEngine] 语音生成失败: {e}")
            raise

    def _switch_qwen_model(self, target_path: str, reason: str = ""):
        """切换 Qwen TTS 模型，强制释放旧模型 MPS/CUDA 显存"""
        import gc as _gc
        if self.qwen_tts_model is not None:
            del self.qwen_tts_model
            self.qwen_tts_model = None
        _gc.collect()
        import torch as _t
        if _t.backends.mps.is_available():
            _t.mps.empty_cache()
        elif _t.cuda.is_available():
            _t.cuda.empty_cache()
        if reason:
            print(f"[TTSEngine] 🔄 {reason} → 切换模型...")
        self.qwen_model_path = target_path
        self._init_qwen_tts_model()

    def _text_to_speech_qwen(self, params: VoiceParams) -> AudioSegment:
        """使用Qwen3-TTS引擎生成语音（clone 模式）"""
        # 旁白 clone 模式需 Base 模型，如果当前是 VoiceDesign → 强制切换
        if self.qwen_tts_model is not None:
            model_type = getattr(self.qwen_tts_model.model, 'tts_model_type', 'unknown')
            if model_type == 'voice_design':
                self._switch_qwen_model("Qwen/Qwen3-TTS-12Hz-1.7B-Base", "clone 模式需要 Base 模型")

        if self.qwen_tts_model is None:
            self._init_qwen_tts_model()
        
        import torch
        
        voice_name = self._lookup_voice_name(params.role)
        if not voice_name:
            raise RuntimeError(f"missing_from_voice_table: 角色「{params.role}」在配音表中未找到 clone 配音名，该句将被跳过")
        qwen_speaker = voice_name
        instruct = params.instruct.strip() if params.instruct else ""
        
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
                    # LRU 淘汰
                    while len(self._voice_clone_prompt_cache) > self._voice_clone_prompt_cache_max_size:
                        oldest_key = next(iter(self._voice_clone_prompt_cache))
                        del self._voice_clone_prompt_cache[oldest_key]
                    return prompt_dict
                except Exception as e:
                    print(f"[TTSEngine] 读取voice_clone_prompt缓存失败，将重新生成: {e}")

            prompt_items = self.qwen_tts_model.create_voice_clone_prompt(
                ref_audio=ref_audio_path,
                ref_text="",
                x_vector_only_mode=x_vector_only_mode,
            )
            prompt_dict = self.qwen_tts_model._prompt_items_to_voice_clone_prompt(prompt_items)
            # LRU 淘汰：缓存超出上限时移除最早条目，防止内存膨胀
            while len(self._voice_clone_prompt_cache) >= self._voice_clone_prompt_cache_max_size:
                oldest_key = next(iter(self._voice_clone_prompt_cache))
                del self._voice_clone_prompt_cache[oldest_key]
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
            """克隆模式下文本切分，复用统一断句逻辑"""
            return self._split_qwen_text(text)

        def _generate_voice_chunk(processed_text: str, ref_audio, x_vector_only_mode=True):
            text_len = len(processed_text)
            max_tokens = min(2048, max(512, text_len * 8))

            result_holder = {}
            exception_holder = {}
            done_flag = threading.Event()

            def _run_generate():
                try:
                    if ref_audio is not None:
                        cached_prompt = _get_cached_prompt(ref_audio, x_vector_only_mode)
                        res = self.qwen_tts_model.generate_voice_clone(
                            text=processed_text,
                            language="chinese",
                            voice_clone_prompt=cached_prompt,
                            style=params.instruct if params.instruct else "",
                            temperature=0.3,
                            top_p=0.85,
                            top_k=20,
                            repetition_penalty=1.05,
                            max_new_tokens=max_tokens
                        )
                    else:
                        res = self.qwen_tts_model.generate_voice_clone(
                            text=processed_text,
                            language="chinese",
                            ref_audio=ref_audio,
                            ref_text="",
                            x_vector_only_mode=x_vector_only_mode,
                            style=params.instruct if params.instruct else "",
                            temperature=0.3,
                            top_p=0.85,
                            top_k=20,
                            repetition_penalty=1.05,
                            max_new_tokens=max_tokens
                        )
                    result_holder["result"] = res
                except Exception as e:
                    exception_holder["error"] = e
                finally:
                    done_flag.set()

            t = threading.Thread(target=_run_generate, daemon=True)
            t.start()
            dots = 0
            dot_interval = 3  # 每 3 秒打印一个点
            while not done_flag.wait(timeout=dot_interval):
                dots += 1
                elapsed = dots * dot_interval
                sys.stdout.write(f"\r[TTSEngine]   生成中 ({text_len}字, 已耗时{elapsed}s)...")
                sys.stdout.flush()
            if dots > 0:
                sys.stdout.write("\n")
                sys.stdout.flush()
            t.join()
            if "error" in exception_holder:
                raise exception_holder["error"]
            return result_holder["result"]

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

            # ── 起始稳定化：每段拼前缀后按前缀实际长度动态裁剪 ──
            max_tokens = 2048

            # 先生成一次前缀，测量真实音频长度
            prefix_sample_count = 0
            prefix_sr = None
            stability_prefix = self.stability_prefix
            need_prefix = (
                stability_prefix
                and text_segments
                and any(len(seg) > 5 for seg in text_segments)
                and not text_segments[0].startswith(stability_prefix)
            )
            if need_prefix:
                try:
                    print(f"[TTSEngine] 生成起始稳定化前缀: '{stability_prefix}'")
                    _prefix_wavs, prefix_sr = _generate_voice_chunk(stability_prefix, ref_audio, x_vector_only_mode)
                    prefix_audio = np.concatenate(_prefix_wavs) if isinstance(_prefix_wavs, list) else _prefix_wavs
                    prefix_sample_count = len(prefix_audio)
                    print(f"[TTSEngine] 前缀音频长度: {prefix_sample_count} samples ({prefix_sample_count/prefix_sr:.2f}s)")
                except Exception as e:
                    print(f"[TTSEngine] ⚠️ 生成稳定化前缀失败，跳过: {e}")
                    prefix_sample_count = 0

            # 按实际前缀音频长度裁剪，保留 5% 安全边距避免削到正文
            # 注意：前缀"话说，"附着在不同正文上时 TTS 合成时长可能略长于独立测量值，
            # 因此安全边距不能太大，否则前缀残留
            safe_trim = int(prefix_sample_count * 1.0) if prefix_sample_count > 0 else 0
            if safe_trim > 0:
                print(f"[TTSEngine] 前缀裁剪量: {safe_trim} samples ({safe_trim/prefix_sr:.2f}s, 实际前缀 {prefix_sample_count/prefix_sr:.2f}s)")

            MAX_CLONE_RETRIES = 3
            t_cumulative = 0.0

            for index, text_segment in enumerate(text_segments, start=1):
                t_seg_start = time.time()
                chunk_audio = None
                sr = None

                # 确定实际合成的文本（是否添加前缀）
                if len(text_segment) <= 5:
                    actual_text = text_segment
                elif stability_prefix:
                    actual_text = stability_prefix + text_segment
                else:
                    actual_text = text_segment

                for attempt in range(1, MAX_CLONE_RETRIES + 1):
                    if attempt > 1:
                        print(f"[TTSEngine]   ⚠️ 分段 {index} 质检异常，重试 {attempt}/{MAX_CLONE_RETRIES}...")

                    if len(text_segments) > 1 and attempt == 1:
                        display_text = text_segment[:24] if not stability_prefix else actual_text[len(stability_prefix):24+len(stability_prefix)]
                        print(f"[TTSEngine] 分段生成 {index}/{len(text_segments)} ({len(text_segment)}字): {display_text}...")
                    wavs, sr = _generate_voice_chunk(actual_text, ref_audio, x_vector_only_mode)
                    chunk_audio = np.concatenate(wavs) if isinstance(wavs, list) else wavs

                    # ── 裁剪前缀（使用 ASR 精确检测）──
                    if stability_prefix and len(text_segment) > 5:
                        chunk_audio = self._detect_and_trim_prefix_by_asr(chunk_audio, sr, stability_prefix)

                    # ── 逐段质检 ──
                    is_good, reason = self._check_segment_quality(chunk_audio, sr, text_segment)
                    if is_good:
                        print(f"[TTSEngine]   ✅ 分段 {index} 质检通过")
                        break

                    if attempt == MAX_CLONE_RETRIES:
                        chunk_max = np.max(np.abs(chunk_audio))
                        chunk_dur = len(chunk_audio) / sr
                        print(f"[TTSEngine]   ⚠️ 分段 {index} 重试 {MAX_CLONE_RETRIES} 次仍异常 ({reason})，保留当前结果 (max={chunk_max:.4f}, dur={chunk_dur:.1f}s)")
                        # ── 保存异常音频到 fatal 目录供人工确认 ──
                        try:
                            fatal_dir = os.path.join(os.path.dirname(os.path.abspath(self.temp_dir)), "fatal_audio")
                            os.makedirs(fatal_dir, exist_ok=True)
                            safe_text = re.sub(r'[\\/:*?"<>|]', '', text_segment[:20])
                            ts = int(time.time() * 1000)
                            fatal_path = os.path.join(
                                fatal_dir,
                                f"{params.role}_{ts}_seg{index}_{safe_text}_max{chunk_max:.3f}_dur{chunk_dur:.1f}s.wav"
                            )
                            fatal_int16 = (np.clip(chunk_audio, -1, 1) * 32767).astype(np.int16)
                            AudioSegment(fatal_int16.tobytes(), frame_rate=sr, sample_width=2, channels=1).export(fatal_path, format="wav")
                            print(f"[TTSEngine]   💾 异常音频已保存: {fatal_path}")
                        except Exception as save_err:
                            print(f"[TTSEngine]   ⚠️ 保存异常音频失败: {save_err}")

                all_wavs.append(chunk_audio)
                sample_rate = sr

                seg_elapsed = time.time() - t_seg_start
                t_cumulative += seg_elapsed
                seg_dur = len(chunk_audio) / sr
                if len(text_segments) > 1:
                    print(f"[TTSEngine]   分段 {index}/{len(text_segments)} 完成 | {len(text_segment)}字 → {seg_dur:.1f}s | 本段 {seg_elapsed:.1f}s | 累计 {t_cumulative:.1f}s")

            if len(all_wavs) == 1:
                result = all_wavs[0]
                return result, sample_rate

            merged_audio = np.concatenate(all_wavs)
            del all_wavs  # 释放分段音频数据，降低峰值内存
            return merged_audio, sample_rate
        
        wavs, sr = None, None

        try:
            print(f"[TTSEngine] 尝试使用克隆语音: {qwen_speaker}")
            ref_audio_path = _find_audio_file(qwen_speaker)

            if not ref_audio_path:
                raise FileNotFoundError(
                    f"找不到克隆音频文件: clone-audio/ 下未找到 '{qwen_speaker}.mp3' 或 '{qwen_speaker}.wav'。"
                    f"已从配音表查找角色「{params.role}」的配音名「{qwen_speaker}」，"
                    f"请确认 clone-audio/ 目录中是否存在对应的音频文件。"
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
        audio = audio.fade_in(50).fade_out(80)  # 去除首尾杂音

        return audio

    def _text_to_speech_qwen_voice_design(self, params: VoiceParams) -> AudioSegment:
        """使用 Qwen3-TTS VoiceDesign 模式（文字描述造音色）生成语音，不需要参考音频"""
        import torch
        # 强制检测：如果当前加载的模型不支持 voice_design，重新加载 VoiceDesign 模型
        if self.qwen_tts_model is not None:
            model_type = getattr(self.qwen_tts_model.model, 'tts_model_type', 'unknown')
            if model_type == 'base':
                self._switch_qwen_model("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "base 模型不支持 VoiceDesign")

        if self.qwen_tts_model is None:
            self._init_qwen_tts_model()

        t_line_start = time.time()

        # 1. 获取 VoiceDesign Prompt（统一逐级回退，只查一次配音表）
        vd_prompt = self._resolve_voice_design_prompt(
            params.role,
            params.voice_design_prompt.strip() if params.voice_design_prompt else None,
        )

        # 2. 拼接剧本语气 instruct
        instruct = params.instruct.strip() if params.instruct else ""
        full_instruct = f"{vd_prompt}，{instruct}"

        print(f"[TTSEngine] VoiceDesign Prompt: {full_instruct}")

        # ── VoiceDesign 生成参数（全局统一）──
        VD_TEMPERATURE = 0.6       # 语音节奏随机性 (0.1~1.5, 低=机械平直/高=飘忽不定)
        VD_SUBTALKER_TEMP = 0.5    # 音色/说话人一致性 (0.1~1.5, 低=同角色音色稳定)
        VD_TOP_P = 0.95            # 核采样截断 (0.5~1.0, 低=保守单调/高=多样但偶发杂音)
        VD_MAX_CHUNK = 350         # 长句分段阈值

        # ── 音色一致性种子：同角色+同 instruct → 相同种子 → 音色稳定 ──
        _role_seed_key = f"{params.role}:{full_instruct}"
        VD_BASE_SEED = int(hashlib.md5(_role_seed_key.encode()).hexdigest()[:8], 16) % (2**31)

        # 3. 文本切分
        cleaned_text = process_polyphone_text(params.text)
        cleaned_text = cleaned_text.replace('\u201c', '').replace('\u201d', '').replace('\u2018', '').replace('\u2019', '')
        text_segments = self._split_qwen_text(cleaned_text, max_chunk_length=VD_MAX_CHUNK)

        # ── 起始稳定化：每段拼前缀后按前缀实际长度动态裁剪 ──
        max_tokens = 1000

        # 先生成一次前缀，测量真实音频长度（按 full_instruct 缓存，同角色/语气只生成一次）
        prefix_sample_count = 0
        prefix_sr = None
        stability_prefix = self.stability_prefix
        need_prefix = (
            stability_prefix
            and text_segments
            and any(len(seg) > 5 for seg in text_segments)
            and not text_segments[0].startswith(stability_prefix)
        )
        if need_prefix:
            cached_prefix = self._vd_prefix_cache.get(full_instruct)
            if cached_prefix is not None:
                prefix_sample_count, prefix_sr = cached_prefix
                print(f"[TTSEngine] 复用前缀长度缓存: {prefix_sample_count} samples ({prefix_sample_count/prefix_sr:.2f}s)")
            else:
                try:
                    print(f"[TTSEngine] 生成起始稳定化前缀: '{stability_prefix}'")
                    torch.manual_seed(VD_BASE_SEED)
                    _prefix_wavs, prefix_sr = self.qwen_tts_model.generate_voice_design(
                        text=stability_prefix, language="Chinese",
                        instruct=full_instruct,
                        max_new_tokens=max_tokens,
                        subtalker_dosample=False, subtalker_temperature=VD_SUBTALKER_TEMP,
                        temperature=VD_TEMPERATURE, top_p=VD_TOP_P, repetition_penalty=1.05,
                    )
                    prefix_audio = np.concatenate(_prefix_wavs) if isinstance(_prefix_wavs, list) else _prefix_wavs
                    prefix_sample_count = len(prefix_audio)
                    self._vd_prefix_cache[full_instruct] = (prefix_sample_count, prefix_sr)
                    # LRU 淘汰：上限 64 条
                    while len(self._vd_prefix_cache) > 64:
                        oldest = next(iter(self._vd_prefix_cache))
                        del self._vd_prefix_cache[oldest]
                    print(f"[TTSEngine] 前缀音频长度: {prefix_sample_count} samples ({prefix_sample_count/prefix_sr:.2f}s)")
                except Exception as e:
                    print(f"[TTSEngine] ⚠️ 生成稳定化前缀失败，跳过: {e}")
                    prefix_sample_count = 0

        # 按实际前缀音频长度裁剪，完全切除前缀
        safe_trim = int(prefix_sample_count * 1.0) if prefix_sample_count > 0 else 0
        if safe_trim > 0:
            print(f"[TTSEngine] 前缀裁剪量: {safe_trim} samples ({safe_trim/prefix_sr:.2f}s, 实际前缀 {prefix_sample_count/prefix_sr:.2f}s)")

        # ── 分段串行生成（逐段质检，异常自动重试）──
        all_wavs = []
        sample_rate = None
        t_cumulative = 0.0
        MAX_RETRIES = 3  # 单段最多重试次数

        for idx, seg in enumerate(text_segments, 1):
            t_seg_start = time.time()

            if len(seg) <= 5:
                actual_text = seg
            elif stability_prefix:
                actual_text = stability_prefix + seg
            else:
                actual_text = seg

            chunk = None
            sr = None

            for attempt in range(1, MAX_RETRIES + 1):
                # 重试时微调参数增加多样性，首次用默认值
                retry_temp = VD_TEMPERATURE + 0.05 * (attempt - 1)
                retry_top_p = min(VD_TOP_P + 0.02 * (attempt - 1), 1.0)

                if attempt > 1:
                    print(f"[TTSEngine]   ⚠️ 分段 {idx} 质检异常，重试 {attempt}/{MAX_RETRIES} (temp={retry_temp:.2f}, top_p={retry_top_p:.2f})...")

                result_holder = {}
                exception_holder = {}
                done_flag = threading.Event()

                def _gen_one():
                    try:
                        # 固定种子：同角色+同 instruct → 同音色；分段/重试微调避免完全相同
                        _seg_seed = VD_BASE_SEED + idx * 100 + attempt
                        torch.manual_seed(_seg_seed)
                        seg_max_tokens = min(2048, max(512, len(actual_text) * 8))
                        res = self.qwen_tts_model.generate_voice_design(
                            text=actual_text, language="Chinese",
                            instruct=full_instruct,
                            max_new_tokens=seg_max_tokens,
                            subtalker_dosample=False, subtalker_temperature=VD_SUBTALKER_TEMP,
                            temperature=retry_temp, top_p=retry_top_p, repetition_penalty=1.05,
                        )
                        result_holder["result"] = res
                    except Exception as ex:
                        exception_holder["error"] = ex
                    finally:
                        done_flag.set()

                t = threading.Thread(target=_gen_one, daemon=True)
                t.start()
                dots, dot_interval = 0, 3
                while not done_flag.wait(timeout=dot_interval):
                    dots += 1
                    sys.stdout.write(f"\r[TTSEngine]   生成中 ({len(actual_text)}字, 已耗时{dots*dot_interval}s)...")
                    sys.stdout.flush()
                if dots > 0:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                t.join()
                if "error" in exception_holder:
                    raise exception_holder["error"]

                wavs_list, sr = result_holder["result"]
                chunk = np.concatenate(wavs_list) if isinstance(wavs_list, list) else wavs_list
                # 立即释放 model 返回的原始数组引用，避免与 chunk 同时驻留内存
                del wavs_list
                result_holder.clear()
                del result_holder
                del exception_holder
                # ── 裁剪前缀（使用 ASR 精确检测）──
                if stability_prefix and len(seg) > 5:
                    chunk = self._detect_and_trim_prefix_by_asr(chunk, sr, stability_prefix)

                # ── 逐段质检：静音/时长异常/连续静音检测 ──
                is_good, reason = self._check_segment_quality(chunk, sr, seg)

                if is_good:
                    print(f"[TTSEngine]   ✅ 分段 {idx} 质检通过")
                    # 成功生成后清理 MPS/CUDA 缓存，释放 GPU 内存
                    try:
                        if hasattr(torch, 'mps') and torch.mps.is_available():
                            torch.mps.empty_cache()
                        elif torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except Exception:
                        pass
                    break  # 合格，跳出重试循环

                if attempt == MAX_RETRIES:
                    chunk_max = np.max(np.abs(chunk))
                    chunk_dur = len(chunk) / sr
                    expected_dur_min = max(0.3, len(seg) / 8.0)
                    print(f"[TTSEngine]   ⚠️ 分段 {idx} 重试 {MAX_RETRIES} 次仍异常 (max={chunk_max:.4f}, dur={chunk_dur:.1f}s, 预期≥{expected_dur_min:.1f}s)，保留当前结果")
                    # ── 保存异常音频到 fatal 目录供人工确认 ──
                    try:
                        fatal_dir = os.path.join(os.path.dirname(os.path.abspath(self.temp_dir)), "fatal_audio")
                        os.makedirs(fatal_dir, exist_ok=True)
                        safe_text = re.sub(r'[\\/:*?"<>|]', '', seg[:20])
                        ts = int(time.time() * 1000)
                        fatal_path = os.path.join(
                            fatal_dir,
                            f"{params.role}_{ts}_seg{idx}_{safe_text}_max{chunk_max:.3f}_dur{chunk_dur:.1f}s.wav"
                        )
                        fatal_int16 = (np.clip(chunk, -1, 1) * 32767).astype(np.int16)
                        AudioSegment(fatal_int16.tobytes(), frame_rate=sr, sample_width=2, channels=1).export(fatal_path, format="wav")
                        print(f"[TTSEngine]   💾 异常音频已保存: {fatal_path}")
                    except Exception as save_err:
                        print(f"[TTSEngine]   ⚠️ 保存异常音频失败: {save_err}")
                
                # 每次重试后清理 MPS/CUDA 缓存，避免 GPU 内存累积
                try:
                    if hasattr(torch, 'mps') and torch.mps.is_available():
                        torch.mps.empty_cache()
                    elif torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

            all_wavs.append(chunk)
            sample_rate = sr

            seg_elapsed = time.time() - t_seg_start
            t_cumulative += seg_elapsed
            seg_dur = len(chunk) / sr
            if len(text_segments) > 1:
                print(f"[TTSEngine]   分段 {idx}/{len(text_segments)} 完成 | {len(seg)}字 → {seg_dur:.1f}s | 本段 {seg_elapsed:.1f}s | 累计 {t_cumulative:.1f}s")

            if hasattr(torch, 'mps') and hasattr(torch.mps, 'empty_cache'):
                torch.mps.empty_cache()

        # ── 合并所有分段 ──
        merged = np.concatenate(all_wavs) if len(all_wavs) > 1 else all_wavs[0]
        del all_wavs  # 释放分段音频数据，降低峰值内存
        merged = np.clip(merged, -1, 1)
        max_val = np.max(np.abs(merged))
        if max_val > 0:
            merged = merged / max_val * 0.9

        audio_data_int16 = (merged * 32767).astype(np.int16)
        audio = AudioSegment(
            audio_data_int16.tobytes(),
            frame_rate=sample_rate,
            sample_width=audio_data_int16.dtype.itemsize,
            channels=1
        )
        audio = audio.set_frame_rate(self.sample_rate).set_channels(self.channels)
        if self.target_voice_dbfs is not None and audio.rms > 0:
            audio = audio.apply_gain(self.target_voice_dbfs - audio.dBFS)
        audio = audio.fade_in(50).fade_out(80)
        audio = self._strip_silence(audio)

        # ── 快速质检（仅未拆分的短句）──
        if len(text_segments) <= 1:
            issues = check_audio_segment(audio, text_len=len(params.text))
            for issue in issues:
                print(f"[TTSEngine] ⚠️ {issue}")
            if not issues:
                t_total = time.time() - t_line_start
                dur = len(audio) / 1000.0
                print(f"[TTSEngine] ⏱ 整句完成 | 总耗时 {t_total:.1f}s | 音频 {dur:.1f}s | RTF {t_total/dur:.1f}x" if dur > 0 else f"[TTSEngine] ⏱ 整句完成 | 总耗时 {t_total:.1f}s")
        else:
            t_total = time.time() - t_line_start
            dur = len(audio) / 1000.0
            print(f"[TTSEngine] ⏱ 整句完成 | {len(text_segments)}段合并 | 总耗时 {t_total:.1f}s | 音频 {dur:.1f}s | RTF {t_total/dur:.1f}x" if dur > 0 else f"[TTSEngine] ⏱ 整句完成 | 总耗时 {t_total:.1f}s")
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
        
        voice_name = self._lookup_voice_name(params.role)
        if not voice_name:
            raise RuntimeError(f"missing_from_voice_table: 角色「{params.role}」在配音表中未找到 clone 配音名，该句将被跳过")
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
            segments = self._split_qwen_text(text)
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
                  mix_config: MixConfig, effect_params: List = None, voice_text: str = "",
                  voice_path: str = None) -> AudioSegment:
        """按规则混音
        
        Args:
            voice: 人声音频
            bgm: 背景音
            effects: 音效列表
            mix_config: 混音配置
            effect_params: 音效参数列表（含 trigger_keyword / trigger_offset）
            voice_text: 当前句文本，用于 TTS 质量校验
            voice_path: 配音文件路径，用于 whisper.cpp 精确时间轴定位
        """
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
            
            # ── TTS 质量校验：转录语音与剧本原文对比 ──
            if self.enable_transcribe_check and voice_path and voice_text:
                self._validate_tts_quality(voice_path, voice_text)
            
            # ── whisper.cpp 精确时间轴：为有 trigger_keyword 的音效定位实际时间 ──
            keyword_map = {}
            if self.enable_transcribe_check and voice_path:
                for ep in (effect_params or []):
                    kw = getattr(ep, "trigger_keyword", "")
                    if kw:
                        keyword_map[kw] = getattr(ep, "trigger_offset", 0.0)
                if keyword_map:
                    keyword_map = self._locate_keywords_by_transcription(voice_path, keyword_map)
            
            print(f"[MixEngine] 开始混入 {len(effects)} 个音效...")
            for i, effect in enumerate(effects):
                process_mode = "overlay"
                delay_ms = 0
                if effect_params and i < len(effect_params):
                    ep = effect_params[i]
                    process_mode = getattr(ep, "process_mode", "overlay") or "overlay"
                    keyword = getattr(ep, "trigger_keyword", "")
                    if keyword and keyword in keyword_map:
                        # whisper.cpp 精确定位：关键字实际时间 + offset
                        actual_time_s = keyword_map[keyword]
                        offset_s = getattr(ep, "trigger_offset", 0.0)
                        delay_ms = max(0, int((actual_time_s + offset_s) * 1000))
                        print(f"  🎯 音效{i+1}: 关键字'{keyword}'定位 {delay_ms}ms")
                    elif keyword and voice_text:
                        # 兜底：按加权字符进度等比映射到真实音频时长
                        offset = getattr(ep, "trigger_offset", 0.0)
                        delay_ms = self._estimate_delay_by_keyword(
                            voice_text, keyword, offset, voice_duration_ms=voice_duration
                        )
                        print(f"  📍 音效{i+1}: 文本估算定位 {delay_ms}ms (关键字'{keyword}')")
                    else:
                        delay_ms = max(0, int(ep.trigger_delay * 1000))
                        print(f"  ⏱️ 音效{i+1}: 固定延迟 {delay_ms}ms")

                # 落点越界保护：pydub overlay 对超出末尾的 position 会静默丢弃音效，
                # 这里回拉落点，保证至少 min(音效时长, 1s) 能被听到
                if process_mode != "insert":
                    min_audible = min(len(effect), 1000)
                    max_pos = max(0, len(final_audio) - min_audible)
                    if delay_ms > max_pos:
                        print(f"    ⚠️ 音效{i+1} 落点 {delay_ms}ms 超出音频可用区间({len(final_audio)}ms)，回拉至 {max_pos}ms")
                        delay_ms = max_pos

                if process_mode == "insert":
                    insert_position = min(delay_ms, len(final_audio))
                    prefix_audio = final_audio[:insert_position]
                    suffix_audio = final_audio[insert_position:]
                    final_audio = prefix_audio + effect + suffix_audio
                    print(f"    ✂️ 使用insert模式插入")
                elif delay_ms > 0:
                    final_audio = final_audio.overlay(effect, position=delay_ms)
                    print(f"    🔊 叠加到 {delay_ms}ms 位置")
                else:
                    final_audio = final_audio.overlay(effect)
                    print(f"    🔊 叠加到开头")
            print(f"[MixEngine] ✅ 音效混入完成")
        
        elif mix_config.mode == "voice_only":
            final_audio = voice
        
        else:
            final_audio = voice
        
        pause = AudioSegment.silent(duration=300)
        final_audio = final_audio + pause
        
        return final_audio

    def _estimate_delay_by_keyword(self, text: str, keyword: str, offset: float = 0.0,
                                   voice_duration_ms: int = None) -> int:
        """根据关键字在文本中的位置估算延迟毫秒数（标点加权）。
        
        用于 trigger_keyword 精确对齐的兜底方案（未来接入 TTS 字级时间戳后可替换）。
        
        Args:
            text: 当前片段完整文本
            keyword: 要匹配的关键字
            offset: 相对关键字的偏移秒数（负数=提前）
            voice_duration_ms: 该句配音实际时长；提供时按加权字符进度等比映射，
                               避免固定语速估算在长句尾部严重漂移导致音效落到音频之外
        Returns:
            延迟毫秒数
        """
        idx = text.find(keyword)
        if idx == -1:
            return 0
        prefix = text[:idx + len(keyword)]

        # 标点加权（按 3 字/秒折算成等效字数）：句号类 +1.5，逗号类 +0.9，冒号 +1.2
        def _weighted_chars(s: str) -> float:
            total = float(len(s))
            for ch in s:
                if ch in '。！？!?':
                    total += 1.5
                elif ch in '，,；;':
                    total += 0.9
                elif ch in '：:':
                    total += 1.2
            return total

        if voice_duration_ms and voice_duration_ms > 0:
            total_weight = _weighted_chars(text)
            if total_weight > 0:
                ratio = min(1.0, _weighted_chars(prefix) / total_weight)
                return max(0, int(ratio * voice_duration_ms + offset * 1000))

        # 无音频时长信息时退回固定 3 字/秒估算
        delay_seconds = _weighted_chars(prefix) / 3.0 + offset
        return max(0, int(delay_seconds * 1000))

    # ── whisper.cpp 精确时间轴 + TTS 质量校验 ──

    def _locate_keywords_by_transcription(self, voice_path: str, keyword_map: dict) -> dict:
        """用 whisper.cpp 转写配音音频，返回每个关键字的实际出现时间（秒）。
        
        Args:
            voice_path: 配音 WAV 文件路径
            keyword_map: {keyword: offset} 字典
        Returns:
            {keyword: actual_time_seconds} 或 {} (失败时)
        """
        try:
            from asr_transcribe_cli import find_whisper_cpp, ensure_whisper_cpp_model
            
            whisper_bin = find_whisper_cpp()
            if not whisper_bin:
                print("[MixEngine] ⚠️ whisper.cpp 未安装, 回退到文本估算")
                return {}
            
            model_path = ensure_whisper_cpp_model("small")
            out_base = voice_path.rsplit(".", 1)[0] + "_transcribe"
            
            cmd = [
                str(whisper_bin), "-m", str(model_path),
                "-f", voice_path, "-l", "zh",
                "-oj", "-of", out_base, "-np",
                "-t", str(os.cpu_count() or 4),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                print(f"[MixEngine] ⚠️ whisper.cpp 转写失败, 回退到文本估算")
                return {}
            
            raw_json = Path(out_base + ".json")
            if not raw_json.exists():
                return {}
            
            with open(raw_json, "r", encoding="utf-8") as f:
                raw = json.load(f)
            
            transcription = raw.get("transcription", [])
            results = {}
            
            for seg in transcription:
                seg_text = seg.get("text", "")
                seg_start_s = seg.get("offsets", {}).get("from", 0) / 1000.0
                
                for keyword in keyword_map:
                    if keyword in results:
                        continue
                    idx = seg_text.find(keyword)
                    if idx != -1:
                        # 粗略按字符位置比例估算关键字在片段中的偏移
                        char_ratio = idx / max(len(seg_text), 1)
                        results[keyword] = seg_start_s + char_ratio * 2  # 近似 2s 片段时长
            
            # 清理临时文件
            for ext in (".json", ".srt"):
                tmp = Path(out_base + ext)
                if tmp.exists():
                    tmp.unlink()
            
            return results
        except Exception as e:
            print(f"[MixEngine] ⚠️ whisper.cpp 定位失败: {e}")
            return {}
    
    def _validate_tts_quality(self, voice_path: str, expected_text: str, threshold: float = 0.65):
        """用 whisper.cpp 定时分片转写配音，对每段单独打分并汇总。
        
        长音频（> 3 分钟）自动切成 3 分钟段分别转录+比对，取分段平均相似度。
        输出结构：{summary: {overall_score, segment_count, failed_segments}, segments: [{start, end, text, score}]}
        
        Args:
            voice_path: 配音 WAV 文件路径
            expected_text: 剧本原文
            threshold: 相似度阈值，默认 0.65
        """
        try:
            from asr_transcribe_cli import find_whisper_cpp, ensure_whisper_cpp_model
            
            whisper_bin = find_whisper_cpp()
            if not whisper_bin:
                return
            
            model_path = ensure_whisper_cpp_model("small")
            
            # ── 获取音频时长 ──
            import wave
            try:
                with wave.open(voice_path, 'rb') as wf:
                    total_duration = wf.getnframes() / wf.getframerate()
            except Exception:
                total_duration = 0
            
            # ── 超过 10 分钟跳过检测，写 skipped 结果到 JSON ──
            MAX_CHECK_SEC = 600  # 10 分钟
            if total_duration > MAX_CHECK_SEC:
                report_path = voice_path.rsplit(".", 1)[0] + "_quality_report.json"
                skip_result = {
                    "summary": {
                        "overall_score": -1,
                        "segment_count": 0,
                        "failed_segment_count": 0,
                        "threshold": threshold,
                        "verdict": "skipped",
                        "reason": f"音频 {total_duration:.0f}s > {MAX_CHECK_SEC}s 跳过检测"
                    },
                    "segments": [],
                }
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(skip_result, f, ensure_ascii=False, indent=2)
                print(f"[MixEngine] ⏭️ 音频 {total_duration:.0f}s > {MAX_CHECK_SEC}s, 跳过 TTS 质检")
                return
            
            # ── 分片策略：最长 3 分钟 ──
            SEGMENT_SEC = 180  # 3 分钟
            segment_count = max(1, int(total_duration / SEGMENT_SEC) + (1 if total_duration % SEGMENT_SEC > 10 else 0))
            if segment_count <= 1:
                segment_boundaries = [(0, 0)]
            else:
                step = int(total_duration * 1000 / segment_count)
                segment_boundaries = [(i * step, step) for i in range(segment_count)]
            
            # ── 分段转写 ──
            segment_scores = []
            all_transcribed = ""
            out_base = voice_path.rsplit(".", 1)[0] + "_validate"
            
            for seg_idx, (offset_ms, dur_ms) in enumerate(segment_boundaries):
                seg_output = f"{out_base}_seg{seg_idx}"
                
                # 如果有分段，用 -ot 和 -d 限制区间
                cmd = [
                    str(whisper_bin), "-m", str(model_path),
                    "-f", voice_path, "-l", "zh",
                    "-oj", "-of", seg_output, "-np",
                    "-t", str(os.cpu_count() or 4),
                    "-p", str(os.cpu_count() or 4),
                    "-bs", "1", "-nf", "-sow",
                ]
                if segment_count > 1:
                    cmd.extend(["-ot", str(offset_ms), "-d", str(dur_ms)])
                
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    continue
                
                raw_json = Path(seg_output + ".json")
                if not raw_json.exists():
                    continue
                
                with open(raw_json, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                seg_text = "".join(seg.get("text", "") for seg in raw.get("transcription", []))
                all_transcribed += seg_text
                
                # ── 分段评分：对应区间文本比对 ──
                seg_ratio = len(expected_text) / max(segment_count, 1)
                expected_start = int(seg_idx * seg_ratio)
                expected_end = int((seg_idx + 1) * seg_ratio) if seg_idx < segment_count - 1 else len(expected_text)
                expected_chunk = expected_text[expected_start:expected_end]
                
                chunk_score = self._text_similarity(seg_text, expected_chunk)
                segment_scores.append({
                    "segment": seg_idx,
                    "start_s": offset_ms / 1000.0 if segment_count > 1 else 0,
                    "end_s": (offset_ms + dur_ms) / 1000.0 if segment_count > 1 else total_duration,
                    "score": round(chunk_score, 4),
                    "transcribed_len": len(seg_text),
                    "expected_len": len(expected_chunk),
                })
                
                # 清理分段文件
                for ext in (".json", ".srt"):
                    tmp = Path(seg_output + ext)
                    if tmp.exists():
                        tmp.unlink()
            
            # ── 汇总 ──
            if not segment_scores:
                return
            
            overall_score = sum(s["score"] for s in segment_scores) / len(segment_scores)
            failed_segments = [s for s in segment_scores if s["score"] < threshold]
            
            detail = {
                "summary": {
                    "overall_score": round(overall_score, 4),
                    "segment_count": len(segment_scores),
                    "failed_segment_count": len(failed_segments),
                    "threshold": threshold,
                    "verdict": "pass" if overall_score >= threshold else "fail",
                },
                "segments": segment_scores,
            }
            
            # ── 写入详细报告 ──
            report_path = voice_path.rsplit(".", 1)[0] + "_quality_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(detail, f, ensure_ascii=False, indent=2)
            
            if overall_score < threshold:
                msg = (f"[MixEngine] ⚠️ TTS 质检异常! 总分: {overall_score:.1%} "
                       f"({len(failed_segments)}/{len(segment_scores)} 段不达标)\n"
                       f"  📋 详细报告: {report_path}\n"
                       f"  ⚡ 提示: 可手动重新合成该节、调整 TTS 参数或更换角色音色后重试")
                print(msg)
                self._append_error_log(voice_path, expected_text, all_transcribed, overall_score,
                                       extra={"report": report_path, "detail": detail})
        except Exception as e:
            print(f"[MixEngine] ⚠️ TTS 质检失败: {e}")
    
    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """计算两个文本的相似度（分窗口 n-gram + LCS 综合）。
        
        策略：
        - 短文本 (< 500 字): 直接用 LCS
        - 中长文本 (500~5000 字): 滑动窗口取 n-gram 交集均值
        - 超长文本 (> 5000 字): 等距 10 窗口采样，每窗口 LCS，取中位数
        """
        if not a or not b:
            return 0.0
        # 只保留中文字符和常见标点
        keep = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf，。！？、；：""''（）《》…—\u3000]')
        a_clean = ''.join(keep.findall(a))
        b_clean = ''.join(keep.findall(b))
        if not a_clean or not b_clean:
            return 0.0
        
        la, lb = len(a_clean), len(b_clean)
        
        # ── 策略 1: 短文本直接 LCS ──
        if la <= 500 and lb <= 500:
            return AudioEngine._lcs_ratio(a_clean, b_clean)
        
        # ── 策略 2: 中长文本 n-gram 窗口 ──
        if la <= 5000 and lb <= 5000:
            n = 3  # trigram
            window = 200
            scores = []
            step = max(1, min(la, lb) // 20)  # 至少 20 个采样点
            for start in range(0, min(la, lb) - window, step):
                a_win = a_clean[start:start + window]
                # 在 b 中找最匹配的区间
                best = 0.0
                for b_start in range(0, max(1, lb - window), max(1, window // 2)):
                    b_win = b_clean[b_start:b_start + window]
                    # 快速 n-gram 交集
                    a_grams = {a_win[i:i+n] for i in range(len(a_win) - n + 1)}
                    b_grams = {b_win[i:i+n] for i in range(len(b_win) - n + 1)}
                    if a_grams:
                        score = len(a_grams & b_grams) / len(a_grams)
                        if score > best:
                            best = score
                scores.append(best)
            return sum(scores) / max(len(scores), 1) if scores else 0.0
        
        # ── 策略 3: 超长文本分窗口 LCS ──
        num_windows = 10
        window_size = min(1000, la // num_windows, lb // num_windows)
        if window_size < 50:
            window_size = 2000  # fallback: 全局抽样
        step = max(1, (min(la, lb) - window_size) // num_windows)
        scores = []
        for i in range(num_windows):
            start = i * step
            a_win = a_clean[start:start + window_size]
            # 在 b 中取对应位置和前后偏移找最佳匹配
            b_center = min(start, lb - window_size)
            best = 0.0
            for offset in (0, -200, 200, -500, 500):
                b_start = max(0, min(b_center + offset, lb - window_size))
                b_win = b_clean[b_start:b_start + window_size]
                r = AudioEngine._lcs_ratio(a_win, b_win)
                if r > best:
                    best = r
            scores.append(best)
        
        # 取中位数（对极端窗口鲁棒）
        scores.sort()
        mid = len(scores) // 2
        if len(scores) % 2 == 0:
            return (scores[mid - 1] + scores[mid]) / 2
        return scores[mid]
    
    @staticmethod
    def _lcs_ratio(a: str, b: str) -> float:
        """标准 LCS 比率，短于 2000 字直接算，超过则降采样。"""
        m, n = len(a), len(b)
        if m > n:
            a, b = b, a
            m, n = n, m
        if m == 0:
            return 0.0
        if m > 2000:
            step = max(1, m // 2000)
            a, b = a[::step], b[::step]
            m, n = len(a), len(b)
        prev = [0] * (n + 1)
        for i in range(1, m + 1):
            curr = [0] * (n + 1)
            ca = a[i - 1]
            for j in range(1, n + 1):
                if ca == b[j - 1]:
                    curr[j] = prev[j - 1] + 1
                else:
                    curr[j] = max(prev[j], curr[j - 1])
            prev = curr
        return prev[n] / m
    
    def _append_error_log(self, voice_path: str, expected: str, transcribed: str, similarity: float,
                           extra: dict = None):
        """追加 TTS 异常记录到错误日志文件。"""
        log_path = os.path.join(os.path.dirname(voice_path), "tts_error.log")
        entry = {
            "file": voice_path,
            "expected": expected,
            "transcribed": transcribed,
            "similarity": round(similarity, 4),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if extra:
            entry.update(extra)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[MixEngine] ⚠️ 写入错误日志失败: {e}")
    
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
                 platform: str = "default", tts_mode: str = "voice_design",
                 stability_prefix: str = ""):
        if output_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(base_dir, "../../output")

        self.json_path = json_path
        self.tts_engine = tts_engine
        self.tts_mode = tts_mode  # "clone" | "voice_design"
        self.stability_prefix = stability_prefix
        self.qwen_model_path = qwen_model_path
        self.sfx_engine = sfx_engine
        self.bgm_engine = bgm_engine
        self.persist_intermediate_audio = persist_intermediate_audio
        self.platform_profile = get_platform_profile(platform)
        self.platform_name = self.platform_profile.name
        self._quality_warnings = []  # TTS 质量异常记录
        self._chunk_title_seq = 0   # chunk_title 序号
        self.completed_count = 0    # 已合成句数（含上次续跑已完成）

        # 初始化音效与背景音生成引擎
        self._generate_sfx_batch = get_sfx_engine(self.sfx_engine)
        self._generate_bgm_batch = get_bgm_engine(self.bgm_engine)
        
        self.config = self.load_config()
        self.chapter_name = self.config["chapter"]
        
        self.novel_name = os.path.basename(os.path.dirname(json_path))
        # 章节目录/音频文件名与剧本 JSON 文件名保持一致
        self.chapter_clean_name = sanitize_chapter_dir_name(json_path)
        
        self.output_dir = os.path.join(output_dir, self.novel_name)
        self.chapter_dir = os.path.join(self.output_dir, self.chapter_clean_name)
        self.intro_outro_dir = os.path.join(self.output_dir, "片头片尾")
        
        self.voice_dir = os.path.join(self.chapter_dir, "配音")
        self.bgm_dir = os.path.join(self.chapter_dir, "背景音")
        self.effect_dir = os.path.join(self.chapter_dir, "音效")
        self.mix_dir = os.path.join(self.chapter_dir, "混音")

        os.makedirs(self.intro_outro_dir, exist_ok=True)
        os.makedirs(self.voice_dir, exist_ok=True)
        os.makedirs(self.bgm_dir, exist_ok=True)
        os.makedirs(self.effect_dir, exist_ok=True)
        os.makedirs(self.mix_dir, exist_ok=True)

        # 错误段落追踪：记录本章合成失败的行 {line_id: {role, text, error, timestamp}}
        self.failed_lines: Dict[int, Dict[str, Any]] = {}
        # 已持久化到磁盘的失败记录路径
        self.failed_lines_log_path = os.path.join(self.chapter_dir, "failed_lines.json")
        
        platform_channels = self.platform_profile.channels or 1
        self.audio_engine = AudioEngine(
            temp_dir="./temp_audio",
            sample_rate=self.platform_profile.sample_rate,
            channels=platform_channels,
            tts_engine=self.tts_engine,
            qwen_model_path=self.qwen_model_path,
            target_voice_dbfs=self.platform_profile.target_voice_dbfs,
            tts_mode=self.tts_mode,
            stability_prefix=self.stability_prefix,
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

        # 切分章节时，片头模板里的 chapter_label 置空（标题由 _build_platform_audio 单独追加）
        if getattr(self, '_current_chunk_suffix', ''):
            chapter_label = ""

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
                "旁白",
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

        # 使用全局固定的标题播报角色（片头片尾统一使用 TITLE_VOICE_ROLE）
        platform_role_voice = TITLE_VOICE_ROLE

        if asset_type == "片头":
            voice_params = VoiceParams(
                text=text,
                role="平台片头",
                role_voice=platform_role_voice,
                speed="-8%",
                volume="+0%",
                pitch="+0Hz",
                instruct="",
                tts_mode="clone",  # 片头片尾固定用 clone 保持音色一致
            )
        else:
            voice_params = VoiceParams(
                text=text,
                role="平台片尾",
                role_voice=platform_role_voice,
                speed="-5%",
                volume="+0%",
                pitch="+0Hz",
                instruct="",
                tts_mode="clone",
            )

        # 尝试 clone 模式，失败则 fallback 到 voice_design
        asset_audio = None
        last_error = None
        for attempt_mode in ("clone", "voice_design"):
            try:
                voice_params.tts_mode = attempt_mode
                asset_audio = self.audio_engine.text_to_speech(voice_params)
                break
            except Exception as e:
                last_error = e
                print(f"[PlatformAsset] {asset_type} {attempt_mode} 模式失败: {e}")

        if asset_audio is None:
            print(f"[PlatformAsset] ❌ {asset_type} 生成失败（clone/voice_design 均不可用）: {last_error}")
            return None

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

            # 切分章节时在片头后追加章节标题前缀（切分时 id=0 标题已跳过，所有段均需追加）
            is_first_chunk = getattr(self, '_is_first_chunk', True)
            chunk_suffix = getattr(self, '_current_chunk_suffix', '')
            if chunk_suffix:
                chapter_label = self._chunk_label(chunk_suffix, with_pause=True)
                title_audio = self._generate_chunk_title_audio(chapter_label)
                if title_audio is not None:
                    result = title_audio + AudioSegment.silent(
                        duration=200, frame_rate=self.platform_profile.sample_rate
                    ) + result
                    print(f"  📢 已追加章节标题前缀: '{chapter_label}' ({len(title_audio) / 1000:.1f}s)")

            result = intro_audio + AudioSegment.silent(duration=200, frame_rate=self.platform_profile.sample_rate) + result
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

    def _find_chunk_splits_audio(self, total_duration_ms: int, target_chunk_seconds: int = 480) -> List[int]:
        """按完整音频时长均分切点，返回每段的起始毫秒列表。

        策略：
          1. N = round(total / target)，至少为 1
          2. 切点 = total * k / N（k=0,1,...,N-1），即每段起始毫秒

        Args:
            total_duration_ms: 音频总时长（毫秒）
            target_chunk_seconds: 目标每段时长（秒），默认 480（8 分钟）

        Returns:
            每段起始毫秒列表，如 [0, 480000, 960000]
        """
        target_chunk_ms = target_chunk_seconds * 1000
        total_seconds = total_duration_ms / 1000.0
        N = max(1, round(total_duration_ms / target_chunk_ms))
        print(f"[ChunkSplit] total={total_seconds/60:.1f}min, target={target_chunk_seconds//60}min, N={N}")
        return [int(total_duration_ms * k / N) for k in range(N)]

    @staticmethod
    def _find_role_transition_after(sorted_ids: List[int], start_idx: int,
                                     role_at, max_chunk_ms: int,
                                     total_duration_ms: int, min_tail_ms: int,
                                     line_ranges: Dict[int, tuple],
                                     prev_chunk_start_id: int) -> Optional[int]:
        """从 start_idx 位置向后查找第一个角色切换的 line_id。

        遍历规则：
        1. 优先在目标时长附近找角色切换点（role 与上一行不同）
        2. 如果同一角色独白一直延续到超过 max_chunk_ms，在 max_chunk_ms 处硬切
        3. 确保切完后尾段不低于 min_tail_ms

        Args:
            sorted_ids: 所有 line_id 的有序列表
            start_idx: 开始搜索的索引位置
            role_at: 获取指定 line_id 的 role 的函数
            max_chunk_ms: 最大段长（毫秒），超过后兜底硬切
            total_duration_ms: 总时长
            min_tail_ms: 最小尾段时长
            line_ranges: {line_id: (start_ms, end_ms)}
            prev_chunk_start_id: 当前段起始 line_id

        Returns:
            切分起始 line_id，或 None（找不到合适切点）
        """
        prev_chunk_start_ms = line_ranges[prev_chunk_start_id][0] if prev_chunk_start_id in line_ranges else 0

        best_by_role = None   # 找到的第一个角色切换点
        fallback_by_max = None  # 超过 max_chunk_ms 时的兜底切点

        for j in range(start_idx, len(sorted_ids)):
            lid = sorted_ids[j]
            current_start_ms, _ = line_ranges[lid]
            chunk_duration_ms = current_start_ms - prev_chunk_start_ms

            # 硬上限保护：超过最大段长，无论角色是否切换都切
            if fallback_by_max is None and chunk_duration_ms >= max_chunk_ms:
                remaining_ms = total_duration_ms - current_start_ms
                if remaining_ms >= min_tail_ms:
                    fallback_by_max = lid

            # 查找角色切换点
            prev_lid = sorted_ids[j - 1]
            prev_role = role_at(prev_lid)
            curr_role = role_at(lid)

            if prev_role and curr_role and prev_role != curr_role:
                # 角色切换了！检查尾段是否足够
                remaining_ms = total_duration_ms - current_start_ms
                if remaining_ms >= min_tail_ms:
                    if best_by_role is None:
                        best_by_role = lid
                    # 找到角色切换点后继续走一段看看是否还在 max_chunk_ms 内，
                    # 但如果已经到了兜底位置就不再找了
                    if fallback_by_max is not None and lid >= fallback_by_max:
                        break
                else:
                    # 角色切换了但尾段太短，这个切点不能用，继续往后
                    pass

        # 优先返回角色切换点，其次返回兜底切点
        return best_by_role or fallback_by_max

    @staticmethod
    def _chunk_suffix(chunk_index: int, total_chunks: int) -> str:
        """根据片段索引和总数返回命名后缀。

        Args:
            chunk_index: 0-based 片段索引
            total_chunks: 总片段数

        Returns:
            命名后缀字符串，如 '_1'、'_2'、'_3'、''（不切片时）
        """
        if total_chunks <= 1:
            return ""
        return f"_{chunk_index + 1}"

    def _export_chapter_audio(self, merged_audio: AudioSegment,
                              line_ranges: Dict[int, tuple] = None) -> str:
        print(f"\n📦 开始导出最终章节音频...")

        total_ms = len(merged_audio)
        total_seconds = total_ms / 1000.0

        # 目标段长 8 分钟
        target_chunk_seconds = int(os.environ.get("CHAPTER_CHUNK_MINUTES", "8")) * 60

        print(f"\n📋 [Export] 进入导出阶段，总时长={total_seconds/60:.1f}min, "
              f"target_chunk={target_chunk_seconds//60}min")

        # 用总时长 ÷ 目标段长，四舍五入得段数 N，直接算每段起止毫秒
        chunk_offsets = self._find_chunk_splits_audio(total_ms, target_chunk_seconds)
        chunk_offsets.append(total_ms)  # 末尾边界
        total_chunks = len(chunk_offsets) - 1

        # 多段切分时，line_0 是章节标题（如"第134回"），每段已有独立的 chunk_title_audio，
        # 需要把 line_0 对应的音频从正文中剔除，避免标题重复朗读。
        # 单段时保留 line_0（不生成 chunk_title_audio，正文直接包含标题）。
        title_end_ms = 0
        if total_chunks > 1 and line_ranges and 0 in line_ranges:
            title_end_ms = int(line_ranges[0][1])
            print(f"  [Export] 多段切分，剔除 line_0（章节标题 {title_end_ms}ms）")

        # 切分时应排除标题时长，否则第一个 chunk 的正文会远短于其他段
        if total_chunks > 1 and title_end_ms > 0:
            body_total_ms = total_ms - title_end_ms
            chunk_offsets = self._find_chunk_splits_audio(body_total_ms, target_chunk_seconds)
            chunk_offsets = [o + title_end_ms for o in chunk_offsets]  # 整体偏移，跳过标题
            chunk_offsets.append(total_ms)
            total_chunks = len(chunk_offsets) - 1

        print(f"\n📋 章节切分（{total_chunks} 段），每段起始偏移 (ms): {chunk_offsets[:-1]}")

        output_paths = []

        for chunk_index in range(total_chunks):
            start_ms = chunk_offsets[chunk_index]
            end_ms = chunk_offsets[chunk_index + 1]
            chunk_duration_sec = (end_ms - start_ms) / 1000.0

            # 第 N 集标签（仅多段时使用）
            suffix = self._chunk_suffix(chunk_index, total_chunks)
            label = self._chunk_label(suffix)
            print(f"\n📻 拼接第{chunk_index + 1}/{total_chunks}集，正文 {chunk_duration_sec/60:.1f}min: '{label}'")

            # 生成标题前缀音频（仅多段时需要）
            if total_chunks > 1:
                title_audio = self._generate_chunk_title_audio(label)
            else:
                title_audio = None

            # 构造正文区间：多段时剔除 line_0 对应的 offset，避免标题+chunk_title 重复
            chunk_body = merged_audio[start_ms:end_ms]
            if total_chunks > 1 and title_end_ms > 0 and start_ms < title_end_ms:
                # 当前段的起始正好是 line_0 或其他前段，但 title 只在开头
                # 需要把 line_0 部分（0..title_end_ms）去掉，然后只取有效正文
                if start_ms == 0:
                    chunk_body = merged_audio[title_end_ms:end_ms]
                else:
                    # 后续段 start_ms > title_end_ms，无需处理
                    pass

            # 拼接：片头 + 标题前缀 + 正文 + 片尾
            final_chunk = AudioSegment.silent(duration=0, frame_rate=self.platform_profile.sample_rate)

            # 片头
            metadata = self._extract_platform_metadata()
            intro_text = self.platform_profile.intro_template.format(**metadata) if self.platform_profile.intro_template else None
            intro = self._load_platform_asset_audio("片头", intro_text) if intro_text else None
            if intro:
                final_chunk += intro
                print(f"  ✅ 片头已加载（{len(intro) / 1000:.1f}s），拼接到正文前")
            elif self.platform_profile.intro_template:
                print(f"  ⚠️ 片头未生成（TTS 合成失败），跳过")

            # 集标题
            if title_audio:
                title_audio = title_audio.set_frame_rate(self.platform_profile.sample_rate).set_channels(self.platform_profile.channels)
                final_chunk += AudioSegment.silent(duration=200, frame_rate=self.platform_profile.sample_rate)
                final_chunk += title_audio
                print(f"  📢 已追加章节标题前缀: '{label}' ({title_audio.duration_seconds:.1f}s)")

            # 正文
            final_chunk += AudioSegment.silent(duration=200, frame_rate=self.platform_profile.sample_rate)
            final_chunk += chunk_body

            # 片尾
            outro_text = self.platform_profile.outro_template.format(**metadata) if self.platform_profile.outro_template else None
            outro = self._load_platform_asset_audio("片尾", outro_text) if outro_text else None
            if outro:
                final_chunk += AudioSegment.silent(duration=300, frame_rate=self.platform_profile.sample_rate)
                final_chunk += outro
                print(f"  ✅ 片尾已加载（{len(outro) / 1000:.1f}s），拼接到正文后")
            elif self.platform_profile.outro_template:
                print(f"  ⚠️ 片尾未生成（TTS 合成失败），跳过")

            total_dur_sec = final_chunk.duration_seconds
            print(f"  📏 最终音频总时长: {total_dur_sec:.1f}s / {total_dur_sec/60:.2f}min")

            suffix = self._chunk_suffix(chunk_index, total_chunks)
            output_ext = self.platform_profile.output_format
            chapter_output_path = os.path.join(
                self.chapter_dir, f"{self.chapter_clean_name}{suffix}.{output_ext}"
            )
            export_kwargs = {"format": output_ext}
            if self.platform_profile.bitrate:
                export_kwargs["bitrate"] = self.platform_profile.bitrate

            chunk_label = f"[{chunk_index + 1}/{total_chunks}]" if total_chunks > 1 else ""
            print(f"  📡 {chunk_label} 正在编码导出，格式: {output_ext.upper()}/{self.platform_profile.channels}ch/{self.platform_profile.sample_rate}Hz...")
            final_chunk.export(chapter_output_path, **export_kwargs)
            print(f"  💾 导出完成: {chapter_output_path}")
            output_paths.append(chapter_output_path)

        return output_paths[0] if output_paths else ""

    def _chunk_label(self, suffix: str, with_pause: bool = False) -> str:
        """根据后缀生成统一的章节标签。

        Args:
            suffix: 文件名后缀，如 '_1'、'_2'、'_3'，空字符串时返回空
            with_pause: 是否在"第N集"前插入逗号停顿

        Returns:
            章节标签，如 "第43回 第1集"、空字符串（suffix 为空时）
        """
        if not suffix:
            return ""
        chapter_name = self.config["data"][0].get("api", {}).get("voice", {}).get("text") or self.config.get("chapter", "无名章节")
        num = suffix.lstrip("_")
        label = f"{chapter_name} 第{num}集"
        if with_pause:
            import re
            label = re.sub(r' (第\d+集)$', r'，\1', label)
        return label

    def _generate_chunk_title_audio(self, chapter_label: str) -> Optional[AudioSegment]:
        """为非首段生成章节标题前缀音频（缓存复用）。

        使用旁白音色朗读章节标签，如"第43回 第1集"。
        缓存 key 基于标签文本 hash，避免重复合成。

        Args:
            chapter_label: 章节标签文本

        Returns:
            AudioSegment，或 None（合成失败时）
        """
        self._chunk_title_seq += 1
        cache_path = os.path.join(self.chapter_dir, f"chunk_title_{self._chunk_title_seq:02d}.wav")
        if os.path.exists(cache_path):
            print(f"  📢 复用章节标题前缀缓存: {cache_path}")
            return AudioSegment.from_wav(cache_path).set_frame_rate(
                self.platform_profile.sample_rate
            ).set_channels(self.platform_profile.channels)

        # 使用全局固定的标题播报角色
        title_voice = TITLE_VOICE_ROLE
        title_speed = "-10%"
        title_volume = "0%"
        title_pitch = "0Hz"

        try:
            voice_params = VoiceParams(
                text=chapter_label,
                role="标题播报",
                role_voice=title_voice,
                speed=title_speed,
                volume=title_volume,
                pitch=title_pitch,
                instruct="",
                tts_mode="clone",  # chunk 标题固定 clone 保证一致
            )
            title_audio = self.audio_engine.text_to_speech(voice_params)
            title_audio = title_audio.set_frame_rate(
                self.platform_profile.sample_rate
            ).set_channels(self.platform_profile.channels)
            title_audio.export(cache_path, format="wav")
            print(f"  📢 已生成章节标题前缀音频: {cache_path}")
            return title_audio
        except Exception as e:
            print(f"  ⚠️ 生成章节标题前缀失败: {e}")
            return None

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
        """持久化失败行到 JSON 文件"""
        if not self.failed_lines:
            return
        failed_path = os.path.join(self.chapter_dir, "failed_lines.json")
        payload = {
            "novel_name": self.novel_name,
            "chapter": self.chapter_name,
            "total_lines": self.total_lines,
            "failed_count": len(self.failed_lines),
            "failed_lines": list(self.failed_lines.values()),
        }
        with open(failed_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"💾 失败段落记录已保存: {self.failed_lines_log_path}")

    def _persist_quality_warnings(self):
        """持久化 TTS 质量异常到 JSON 文件"""
        if not self._quality_warnings:
            return
        warn_path = os.path.join(self.chapter_dir, "quality_warnings.json")
        payload = {
            "novel_name": self.novel_name,
            "chapter": self.chapter_name,
            "warnings_count": len(self._quality_warnings),
            "warnings": self._quality_warnings,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(warn_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"📝 质量异常记录: quality_warnings.json ({len(self._quality_warnings)} 条)")

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

    def _ffmpeg_concat_wavs(self, wav_files: List[str], output_path: str):
        """使用 ffmpeg concat 协议将多个 wav 文件合并为一个，避免一次性加载所有音频到内存。
        
        先将每个输入文件标准化为 44100Hz/2ch/PCM16，再用 concat demuxer 无损拼接。
        这样避免了 concat demuxer 遇到不同采样率时产生的语速异常问题。
        """
        if not wav_files:
            AudioSegment.silent(duration=0, frame_rate=44100).export(output_path, format="wav")
            return

        # 临时目录存放标准化后的文件
        norm_dir = output_path + "_norm"
        os.makedirs(norm_dir, exist_ok=True)
        norm_files = []

        try:
            # Step 1: 标准化每个输入文件为 44100Hz/2ch/pcm_s16le
            for i, wav in enumerate(wav_files):
                norm_path = os.path.join(norm_dir, f"{i:04d}.wav")
                cmd_norm = [
                    "ffmpeg", "-y", "-i", wav,
                    "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
                    norm_path
                ]
                r = subprocess.run(cmd_norm, capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    # fallback: 直接拷贝原文件（可能格式已一致）
                    import shutil
                    shutil.copy2(wav, norm_path)
                norm_files.append(norm_path)

            # Step 2: 写 concat 清单并用 -c copy 拼接（格式已统一，安全无损）
            list_path = output_path + ".txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for nf in norm_files:
                    safe_path = os.path.abspath(nf).replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")

            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_path,
                "-c", "copy",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg concat 失败: {result.stderr[-500:]}")

            try:
                os.remove(list_path)
            except:
                pass
        finally:
            # 清理标准化临时文件
            import shutil
            try:
                shutil.rmtree(norm_dir, ignore_errors=True)
            except:
                pass

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

        # 注入 tts_mode：旁白强制 clone（使用 voice_design 生成的参考音频），其他角色走 voice_design
        #role_name = line.get('role', '')
        #line_id = line.get('id', -1)
        #if role_name == '旁白':
        #    voice_params_dict['tts_mode'] = 'clone'
        #elif 'tts_mode' not in voice_params_dict:
        #    voice_params_dict['tts_mode'] = self.tts_mode
        voice_params_dict['tts_mode'] = self.tts_mode

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
                    process_mode=effect.get("process_mode", "overlay"),
                    trigger_keyword=effect.get("trigger_keyword", ""),
                    trigger_offset=effect.get("trigger_offset", 0.0)
                ))
        
        mix_config = MixConfig(**line["api"].get("mix", {"mode": "mix"}))
        
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
            f"\n🎙️ [{self.novel_name} / {self.chapter_name}] 正在合成第{current_index}句，已完成{self.completed_count}句，共{self.total_lines}句 | 角色: {line_config.role} | 文本: {text_preview}..."
        )
        
        voice_output_path = os.path.join(self.voice_dir, f"voice_line_{line_config.id}.wav")
        single_output_path = os.path.join(self.mix_dir, f"mixed_line_{line_config.id}.wav")
        generated_new_audio = False
        remixed_audio = False
        
        if os.path.exists(voice_output_path):
            print(
                f"🟢 [{self.novel_name} / {self.chapter_name}] 正在合成第{current_index}句，已完成{self.completed_count}句，共{self.total_lines}句 | 命中 voice 缓存，重新混音"
            )
            remixed_audio = True
            voice_audio = AudioSegment.from_wav(voice_output_path)
        elif os.path.exists(single_output_path):
            print(
                f"🟡 [{self.novel_name} / {self.chapter_name}] 正在合成第{current_index}句，已完成{self.completed_count}句，共{self.total_lines}句 | 命中 mixed 缓存，直接复用"
            )
            self.completed_count += 1
            return AudioSegment.from_wav(single_output_path)
        else:
            print(
                f"🔴 [{self.novel_name} / {self.chapter_name}] 正在合成第{current_index}句，已完成{self.completed_count}句，共{self.total_lines}句 | 未命中缓存，开始生成 TTS"
            )
            generated_new_audio = True
            voice_audio = self.audio_engine.text_to_speech(line_config.voice_params)

            # VoiceDesign 模式：检查配音表中角色但无有效语音属性，记录警告
            if self.tts_mode == "voice_design":
                for missing_role in self.audio_engine.get_voice_table_missing():
                    self.record_failed_line(
                        line_config,
                        Exception(f"missing_from_voice_table: 角色「{missing_role}」在配音表中但无有效语音属性，已使用兜底 Prompt"),
                    )

            # 收集 TTS 质量异常
            warnings = self.audio_engine.get_quality_warnings()

            # 质量异常 → 自动重试（最多 2 次）
            # 只对时长异常（过短/过长）重试，连续静音不重试（TTS 固有停顿，重试无意义）
            def _should_retry(w_list):
                # 判断当前警告列表中是否存在需要重试的项
                # 过滤规则：只要有任意一个警告的 issue 字段不含"静音"关键字，就认为需要重试
                # 原因：静音类警告属于 TTS 固有停顿，重试无法改善，只有时长异常等才值得重试
                return any(w for w in w_list if "静音" not in w.get("issue", ""))

            for attempt in range(2):
                if not warnings: break
                if not _should_retry(warnings):
                    for w in warnings:
                        print(f"  ⚠️ 继续使用（非重试类警告）: {w['issue']}")
                    break
                print(f"  🔄 质量异常重试 {attempt+1}/2: {warnings[0]['issue']}")
                del voice_audio
                voice_audio = self.audio_engine.text_to_speech(line_config.voice_params)
                warnings = self.audio_engine.get_quality_warnings()

            if warnings:
                for w in warnings:
                    w["line_id"] = line_config.id
                self._quality_warnings.extend(warnings)
                self._persist_quality_warnings()

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
        
        # 音效处理
        effect_count = len(line_config.effect_params)
        if effect_count > 0:
            print(f"  🎵 本句配置了 {effect_count} 个音效")
        
        for i, effect_param in enumerate(line_config.effect_params):
            effect_name = effect_param.name.replace(" ", "_").replace("/", "_").replace(":", "_").replace("\n", "")
            effect_output_path = os.path.join(self.effect_dir, f"effect_line_{line_config.id}_{effect_name}.wav")
            effect_output_paths.append(effect_output_path)
            if not os.path.exists(effect_output_path):
                print(f"    ➕ 音效{i+1}/{effect_count}: {effect_name} ({effect_param.duration}s) - 待生成")
                sfx_tasks.append({
                    "prompt": effect_param.sound_en,
                    "duration": effect_param.duration,
                    "output_path": effect_output_path
                })
            else:
                print(f"    ✅ 音效{i+1}/{effect_count}: {effect_name} - 已存在，使用缓存")
        
        if bgm_tasks:
            print(f"🔄 开始批量生成 {len(bgm_tasks)} 个背景音 (引擎: {self.bgm_engine}, max_workers=2)...")
            self._generate_bgm_batch(bgm_tasks, max_workers=2)

        if sfx_tasks:
            print(f"🔄 开始批量生成 {len(sfx_tasks)} 个音效 (引擎: {self.sfx_engine})...")
            generated_sfx = self._generate_sfx_batch(sfx_tasks)
            success_count = sum(1 for p in generated_sfx if p is not None)
            print(f"✅ 音效生成完成: {success_count}/{len(sfx_tasks)} 个成功")
        
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
        
        loaded_effects = 0
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
                loaded_effects += 1
            else:
                print(f"    ⚠️ 音效文件不存在: {os.path.basename(effect_output_path)}")
        
        if effect_count > 0:
            print(f"  🎵 音效加载: {loaded_effects}/{effect_count} 个成功，即将混入音频")
        
        mixed_audio = self.audio_engine.mix_audio(
            voice=voice_audio,
            bgm=bgm_audio,
            effects=effect_audios,
            mix_config=line_config.mix_config,
            effect_params=line_config.effect_params,
            voice_text=line_config.voice_params.text,
            voice_path=voice_output_path,
        )
        
        if self.persist_intermediate_audio or generated_new_audio or remixed_audio:
            mixed_audio.export(single_output_path, format="wav")
            if generated_new_audio and not self.persist_intermediate_audio:
                print(f"💾 新生成单句混合音频已保存: {single_output_path}")
            elif remixed_audio and not self.persist_intermediate_audio:
                print(f"💾 重混单句混合音频已保存: {single_output_path}")
            else:
                print(f"💾 单句混合音频已保存: {single_output_path}")
        
        self.completed_count += 1
        return mixed_audio

    def generate_chapter_audio(self) -> str:
        """生成整章音频"""
        output_ext = self.platform_profile.output_format
        chapter_output_path = os.path.join(
            self.chapter_dir,
            f"{self.chapter_clean_name}.{output_ext}",
        )
        # 同时检查未切分和已切分的输出文件（支持 _1/_2 等后缀）
        import glob as _glob
        chunk_pattern = os.path.join(self.chapter_dir, f"{self.chapter_clean_name}_*.{output_ext}")
        existing_chunks = _glob.glob(chunk_pattern)
        if os.path.exists(chapter_output_path):
            print(f"✅ 整章音频已存在，跳过生成: {chapter_output_path}")
            return chapter_output_path
        elif existing_chunks:
            print(f"✅ 检测到 {len(existing_chunks)} 个已切分音频文件，跳过生成: {os.path.basename(existing_chunks[0])} ...")
            return existing_chunks[0]

        # 检测是否存在上次中断留下的 stream_tmp，自动续跑
        stream_tmp_dir = os.path.join(self.chapter_dir, "stream_tmp")
        existing_tmp = set()
        if os.path.isdir(stream_tmp_dir):
            for fname in os.listdir(stream_tmp_dir):
                if fname.startswith("line_") and fname.endswith(".wav"):
                    try:
                        existing_tmp.add(int(fname[5:-4]))
                    except ValueError:
                        pass
            if existing_tmp:
                print(f"⚡ 检测到上次中断的流式临时文件 ({len(existing_tmp)} 行)，自动续跑缺失行...")

        if self.tts_engine == "qwen3-tts":
            return self.generate_chapter_audio_serial(resume_ids=existing_tmp)
        return self.generate_chapter_audio_parallel(resume_ids=existing_tmp)

    def _periodic_memory_cleanup(self):
        """定期内存清理：每N句合成后执行，防止MPS/CUDA缓存累积导致内存暴涨"""
        try:
            # 记录清理前内存状态
            mem_before = psutil.virtual_memory()
            available_before = mem_before.available / 1024 / 1024  # MB
            percent_before = mem_before.percent
            
            # 强制垃圾回收
            gc.collect()
            
            # 清理 PyTorch MPS/CUDA 缓存
            try:
                import torch
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                elif torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            
            # 清理 AudioEngine 的 prompt 缓存（保留最近10条而不是32条）
            if hasattr(self, 'audio_engine') and self.audio_engine:
                cache = self.audio_engine._voice_clone_prompt_cache
                max_keep = 10
                while len(cache) > max_keep:
                    oldest_key = next(iter(cache))
                    del cache[oldest_key]
                
                vd_cache = self.audio_engine._vd_prefix_cache
                while len(vd_cache) > max_keep:
                    oldest_key = next(iter(vd_cache))
                    del vd_cache[oldest_key]
            
            # macOS: 强制归还已释放内存给系统
            _release_malloc_memory()
            
            # 记录清理后内存状态
            mem_after = psutil.virtual_memory()
            available_after = mem_after.available / 1024 / 1024  # MB
            percent_after = mem_after.percent
            
            # 输出内存监控日志
            freed_mb = available_after - available_before
            print(f"\n  🧹 [内存清理] 可用: {available_before:.0f}MB → {available_after:.0f}MB (释放{freed_mb:+.0f}MB) | 使用率: {percent_before}% → {percent_after}%")
            
        except Exception as e:
            print(f"  ⚠️ 定期内存清理时出错: {e}")

    def _cleanup_chapter_intermediate_dirs(self):
        """清理整章的中间产物目录（配音、背景音、音效、混音），节省磁盘存储 """
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

    def generate_chapter_audio_serial(self, resume_ids: set = None) -> str:
        """串行生成整章音频（流式写入优化）。

        Args:
            resume_ids: 已有 stream_tmp 的 line_id 集合。传入时跳过这些行的 TTS 生成，
                        直接从已有文件恢复，实现中断续跑。
        """
        is_resume = bool(resume_ids)
        if is_resume:
            print(f"\n🔄 续跑模式 | 小说: {self.novel_name} | 章节: {self.chapter_name} | 跳过已完成 {len(resume_ids)} 行")
        else:
            print(f"\n🚀 开始串行生成 | 小说: {self.novel_name} | 章节: {self.chapter_name} | 共{self.total_lines}句")
        start_time = time.time()

        line_configs = [self._parse_line_config(line) for line in self.config["data"]]
        soundscape_layers = []  # self._parse_soundscape_layers()  # 已屏蔽背景音解析

        # 创建临时目录存放每句音频
        stream_tmp_dir = os.path.join(self.chapter_dir, "stream_tmp")
        os.makedirs(stream_tmp_dir, exist_ok=True)

        # 从已有 tmp 文件中恢复 tmp_files 列表和时间轴
        tmp_files = []
        if is_resume:
            for lid in sorted(resume_ids):
                fpath = os.path.join(stream_tmp_dir, f"line_{lid}.wav")
                if os.path.exists(fpath):
                    tmp_files.append((lid, fpath))
            # 检查 silent_0.wav
            silent_file = os.path.join(stream_tmp_dir, "silent_0.wav")
            if os.path.exists(silent_file):
                tmp_files.append((-1, silent_file))
            # 重新计算 line_ranges 和 current_ms（基于已有音频时长）
            # 排序：line_0, silent_0(-1 排在 0 之后), line_1, line_2, ...
            tmp_files_sorted = sorted(tmp_files, key=lambda x: (x[0] if x[0] >= 0 else 0.5))
            line_ranges = {}
            current_ms = 0
            for lid, fpath in tmp_files_sorted:
                if lid < 0:
                    seg = AudioSegment.from_wav(fpath)
                    current_ms += len(seg)
                    del seg
                    continue
                seg = AudioSegment.from_wav(fpath)
                dur = len(seg)
                line_ranges[lid] = (current_ms, current_ms + dur)
                current_ms += dur
                del seg
        else:
            line_ranges = {}
            current_ms = 0

        # 初始化已合成计数：基于已有配音文件数
        if os.path.isdir(self.voice_dir):
            existing_voice_ids = set()
            for f in os.listdir(self.voice_dir):
                if f.startswith("voice_line_") and f.endswith(".wav"):
                    try:
                        existing_voice_ids.add(int(f[11:-4]))
                    except ValueError:
                        pass
            # 不在这里设置 completed_count，让处理循环自己统计
        else:
            existing_voice_ids = set()
            self.completed_count = 0

        # ── 按角色分组：同一角色连续合成，减少模型切换 ──
        role_order = []
        role_groups = {}
        for lc in line_configs:
            role = lc.voice_params.role if hasattr(lc, 'voice_params') else getattr(lc, 'role', '')
            if role not in role_groups:
                role_groups[role] = []
                role_order.append(role)
            role_groups[role].append(lc)

        processed_since_cleanup = 0
        CLEANUP_EVERY_N_LINES = 5  # 每5句清理一次内存

        # 打印角色分组概览
        print(f"\n📋 角色分组概览（共 {len(role_order)} 个角色）:")
        for i, r in enumerate(role_order, 1):
            print(f"   {i}. {r}: {len(role_groups[r])} 句")
        print()

        for role in role_order:
            group = role_groups[role]
            tts_label = f"🎤 {self.tts_mode}"
            line_ids = [lc.id + 1 for lc in group]
            print(f"\n  ════════════════════════════════════════════════════")
            print(f"  🎭 角色: [{role}] {tts_label}")
            print(f"  📝 本组合成 {len(group)} 句（第 {line_ids} 句）")
            print(f"  ════════════════════════════════════════════════════")

            for line_config in group:
                try:
                    # 混音文件存在 → 直接复用；只有配音文件 → 重新混音
                    mixed_path = os.path.join(self.mix_dir, f"mixed_line_{line_config.id}.wav")
                    if os.path.exists(mixed_path):
                        cached = AudioSegment.from_wav(mixed_path)
                        dur_ms = len(cached)
                        line_ranges[line_config.id] = (current_ms, current_ms + dur_ms)
                        current_ms += dur_ms
                        tmp_file = os.path.join(stream_tmp_dir, f"line_{line_config.id}.wav")
                        cached.export(tmp_file, format="wav")
                        tmp_files.append((line_config.id, tmp_file))
                        del cached
                        self.completed_count += 1
                        print(f"  ✅ 命中混音缓存 #{line_config.id}，直接复用")
                        if line_config.id == 0:
                            silent_audio = AudioSegment.silent(duration=600, frame_rate=44100)
                            silent_file = os.path.join(stream_tmp_dir, "silent_0.wav")
                            silent_audio.export(silent_file, format="wav")
                            tmp_files.append((-1, silent_file))
                            current_ms += 600
                        continue
                    elif line_config.id in existing_voice_ids:
                        print(f"  🟢 命中配音缓存 #{line_config.id}，重新混音")
                except Exception as e:
                    print(f"  ⚠️ 缓存配音读取失败 #{line_config.id}: {e}，将重新合成")
                    existing_voice_ids.discard(line_config.id)
                try:
                    group_idx = group.index(line_config) + 1
                    print(f"  📊 [{role}] 组内进度 {group_idx}/{len(group)} | 全文第{line_config.id + 1}句，已完成{self.completed_count}句")
                    line_audio = self.generate_single_line(line_config)
                    
                    start_ms = current_ms
                    duration_ms = len(line_audio)
                    end_ms = start_ms + duration_ms
                    line_ranges[line_config.id] = (start_ms, end_ms)
                    current_ms = end_ms
                    
                    tmp_file = os.path.join(stream_tmp_dir, f"line_{line_config.id}.wav")
                    line_audio.export(tmp_file, format="wav")
                    tmp_files.append((line_config.id, tmp_file))
                    
                    if line_config.id == 0:
                        silent_audio = AudioSegment.silent(duration=600, frame_rate=44100)
                        silent_file = os.path.join(stream_tmp_dir, f"silent_0.wav")
                        silent_audio.export(silent_file, format="wav")
                        tmp_files.append((-1, silent_file))
                        current_ms += 600
                    
                    del line_audio
                    
                    # 定期清理内存，防止累积
                    processed_since_cleanup += 1
                    if processed_since_cleanup >= CLEANUP_EVERY_N_LINES:
                        self._periodic_memory_cleanup()
                        processed_since_cleanup = 0
                    
                except Exception as e:
                    print(f"  ❌ 第 {line_config.id} 句异常: {e}")
                    self.record_failed_line(line_config, e)
            
            # 角色组完成标记
            print(f"  ✅ 角色 [{role}] 合成完成（{len(group)} 句）")

        # 持久化失败段落记录
        self.persist_failed_lines()

        if self.has_failed_lines():
            failed_count = len(self.failed_lines)
            missing_from_voice = any("missing_from_voice_table" in e.get("error", "") for e in self.failed_lines.values())
            reason = "（配音表缺失）" if missing_from_voice else ""
            print(f"\n⚠️ 检测到 {failed_count}/{self.total_lines} 句合成失败{reason}，已跳过，将在后续修复配音表后重新合成")
            print(f"📋 失败段落明细:\n{self.summarize_failed_lines()}")

        # ── 最终对齐校验：已完成数 vs 总行数 ──
        expected_ids = set(range(self.total_lines))
        actual_ids = {lid for lid, _ in tmp_files if lid >= 0}
        missing_ids = expected_ids - actual_ids
        if missing_ids:
            print(f"\n❌ 最终校验失败：缺少 {len(missing_ids)} 句配音 ({sorted(missing_ids)[:20]}{'...' if len(missing_ids) > 20 else ''})，中止导出")
            print(f"  已完成: {self.completed_count}/{self.total_lines}，缺 {len(missing_ids)} 句")
            return ""
        if self.completed_count != self.total_lines:
            print(f"\n⚠️ 计数不一致: completed={self.completed_count}, total={self.total_lines}")
        else:
            print(f"\n✅ 对齐校验通过: {self.completed_count}/{self.total_lines} 句全部就绪")

        # 合并所有临时文件（使用 ffmpeg concat 节省内存）
        print(f"\n📦 合并 {len(tmp_files)} 个音频片段...")
        # 按生成顺序排列 + 去重：line_0, silent_0(-1排在0之后), line_1, line_2, ...
        seen = set()
        deduped = []
        for entry in sorted(tmp_files, key=lambda x: (x[0] if x[0] >= 0 else 0.5)):
            if entry[0] not in seen:
                seen.add(entry[0])
                deduped.append(entry)
        tmp_files = deduped

        # ⚠️ 关键修正：按角色分组合成时 line_ranges 的时间位置是错乱的，
        # 必须按最终合并顺序（line_id 排序）重新计算，否则分卷切点会落在错误位置。
        line_ranges = {}
        current_ms = 0
        for line_id, tmp_file in tmp_files:
            seg = AudioSegment.from_wav(tmp_file)
            duration_ms = len(seg)
            del seg
            if line_id >= 0:
                line_ranges[line_id] = (current_ms, current_ms + duration_ms)
            current_ms += duration_ms

        merged_wav_path = os.path.join(stream_tmp_dir, "_merged_chapter.wav")
        self._ffmpeg_concat_wavs([f for _, f in tmp_files], merged_wav_path)

        # 加载合并后的音频用于后续处理
        merged_audio = AudioSegment.from_wav(merged_wav_path)

        if soundscape_layers:
            print("\n🎼 开始叠加 soundscape 背景音...")
            self._prepare_soundscape_layers(soundscape_layers)
            merged_audio = self._apply_soundscape(merged_audio, line_ranges, soundscape_layers)

        chapter_output_path = self._export_chapter_audio(merged_audio, line_ranges)
        del merged_audio
        gc.collect()

        # 清理临时文件
        print(f"\n🗑️ 清理流式临时文件...")
        try:
            os.remove(merged_wav_path)
        except:
            pass
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

    def generate_chapter_audio_parallel(self, resume_ids: set = None) -> str:
        """并行生成整章音频（流式写入优化）。

        Args:
            resume_ids: 已有 stream_tmp 的 line_id 集合，传入时跳过这些行，实现中断续跑。
        """
        is_resume = bool(resume_ids)
        if is_resume:
            print(f"\n🔄 续跑模式（并行）| 小说: {self.novel_name} | 章节: {self.chapter_name} | 跳过已完成 {len(resume_ids)} 行")
        else:
            print(f"\n🚀 开始并行生成 | 小说: {self.novel_name} | 章节: {self.chapter_name} | 共{self.total_lines}句")
        start_time = time.time()

        line_configs = [self._parse_line_config(line) for line in self.config["data"]]
        soundscape_layers = []  # self._parse_soundscape_layers()  # 已屏蔽背景音解析

        # 创建临时目录存放每句音频
        stream_tmp_dir = os.path.join(self.chapter_dir, "stream_tmp")
        os.makedirs(stream_tmp_dir, exist_ok=True)

        # 续跑：先收集已有文件
        tmp_files = []
        if is_resume:
            for lid in sorted(resume_ids):
                fpath = os.path.join(stream_tmp_dir, f"line_{lid}.wav")
                if os.path.exists(fpath):
                    tmp_files.append((lid, fpath))

        # 初始化已合成计数：基于已有配音文件数
        if os.path.isdir(self.voice_dir):
            existing_voice_ids = set()
            for f in os.listdir(self.voice_dir):
                if f.startswith("voice_line_") and f.endswith(".wav"):
                    try:
                        existing_voice_ids.add(int(f[11:-4]))
                    except ValueError:
                        pass
            self.completed_count = len(existing_voice_ids)
        else:
            existing_voice_ids = set()
            self.completed_count = 0

        # 只对缺失行进行并行生成
        pending_configs = [lc for lc in line_configs if lc.id not in existing_voice_ids]
        total_lines = len(line_configs)
        max_workers = min(3, len(pending_configs)) if pending_configs else 1

        # 已有配音文件直接加入 tmp_files（确保合并时不缺失）
        for line_config in line_configs:
            if line_config.id in existing_voice_ids:
                voice_path = os.path.join(self.voice_dir, f"voice_line_{line_config.id}.wav")
                try:
                    cached = AudioSegment.from_wav(voice_path)
                    tmp_file = os.path.join(stream_tmp_dir, f"line_{line_config.id}.wav")
                    cached.export(tmp_file, format="wav")
                    tmp_files.append((line_config.id, tmp_file))
                    del cached
                except Exception as e:
                    print(f"  ⚠️ 缓存配音读取失败 #{line_config.id}: {e}，加入待合成队列")
                    existing_voice_ids.discard(line_config.id)
                    pending_configs.append(line_config)

        if pending_configs:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_line = {
                    executor.submit(self.generate_single_line, line_config): line_config
                    for line_config in pending_configs
                }
                for index, future in enumerate(concurrent.futures.as_completed(future_to_line), 1):
                    line_config = future_to_line[future]
                    print(f"\n📊 [{self.novel_name} / {self.chapter_name}] 已并行完成 {index}/{len(pending_configs)} 句（待处理），总进度 {self.completed_count}/{self.total_lines} | 当前返回: 第{line_config.id + 1}句")
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
        else:
            print(f"✅ 所有行已在上次运行中生成，直接合并")

        # 持久化失败段落记录
        self.persist_failed_lines()

        if self.has_failed_lines():
            failed_count = len(self.failed_lines)
            missing_from_voice = any("missing_from_voice_table" in e.get("error", "") for e in self.failed_lines.values())
            reason = "（配音表缺失）" if missing_from_voice else ""
            print(f"\n⚠️ 检测到 {failed_count}/{self.total_lines} 句合成失败{reason}，已跳过，将在后续修复配音表后重新合成")
            print(f"📋 失败段落明细:\n{self.summarize_failed_lines()}")

        # ── 最终对齐校验 ──
        expected_ids = set(range(self.total_lines))
        actual_ids = {lid for lid, _ in tmp_files if lid >= 0}
        missing_ids = expected_ids - actual_ids
        if missing_ids:
            print(f"\n❌ 最终校验失败：缺少 {len(missing_ids)} 句配音 ({sorted(missing_ids)[:20]}{'...' if len(missing_ids) > 20 else ''})，中止导出")
            print(f"  已完成: {self.completed_count}/{self.total_lines}，缺 {len(missing_ids)} 句")
            return ""
        if self.completed_count != self.total_lines:
            print(f"\n⚠️ 计数不一致: completed={self.completed_count}, total={self.total_lines}")
        else:
            print(f"\n✅ 对齐校验通过: {self.completed_count}/{self.total_lines} 句全部就绪")

        # 合并所有临时文件（使用 ffmpeg concat 节省内存）
        print(f"\n📦 合并 {len(tmp_files)} 个音频片段...")
        # 排序 + 去重：line_0, silent_0(-1排在0之后), line_1, line_2, ...
        seen = set()
        deduped = []
        for entry in sorted(tmp_files, key=lambda x: (x[0] if x[0] >= 0 else 0.5)):
            if entry[0] not in seen:
                seen.add(entry[0])
                deduped.append(entry)
        tmp_files = deduped

        # 计算 line_ranges（通过读取各 wav 时长，不需要全部加载到内存）
        line_ranges = {}
        current_ms = 0
        for line_id, tmp_file in tmp_files:
            seg = AudioSegment.from_wav(tmp_file)
            duration_ms = len(seg)
            del seg
            if line_id >= 0:
                line_ranges[line_id] = (current_ms, current_ms + duration_ms)
            current_ms += duration_ms
            # 第一句后有600ms静音（对应 silent_0.wav，line_id=-1）

        merged_wav_path = os.path.join(stream_tmp_dir, "_merged_chapter.wav")
        self._ffmpeg_concat_wavs([f for _, f in tmp_files], merged_wav_path)

        # 加载合并后的音频用于后续处理
        merged_audio = AudioSegment.from_wav(merged_wav_path)

        if soundscape_layers:
            print("\n🎼 开始叠加 soundscape 背景音...")
            self._prepare_soundscape_layers(soundscape_layers)
            merged_audio = self._apply_soundscape(merged_audio, line_ranges, soundscape_layers)

        chapter_output_path = self._export_chapter_audio(merged_audio, line_ranges)
        del merged_audio
        gc.collect()

        # 清理临时文件
        print(f"\n🗑️ 清理流式临时文件...")
        try:
            os.remove(merged_wav_path)
        except:
            pass
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
                 platform: str = "default", tts_mode: str = "voice_design",
                 stability_prefix: str = ""):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.script_dir = script_dir or os.path.join(self.base_dir, "../novel_scripts")
        self.output_dir = output_dir or os.path.join(self.base_dir, "../../output")
        self.tts_engine = tts_engine
        self.tts_mode = tts_mode  # "clone" | "voice_design"

        # 自动选择默认模型：VoiceDesign 模式用 VoiceDesign 模型
        if qwen_model_path:
            self.qwen_model_path = qwen_model_path
        elif tts_mode == "voice_design":
            self.qwen_model_path = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
            print(f"[Synthesizer] VoiceDesign 模式，自动使用模型: {self.qwen_model_path}")
        else:
            self.qwen_model_path = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
        self.sfx_engine = sfx_engine
        self.bgm_engine = bgm_engine
        self.persist_intermediate_audio = persist_intermediate_audio
        self.platform = platform
        self.tts_mode = tts_mode
        self.stability_prefix = stability_prefix
        
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
        
        # ====== JSON 合法性校验 ======
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            error_msg = f"❌ 加载JSON失败，跳过本章: {json_file}\n   错误: {e}"
            print(error_msg)
            self._log_chapter_exception(json_file, error_msg)
            return None
        
        try:
            chapter_name = config["chapter"]
            # 章节目录/音频文件名与剧本 JSON 文件名保持一致
            chapter_clean_name = sanitize_chapter_dir_name(json_file)
            
            chapter_dir = os.path.join(self.output_dir, os.path.basename(os.path.dirname(json_file)), chapter_clean_name)
            output_ext = get_platform_profile(self.platform).output_format
            chapter_output_path = os.path.join(chapter_dir, f"{chapter_clean_name}.{output_ext}")
            
            if os.path.exists(chapter_output_path):
                print(f"✅ 整章音频已存在，跳过生成: {chapter_output_path}")
                return chapter_output_path
            # 同时检查分段的第1个文件（长章节会被切分为 _1/_2/_3 等）
            first_chunk_path = os.path.join(chapter_dir, f"{chapter_clean_name}_1.{output_ext}")
            if os.path.exists(first_chunk_path):
                print(f"✅ 整章音频已存在（分段），跳过生成: {first_chunk_path}")
                return first_chunk_path
        except Exception as e:
            error_msg = f"❌ 检查整章音频时发生错误，跳过本章: {json_file}\n   错误: {e}"
            print(error_msg)
            self._log_chapter_exception(json_file, error_msg)
            return None
        
        try:
            generator = AudioGenerator(
                json_path=json_file,
                output_dir=self.output_dir,
                tts_engine=self.tts_engine,
                qwen_model_path=self.qwen_model_path,
                sfx_engine=self.sfx_engine,
                bgm_engine=self.bgm_engine,
                persist_intermediate_audio=self.persist_intermediate_audio,
                platform=self.platform,
                tts_mode=self.tts_mode,
                stability_prefix=self.stability_prefix,
            )
            
            result = generator.generate_chapter_audio()
            
            # 显式释放 TTS 模型等资源，防止跨章节内存泄漏
            try:
                generator.audio_engine.release()
            except Exception as e:
                print(f"⚠️ 释放资源时出错（不影响已生成的音频）: {e}")
            del generator
            gc.collect()
            try:
                import torch
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                elif torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            gc.collect()
            _release_malloc_memory()
            
            return result
        except Exception as e:
            # 异常时也需释放可能已加载的 TTS 模型资源
            try:
                if 'generator' in locals() and hasattr(generator, 'audio_engine'):
                    generator.audio_engine.release()
                del generator
            except Exception:
                pass
            gc.collect()
            try:
                import torch
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                elif torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            _release_malloc_memory()
            
            error_msg = f"❌ 生成音频时发生错误，跳过本章: {json_file}\n   错误: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self._log_chapter_exception(json_file, error_msg)
            return None

    def _log_chapter_exception(self, json_file: str, error_msg: str):
        """记录章节处理异常到异常文件"""
        exceptions_file = os.path.join(self.output_dir, "chapter_exceptions.txt")
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {json_file}\n{error_msg}\n{'-'*60}\n"
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            with open(exceptions_file, "a", encoding="utf-8") as f:
                f.write(entry)
            print(f"📝 异常信息已写入: {exceptions_file}")
        except Exception as e:
            print(f"⚠️ 写入异常文件失败: {e}")

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
                if output_path is None:
                    print(f"⏭️ 跳过本章节，继续下一章...")
                    continue
                output_paths.append(output_path)
                
                # 每章结束后主动执行 GC，释放 MPS/CUDA 显存
                available_percent = self._check_memory_usage()
                print(f"\n📊 当前可用内存: {available_percent:.1f}%")
                
                if available_percent < 25.0:
                    self._garbage_collect()
                    # 重新读取可用内存百分比，展示回收效果
                    available_after = self._check_memory_usage()
                    print(f"📊 GC 后可用内存: {available_after:.1f}%")
        
        return output_paths

    def run(self, json_file: str = None, sort_mode: str = "pinyin") -> List[str]:
        """运行小说音频合成器"""
        if not self.check_environment():
            return []
        
        if json_file:
            output_path = self.process_novel(json_file)
            if output_path is None:
                print("\n❌ 处理失败，章节已被跳过。")
                return []
            output_paths = [output_path]
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
    parser.add_argument("--qwen-model-path", type=str, default=None, 
                        help="Qwen TTS模型路径（不指定时根据 --tts-mode 自动选择）")
    parser.add_argument("--persist-intermediate-audio", action="store_true",
                        help="保留单句配音/混音等中间音频文件，默认尽量减少落盘")
    parser.add_argument("--platform", type=str, default="ximalaya",
                        help="输出平台配置，如 default | ximalaya")
    parser.add_argument("--sort-mode", type=str, default="chapter",
                        help="排序模式: chapter(章节号排序，默认) | pinyin(拼音排序) | name(文件名排序)")
    parser.add_argument("--tts-mode", type=str, default="voice_design",
                        help="TTS 合成模式: voice_design(文字描述造音色，默认) | clone(克隆音频)")
    parser.add_argument("--stability-prefix", type=str, default="",
                        help="TTS 合成时添加起始稳定化前缀(如'话说，')，默认空字符串表示不添加")

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
        tts_mode=args.tts_mode,
        stability_prefix=args.stability_prefix,
    )
    
    if args.json_path:
        synthesizer.run(json_file=args.json_path, sort_mode=args.sort_mode)
    else:
        synthesizer.run(sort_mode=args.sort_mode)