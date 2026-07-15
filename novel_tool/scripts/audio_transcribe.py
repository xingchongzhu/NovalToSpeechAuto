#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Transcription Tool — whisper.cpp + faster-whisper 双引擎转写工具

主引擎: whisper.cpp (C++ 原生, Apple Silicon Metal GPU 加速, 速度最快)
备用引擎: faster-whisper (Python/CTranslate2, 通用兼容, 逐字时间轴)

Features:
- 主引擎 whisper.cpp → 段级时间轴, Metal GPU 极速
- 备用引擎 faster-whisper → 逐字级时间轴 (word-level timestamps)
- 目录输入自动批量处理
- 多格式输出: JSON, SRT, TXT
- URL 音频下载
- 自动检测 whisper.cpp 是否可用, 不可用时回退 faster-whisper

依赖:
  brew install whisper-cpp                          # 主引擎
  pip install faster-whisper requests torch         # 备用引擎

Usage:
    python audio_transcribe.py -i audio.mp3
    python audio_transcribe.py -i ./配音/
    python audio_transcribe.py -i ./配音/ -o ./output_json/
    python audio_transcribe.py -i audio.mp3 -o custom.json
    python audio_transcribe.py -i https://example.com/audio.mp3
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma", ".webm", ".mka"}

# ── whisper.cpp config ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models"
WHISPER_CPP_MODELS = {
    "tiny":      DEFAULT_MODEL_DIR / "ggml-tiny.bin",
    "base":      DEFAULT_MODEL_DIR / "ggml-base.bin",
    "small":     DEFAULT_MODEL_DIR / "ggml-small.bin",
    "medium":    DEFAULT_MODEL_DIR / "ggml-medium.bin",
    "large-v3":  DEFAULT_MODEL_DIR / "ggml-large-v3.bin",
}
WHISPER_CPP_MODEL_URLS = {
    "tiny":      "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    "base":      "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "small":     "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "medium":    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    "large-v3":  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
}


# ═══════════════════════════════════════════════════════════
#  engine detection
# ═══════════════════════════════════════════════════════════

def find_whisper_cpp() -> Optional[Path]:
    """Find whisper-cli binary."""
    for candidate in [
        "/opt/homebrew/bin/whisper-cli",
        "/usr/local/bin/whisper-cli",
    ]:
        if os.path.isfile(candidate):
            return Path(candidate)
    # fall back to PATH search
    found = shutil.which("whisper-cli")
    return Path(found) if found else None


def ensure_whisper_cpp_model(model_name: str) -> Path:
    """Return path to ggml model file, downloading if needed."""
    model_path = WHISPER_CPP_MODELS.get(model_name)
    if model_path is None:
        raise ValueError(f"未知模型: {model_name}. 可选: {list(WHISPER_CPP_MODELS.keys())}")
    if model_path.exists():
        return model_path

    url = WHISPER_CPP_MODEL_URLS.get(model_name)
    if not url:
        raise RuntimeError(f"模型 {model_name} 无下载地址")

    model_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"⬇️  下载 whisper.cpp 模型 ({model_name}): {url}")
    import requests

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(model_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  下载中... {pct}% ({downloaded//1048576}MB/{total//1048576}MB)", end="")
            print()
    return model_path


# ═══════════════════════════════════════════════════════════
#  whisper.cpp engine
# ═══════════════════════════════════════════════════════════

def transcribe_whisper_cpp(
    audio_path: Path,
    output_path: Path,
    model_name: str,
    language: str,
    output_format: str,
    verbose: bool,
) -> dict:
    """Transcribe using whisper.cpp CLI, then convert JSON to unified format."""
    whisper_bin = find_whisper_cpp()
    if not whisper_bin:
        raise RuntimeError("whisper-cli 未找到, 请先运行: brew install whisper-cpp")

    model_path = ensure_whisper_cpp_model(model_name)

    # whisper-cli args — 速度优化: beam_size=1, 关闭 fallback, 词边界分句
    out_base = output_path.with_suffix("")  # whisper.cpp appends extension itself
    cmd = [
        str(whisper_bin),
        "-m", str(model_path),
        "-f", str(audio_path),
        "-l", language,
        "-oj",                         # JSON output
        "-of", str(out_base),
        str(os.cpu_count() or 4),
        "-p", str(os.cpu_count() or 4),  # 处理器数
        "-bs", "1",                      # beam_size=1 贪婪解码(速度 3-5x)
        "-nf",                           # 关闭 temperature fallback
        "-sow",                          # 词边界分句(更快的分段)
        "--print-progress",              # 实时进度日志
    ]

    if verbose:
        print(f"  ⚡ whisper.cpp: {model_path.name}")

    # ── 打印进度日志 ──
    if verbose:
        # 估算耗时：small model 约 0.05x 实时，medium 约 0.1x
        import wave
        try:
            with wave.open(str(audio_path), 'rb') as wf:
                audio_dur = wf.getnframes() / wf.getframerate()
            est_seconds = max(0.3, audio_dur * 0.05)
            print(f"  🔄 转写中... (音频 {audio_dur:.0f}s, 预计 {est_seconds:.0f}s)")
        except Exception:
            print(f"  🔄 转写中...")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"whisper.cpp 错误:\n{proc.stderr}")

    if verbose:
        segs = 0
        try:
            with open(Path(str(out_base) + ".json"), "r", encoding="utf-8") as f:
                segs = len(json.load(f).get("transcription", []))
        except Exception:
            pass
        print(f"  ✅ 转写完成 ({segs} 段)")

    # whisper.cpp output is at out_base.json
    raw_json_path = Path(str(out_base) + ".json")
    if not raw_json_path.exists():
        raise RuntimeError(f"whisper.cpp 未生成输出文件: {raw_json_path}")

    # Parse whisper.cpp JSON → unified format
    with open(raw_json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    transcription = raw.get("transcription", [])
    segments = []
    full_text = ""
    srt_lines = []

    for i, seg in enumerate(transcription, 1):
        offsets = seg.get("offsets", {})
        start_ms = offsets.get("from", 0)
        end_ms = offsets.get("to", 0)
        start_s = start_ms / 1000.0
        end_s = end_ms / 1000.0
        text = seg.get("text", "").strip()

        segments.append({"id": i, "start": start_s, "end": end_s, "text": text})
        full_text += text

        srt_lines.append(str(i))
        srt_lines.append(f"{_fmt_srt(start_s)} --> {_fmt_srt(end_s)}")
        srt_lines.append(text)
        srt_lines.append("")

    result = {
        "file": str(audio_path),
        "engine": "whisper.cpp",
        "model": model_name,
        "language": raw.get("result", {}).get("language", language),
        "language_probability": raw.get("result", {}).get("language_probability"),
        "duration_seconds": round((segments[-1]["end"] if segments else 0), 2),
        "full_text": full_text,
        "segments": segments,
    }

    # Write unified JSON (overwrite raw whisper.cpp output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Write SRT if requested
    if output_format == "srt":
        srt_path = output_path.with_suffix(".srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
    elif output_format == "txt":
        txt_path = output_path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)

    if verbose:
        print(f"  📄 输出: {output_path} ({len(segments)} 段)")

    return result


# ═══════════════════════════════════════════════════════════
#  faster-whisper fallback engine
# ═══════════════════════════════════════════════════════════

def transcribe_faster_whisper(
    audio_path: Path,
    output_path: Path,
    model_name: str,
    language: str,
    output_format: str,
    verbose: bool,
) -> dict:
    """Fallback: faster-whisper with word-level timestamps."""
    from faster_whisper import WhisperModel

    if verbose:
        print(f"  🐍 faster-whisper: {model_name}")

    model = WhisperModel(model_name, device="auto", compute_type="auto",
                         num_workers=2, cpu_threads=os.cpu_count() or 4)
    segments_result, info = model.transcribe(
        str(audio_path), language=language if language != "auto" else None,
        beam_size=1, word_timestamps=True,
    )
    segments_list = list(segments_result)

    full_text = ""
    result_segments = []
    words_list = []
    srt_lines = []

    for i, seg in enumerate(segments_list, 1):
        text = seg.text.strip()
        full_text += text
        result_segments.append({"id": i, "start": seg.start, "end": seg.end, "text": text})

        if seg.words:
            for w in seg.words:
                words_list.append({
                    "word": w.word, "start": round(w.start, 3),
                    "end": round(w.end, 3), "probability": round(w.probability, 4),
                })

        srt_lines.append(str(i))
        srt_lines.append(f"{_fmt_srt(seg.start)} --> {_fmt_srt(seg.end)}")
        srt_lines.append(text)
        srt_lines.append("")

    result = {
        "file": str(audio_path),
        "engine": "faster-whisper",
        "model": model_name,
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "duration_seconds": round(info.duration, 2),
        "full_text": full_text,
        "segments": result_segments,
        "words": words_list,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if output_format == "srt":
        srt_path = output_path.with_suffix(".srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
    elif output_format == "txt":
        txt_path = output_path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)

    if verbose:
        print(f"  📄 输出: {output_path} ({len(result_segments)} 段, {len(words_list)} 词)")

    return result


# ═══════════════════════════════════════════════════════════
#  helpers
# ═══════════════════════════════════════════════════════════

def _fmt_srt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def collect_audio_files(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        files = sorted(p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES)
        if not files:
            raise FileNotFoundError(f"目录中未找到音频文件: {input_path}")
        return files
    if input_path.is_file():
        return [input_path]
    raise FileNotFoundError(f"路径不存在: {input_path}")


def download_audio(url: str, output_dir: Path) -> Path:
    import re
    import requests

    output_dir.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    filename = None
    cd = resp.headers.get("Content-Disposition", "")
    match = re.search(r'filename[^;=\n]*=["\']?([^"\'\n]+)["\']?', cd)
    if match:
        filename = match.group(1)
    if not filename:
        filename = os.path.basename(url.split("?")[0])
    if not filename or not any(filename.lower().endswith(suf) for suf in AUDIO_SUFFIXES):
        filename = "downloaded_audio.mp3"
    filepath = output_dir / filename
    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return filepath


# ═══════════════════════════════════════════════════════════
#  main
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="whisper.cpp + faster-whisper 双引擎音频转文本工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--input", required=True, help="音频文件路径 / 目录 / URL")
    parser.add_argument("-o", "--output", default=None,
                        help="输出路径: 单文件=JSON路径, 目录=输出目录 (默认: 音频同目录同名)")
    parser.add_argument("-m", "--model", default="small",
                        help="模型: tiny|base|small|medium|large-v3 (默认: small)")
    parser.add_argument("-l", "--language", default="zh", help="音频语言 (默认: zh, auto=自动)")
    parser.add_argument("-f", "--format", default="json", choices=["json", "srt", "txt"],
                        help="输出格式 (默认: json)")
    parser.add_argument("--force-faster-whisper", action="store_true",
                        help="强制使用 faster-whisper (含逐字时间轴)")
    parser.add_argument("--force", action="store_true",
                        help="强制重新转写，即使 JSON 已存在")
    parser.add_argument("--download-dir", default=None, help="URL 下载临时目录")
    parser.add_argument("-q", "--quiet", action="store_true", help="静默模式")
    args = parser.parse_args()

    # ── Engine selection ──
    whisper_cpp_bin = find_whisper_cpp()
    use_whisper_cpp = whisper_cpp_bin is not None and not args.force_faster_whisper

    if not args.quiet:
        if use_whisper_cpp:
            print(f"⚡ 主引擎: whisper.cpp ({whisper_cpp_bin}) + Apple Metal GPU")
        else:
            print("🐍 引擎: faster-whisper (含逐字时间轴)")
        print(f"🧠 模型: {args.model}")

    # ── Input files ──
    input_val = args.input.strip()
    tmp_dir = None
    if input_val.startswith(("http://", "https://")):
        if not args.quiet:
            print(f"⬇️  下载音频: {input_val}")
        tmp_dir = Path(args.download_dir) if args.download_dir else Path(tempfile.mkdtemp(prefix="whisper_dl_"))
        audio_files = [download_audio(input_val, tmp_dir)]
    else:
        audio_files = collect_audio_files(Path(input_val))

    if not args.quiet:
        print(f"📂 待处理: {len(audio_files)} 个音频文件\n")

    # ── Output dir for batch ──
    output_dir_for_batch = None
    if args.output and len(audio_files) > 1:
        output_dir_for_batch = Path(args.output)
        output_dir_for_batch.mkdir(parents=True, exist_ok=True)

    # ── Process ──
    total_start = time.time()
    success_count = 0
    fail_count = 0

    for idx, audio_path in enumerate(audio_files, 1):
        if not args.quiet:
            print(f"[{idx}/{len(audio_files)}] 🎧 {audio_path.name}")

        try:
            if output_dir_for_batch:
                output_path = output_dir_for_batch / (audio_path.stem + ".json")
            elif args.output and len(audio_files) == 1:
                output_path = Path(args.output)
            else:
                output_path = audio_path.parent / (audio_path.stem + ".json")

            # ── Skip if output already exists ──
            if output_path.exists() and not args.force:
                if not args.quiet:
                    print(f"  ⏭️  跳过 (已存在): {output_path.name}")
                success_count += 1
                continue

            if use_whisper_cpp:
                result = transcribe_whisper_cpp(
                    audio_path, output_path, args.model, args.language,
                    args.format, verbose=not args.quiet,
                )
            else:
                result = transcribe_faster_whisper(
                    audio_path, output_path, args.model, args.language,
                    args.format, verbose=not args.quiet,
                )

            if not args.quiet:
                engine = result.get("engine", "?")
                segs = len(result.get("segments", []))
                words = result.get("words")
                summary = f"  ✅ {engine} | {segs} 段"
                if words is not None:
                    summary += f", {len(words)} 词"
                print(summary)
            success_count += 1
        except Exception as e:
            print(f"  ❌ 失败: {e}", file=sys.stderr)
            fail_count += 1

    elapsed = time.time() - total_start
    if not args.quiet:
        print(f"\n{'─' * 40}")
        print(f"✅ 完成: {success_count} 成功, {fail_count} 失败 | 耗时: {elapsed:.1f}s")

    if tmp_dir and not args.download_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
