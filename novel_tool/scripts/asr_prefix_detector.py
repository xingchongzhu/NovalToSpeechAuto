#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Transcription Module
音频转写模块，提供音频识别功能

支持模型:
- whisper.cpp (ggml-small/base/tiny)
- SenseVoice (FunASR) - 中文识别更准确

主要功能：
- 使用 whisper.cpp 或 SenseVoice 识别音频
- 检测前缀文本并返回时间位置
"""

import os
import shutil
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# 默认使用的ASR模型
DEFAULT_ASR_MODEL = os.environ.get("ASR_MODEL", "sensevoice")  # "whisper" 或 "sensevoice"

# SenseVoice 模型缓存
_sensevoice_model = None


def get_sensevoice_model():
    """获取或初始化 SenseVoice 模型"""
    global _sensevoice_model
    if _sensevoice_model is None:
        try:
            from funasr import AutoModel
            print("[Transcribe] 加载 SenseVoice 模型...")
            # 使用本地模型路径
            project_root = Path(__file__).resolve().parent.parent.parent
            model_path = project_root / "models" / "SenseVoiceSmall"
            _sensevoice_model = AutoModel(
                model=str(model_path),
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device="cpu",
                disable_update=True,
            )
        except Exception as e:
            print(f"[Transcribe] 加载 SenseVoice 失败: {e}")
            return None
    return _sensevoice_model


def transcribe_with_sensevoice(
    audio_path: str,
    language: str = "auto",
) -> Optional[Dict[str, Any]]:
    """
    使用 SenseVoice 识别音频
    
    Args:
        audio_path: 音频文件路径
        language: 语言代码，默认 "auto" 自动检测
        
    Returns:
        识别结果字典，包含 transcription 数组
    """
    model = get_sensevoice_model()
    if model is None:
        return None
    
    try:
        result = model.generate(
            input=audio_path,
            language=language,
            use_itn=True,
        )
        
        # 转换为标准格式
        transcription = []
        for res in result:
            text = res.get("text", "").strip()
            # 移除特殊标签
            text = text.replace("<|zh|>", "").replace("<|NEUTRAL|>", "")
            text = text.replace("<|Speech|>", "").replace("<|withitn|>", "")
            text = text.strip()
            
            # SenseVoice 不提供时间戳，使用简化格式
            transcription.append({
                "text": text,
                "offsets": {"from": 0, "to": 0},  # SenseVoice 不提供时间戳
            })
        
        return {"transcription": transcription}
        
    except Exception as e:
        print(f"[Transcribe] SenseVoice 识别失败: {e}")
        return None


def find_whisper_cpp() -> Optional[Path]:
    """查找 whisper-cli 可执行文件"""
    candidates = [
        "/opt/homebrew/bin/whisper-cli",
        "/usr/local/bin/whisper-cli",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            print(f"[Transcribe] ✓ 找到 whisper-cli: {candidate}")
            return Path(candidate)
    found = shutil.which("whisper-cli")
    if found:
        print(f"[Transcribe] ✓ 找到 whisper-cli (which): {found}")
        return Path(found)
    print("[Transcribe] ✗ whisper-cli 未找到，尝试过的路径:", candidates)
    return None


def get_whisper_model_path(project_root: Optional[Path] = None) -> str:
    """获取 whisper.cpp 模型路径，优先使用已下载的模型"""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent
    model_dir = project_root / "models"
    
    # 优先查找已存在的模型（small > base > tiny）
    for model_name in ["ggml-small.bin", "ggml-base.bin", "ggml-tiny.bin"]:
        model_path = model_dir / model_name
        if model_path.exists():
            return str(model_path)
    
    # 如果没有找到任何模型，自动下载 tiny 模型
    model_path = model_dir / "ggml-tiny.bin"
    model_dir.mkdir(parents=True, exist_ok=True)
    url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
    print(f"[Transcribe] ⬇️ 下载 Whisper tiny 模型...")
    
    import requests
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(model_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return str(model_path)


def transcribe_with_whisper(
    audio_path: str,
    language: str = "zh",
    model_path: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    使用 whisper.cpp 识别音频
    
    Args:
        audio_path: 音频文件路径
        language: 语言代码，默认 "zh"
        model_path: 指定模型路径，None 则自动查找
        project_root: 项目根目录
        
    Returns:
        识别结果字典，包含 transcription 数组，失败返回 None
    """
    whisper_bin = find_whisper_cpp()
    if not whisper_bin:
        print("[Transcribe] ⚠️ whisper-cli 未找到")
        return None
    
    if model_path is None:
        model_path = get_whisper_model_path(project_root)
    
    # 使用唯一输出文件名避免缓存冲突
    import uuid
    output_base = audio_path.replace('.wav', '').replace('.mp3', '') + f"_{uuid.uuid4().hex[:8]}"

    # 清理可能存在的旧缓存文件
    json_path = output_base + ".json"
    if os.path.exists(json_path):
        os.remove(json_path)

    cmd = [
        str(whisper_bin),
        "-m", model_path,
        "-f", audio_path,
        "-l", language,
        "-oj",
        "-of", output_base,
        "-p", "2",
        "-bs", "1",
        "-nf",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='ignore')[:200]
            print(f"[Transcribe] ✗ whisper-cli 失败: {stderr}")
            return None

        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[Transcribe] ✓ 识别成功，共 {len(data.get('transcription', []))} 段")
                return data
        else:
            print(f"[Transcribe] ✗ 输出文件不存在: {json_path}")
    except Exception as e:
        print(f"[Transcribe] ✗ 识别异常: {e}")

    return None


def transcribe_audio(
    audio_path: str,
    language: str = "zh",
    model_path: Optional[str] = None,
    project_root: Optional[Path] = None,
    asr_model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    识别音频（自动选择模型）
    
    Args:
        audio_path: 音频文件路径
        language: 语言代码，默认 "zh"
        model_path: 指定模型路径（whisper 用），None 则自动查找
        project_root: 项目根目录
        asr_model: 指定 ASR 模型，None 则使用环境变量或默认 "sensevoice"
                 可选: "whisper", "sensevoice"
        
    Returns:
        识别结果字典，包含 transcription 数组
    """
    model = asr_model or DEFAULT_ASR_MODEL
    
    if model == "sensevoice":
        print(f"[Transcribe] 使用 SenseVoice 识别...")
        return transcribe_with_sensevoice(audio_path, language)
    else:
        print(f"[Transcribe] 使用 Whisper 识别...")
        return transcribe_with_whisper(audio_path, language, model_path, project_root)


def detect_prefix_end_time(
    audio_data: bytes,
    sample_rate: int,
    prefix_text: str = "话说，",
    search_seconds: float = 3.0,
    project_root: Optional[Path] = None,
    asr_model: Optional[str] = None,
) -> Tuple[float, bool]:
    """
    检测音频中前缀文本的结束时间
    
    Args:
        audio_data: 音频数据 (int16 bytes)
        sample_rate: 采样率
        prefix_text: 要检测的前缀文本
        search_seconds: 只检测前 N 秒
        project_root: 项目根目录
        asr_model: 指定 ASR 模型
        
    Returns:
        (end_time_seconds, found)
        - end_time_seconds: 前缀结束时间（秒），未找到返回 0
        - found: 是否找到前缀
    """
    import numpy as np
    
    # 只取前 N 秒
    max_samples = int(sample_rate * search_seconds)
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    search_audio = audio_array[:max_samples]
    
    # 保存为临时文件
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name
        
        # 使用 wave 模块写入
        import wave
        with wave.open(tmp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(search_audio.tobytes())
        
        # 识别
        result = transcribe_audio(tmp_path, project_root=project_root, asr_model=asr_model)
        if not result:
            return 0.0, False
        
        # 解析识别结果，查找前缀
        transcription = result.get("transcription", [])
        print(f"[Transcribe] 🔍 查找前缀 '{prefix_text}'，识别结果共 {len(transcription)} 段")
        prefix_end_ms = 0

        # 构建前缀匹配列表（支持简体、繁体、带标点、ASR误识别变体）
        prefix_variants = [prefix_text]
        if prefix_text == "话说，":
            # 包括：简体、繁体、带各种标点、ASR误识别变体、单字匹配
            prefix_variants = [
                "话说，", "話說，", "话说", "話說",
                "话说:", "話說:", "话说：", "話說：",
                "他说", "他說", "她说", "她說",  # ASR常见误识别
                "话", "話", "说", "說",  # 单字匹配（只检测开头）
            ]
        elif len(prefix_text) >= 2:
            prefix_variants = [prefix_text, prefix_text.replace("话", "話").replace("说", "說")]

        for seg in transcription:
            text = seg.get("text", "").strip()
            offsets = seg.get("offsets", {})
            start_ms = offsets.get("from", 0)
            end_ms_seg = offsets.get("to", 0)
            print(f"[Transcribe]   文本: '{text}' | 时间: {start_ms}-{end_ms_seg}ms")

            # 只检测前2秒内的文本（前缀通常在前0.5-1秒内）
            if start_ms > 2000:
                continue

            # 检查是否匹配任意前缀变体
            matched = False
            for variant in prefix_variants:
                if variant in text or text.startswith(variant[:2]):
                    matched = True
                    end_ms = end_ms_seg
                    print(f"[Transcribe]   ✓ 匹配前缀 '{variant}'! 结束时间: {end_ms}ms")
                    if end_ms > prefix_end_ms:
                        prefix_end_ms = end_ms
                    break

        if prefix_end_ms > 100:  # 至少 100ms
            # 限制最大裁剪时长，避免过度裁剪
            MAX_PREFIX_DURATION_MS = 1200  # 最大1.2秒
            if prefix_end_ms > MAX_PREFIX_DURATION_MS:
                print(f"[Transcribe] ⚠️ 识别到的前缀时长过长({prefix_end_ms}ms)，限制为{MAX_PREFIX_DURATION_MS}ms")
                prefix_end_ms = MAX_PREFIX_DURATION_MS
            end_time = prefix_end_ms / 1000.0
            print(f"[Transcribe] ✓ 找到前缀结束时间: {end_time:.2f}s")
            return end_time, True
        else:
            print(f"[Transcribe] ✗ 未找到前缀 '{prefix_text}'")

    except Exception as e:
        print(f"[Transcribe] ✗ 检测前缀异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                # 清理生成的 json 文件
                json_path = tmp_path.replace('.wav', '.json')
                if os.path.exists(json_path):
                    os.remove(json_path)
            except:
                pass
    
    return 0.0, False


def detect_and_trim_prefix(
    audio_array: 'np.ndarray',
    sample_rate: int,
    prefix_text: str = "话说，",
    padding_ms: float = 50.0,
    project_root: Optional[Path] = None,
    search_seconds: float = 3.0,
    asr_model: Optional[str] = None,
) -> 'np.ndarray':
    """
    检测并裁剪音频中的前缀（支持渐进式裁剪避免过度裁剪）

    Args:
        audio_array: 音频数据 (float32 numpy array, -1.0 ~ 1.0)
        sample_rate: 采样率
        prefix_text: 要检测的前缀文本
        padding_ms: 保留的安全边距（毫秒）
        project_root: 项目根目录
        search_seconds: 只检测前 N 秒，默认 3.0 秒
        asr_model: 指定 ASR 模型

    Returns:
        裁剪后的音频数组
    """
    import numpy as np
    import wave
    import tempfile
    import os

    if not prefix_text or len(audio_array) < sample_rate * 0.1:
        return audio_array

    # 渐进式裁剪：多次检测避免过度裁剪
    max_iterations = 3  # 最多尝试3次
    total_trimmed_samples = 0
    original_array = audio_array.copy()

    for iteration in range(max_iterations):
        # 直接使用临时文件
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name

            # 将当前音频写入 wav 文件
            audio_int16 = (np.clip(audio_array, -1.0, 1.0) * 32767).astype(np.int16)
            max_samples = int(sample_rate * search_seconds)
            audio_int16 = audio_int16[:max_samples]

            if audio_int16.ndim == 1:
                n_channels = 1
            else:
                n_channels = audio_int16.shape[1]
            audio_bytes = audio_int16.tobytes()

            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(n_channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)

            # 识别
            result = transcribe_audio(tmp_path, project_root=project_root, asr_model=asr_model)
            if not result:
                break

            transcription = result.get("transcription", [])
            if iteration == 0:
                print(f"[Transcribe] 🔍 查找前缀 '{prefix_text}'，识别结果共 {len(transcription)} 段")

            # 构建前缀匹配列表
            prefix_variants = [prefix_text]
            if prefix_text == "话说，":
                prefix_variants = [
                    "话说，", "話說，", "话说", "話說",
                    "话说:", "話說:", "话说：", "話說：",
                    "他说", "他說", "她说", "她說",
                    "话", "話", "说", "說",
                ]

            prefix_found = False
            for seg in transcription:
                text = seg.get("text", "").strip()
                offsets = seg.get("offsets", {})
                start_ms = offsets.get("from", 0)
                end_ms_seg = offsets.get("to", 0)

                if iteration == 0:
                    print(f"[Transcribe]   文本: '{text}' | 时间: {start_ms}-{end_ms_seg}ms")

                if start_ms > 2000:
                    continue

                for variant in prefix_variants:
                    if variant in text or text.startswith(variant[:2]):
                        # SenseVoice 无时间戳，使用保守估算（0.6秒）
                        if end_ms_seg == 0:
                            estimated_duration = 600  # 保守估算 0.6 秒
                            end_ms = estimated_duration
                            print(f"[Transcribe]   ✓ 第{iteration+1}次匹配 '{variant}'! 估算: {end_ms}ms")
                        else:
                            end_ms = end_ms_seg
                            print(f"[Transcribe]   ✓ 第{iteration+1}次匹配 '{variant}'! 结束时间: {end_ms}ms")

                        # 裁剪（减去安全边距）
                        trim_seconds = max(0, end_ms / 1000.0 - padding_ms / 1000.0)
                        trim_samples = int(trim_seconds * sample_rate)

                        if trim_samples < len(audio_array):
                            audio_array = audio_array[trim_samples:]
                            total_trimmed_samples += trim_samples
                            prefix_found = True
                            print(f"[Transcribe]   🔪 本次裁剪: {trim_seconds:.2f}s, 累计裁剪: {total_trimmed_samples/sample_rate:.2f}s")
                        break

                if prefix_found:
                    break

            if not prefix_found:
                if iteration == 0:
                    print(f"[Transcribe] ✗ 未找到前缀 '{prefix_text}'")
                else:
                    print(f"[Transcribe] ✓ 前缀已完全去除，共裁剪 {total_trimmed_samples/sample_rate:.2f}s")
                break

        except Exception as e:
            print(f"[Transcribe] ✗ 检测前缀异常: {e}")
            break
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    json_path = tmp_path.replace('.wav', '.json')
                    if os.path.exists(json_path):
                        os.remove(json_path)
                except:
                    pass

    if total_trimmed_samples > 0:
        print(f"[Transcribe] 🔪 总计裁剪前缀: {total_trimmed_samples/sample_rate:.2f}s")

    return audio_array


if __name__ == "__main__":
    # 测试代码
    import sys
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        print(f"测试识别: {audio_file}")
        
        # 测试两种模型
        print("\n" + "="*60)
        print("SenseVoice 识别:")
        print("="*60)
        result1 = transcribe_audio(audio_file, asr_model="sensevoice")
        if result1:
            for seg in result1.get('transcription', []):
                print(f"  {seg.get('text', '')}")
        
        print("\n" + "="*60)
        print("Whisper 识别:")
        print("="*60)
        result2 = transcribe_audio(audio_file, asr_model="whisper")
        if result2:
            for seg in result2.get('transcription', []):
                print(f"  {seg.get('text', '')}")
        else:
            print("  识别失败")
