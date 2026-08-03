#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Novel Audio Visual Tool - Backend Server
提供剧本管理、音频试听、生成控制的 REST API + SSE 实时日志
"""

import http.server
import socketserver
import json
import os
import sys
import hashlib
import tempfile
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import queue
from pathlib import Path

# 添加脚本目录到 sys.path 以便导入音频模块
_script_dir_abs = str(Path(__file__).resolve().parent.parent / "novel_tool" / "scripts")
sys.path.insert(0, _script_dir_abs)

# ======================== 路径配置 ========================
BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = BASE_DIR / "novel_tool" / "scripts"
SCRIPT_BASE = BASE_DIR / "novel_tool" / "novel_scripts"
SCRIPT_RAW_BASE = BASE_DIR / "novel_tool" / "novel_scripts_raw"
CLONE_AUDIO_DIR = BASE_DIR / "clone-audio"
OUTPUT_DIR = BASE_DIR / "output"

PORT = 8088

# ======================== 生成任务管理 ========================
_gen_tasks: dict = {}
_gen_lock = threading.Lock()
_log_queues: dict = {}
_task_counter = 0

# ======================== 声音实验室（TTS / SFX / BGM）=======================

LAB_OUTPUT_DIR = BASE_DIR / "output" / "_lab"
os.makedirs(LAB_OUTPUT_DIR, exist_ok=True)

_tts_engine = None

def _get_tts_engine():
    global _tts_engine
    if _tts_engine is None:
        from audio_processing_module import AudioEngine
        _tts_engine = AudioEngine()
    return _tts_engine


def synthesize_tts(text: str, voice: str, speed: str, volume: str, pitch: str, instruct: str = "") -> str:
    """TTS 合成，返回相对于 BASE_DIR 的输出路径"""
    from audio_processing_module import VoiceParams
    h = hashlib.md5(f"{text}{voice}{speed}{volume}{pitch}{instruct}".encode()).hexdigest()[:12]
    out_path = LAB_OUTPUT_DIR / f"tts_{h}.wav"
    if out_path.exists():
        return str(out_path.relative_to(BASE_DIR))
    engine = _get_tts_engine()
    params = VoiceParams(text=text, role="lab", role_voice=voice,
                         speed=speed, volume=volume, pitch=pitch,
                         instruct=instruct or None)
    audio = engine.text_to_speech(params)
    audio.export(str(out_path), format="wav")
    return str(out_path.relative_to(BASE_DIR))


def synthesize_vd_preview(vd_prompt: str, text: str = "我是{角色}，这是我的声音样本，欢迎收听蜀山剑侠传有声剧，给你带来不一样的听觉盛宴，感谢收听。", char_name: str = "") -> str:
    """VoiceDesign 试听合成，返回相对于 BASE_DIR 的输出路径"""
    from audio_processing_module import VoiceParams, AudioEngine
    # 文件名：优先用角色名，否则 fallback 到 hash
    if char_name.strip():
        safe_name = char_name.replace('/', '_').replace('\\', '_').replace(':', '_')
        filename = f"vd_{safe_name}.wav"
    else:
        h = hashlib.md5(f"vd_{vd_prompt}_{text}".encode()).hexdigest()[:12]
        filename = f"vd_{h}.wav"
    out_path = LAB_OUTPUT_DIR / filename
    # 同名已存在则跳过合成，直接返回缓存（仅当 char_name 非空时生效）
    if out_path.exists():
        return str(out_path.relative_to(BASE_DIR))

    tid = filename.replace('.wav', '')
    q = _log_queues.get(tid, queue.Queue())

    # 取消上一个正在进行的 VD 合成
    _cancel_vd_synthesis()

    q.put({"type": "log", "data": f"🎤 VoiceDesign 合成中... | Prompt: {vd_prompt[:60]}..."})
    
    engine = AudioEngine(
        temp_dir=str(LAB_OUTPUT_DIR),
        tts_engine="qwen3-tts",
        tts_mode="voice_design",
        qwen_model_path="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    )
    params = VoiceParams(text=text, role="vd_preview", role_voice="",
                         speed="0%", volume="0%", pitch="0Hz",
                         tts_mode="voice_design",
                         voice_design_prompt=vd_prompt)

    # 设置当前合成任务
    _vd_current_cancel = threading.Event()
    _vd_current_thread = threading.current_thread()

    try:
        audio = _do_vd_synthesis(engine, params, q, _vd_current_cancel)
        audio.export(str(out_path), format="wav")
        dur = len(audio) / 1000.0
        q.put({"type": "log", "data": f"✓ VoiceDesign 合成完成 | 时长 {dur:.1f}s"})
        q.put({"type": "done", "data": str(out_path.relative_to(BASE_DIR))})
        return str(out_path.relative_to(BASE_DIR))
    except Exception as e:
        if "被取消" in str(e):
            q.put({"type": "error", "data": f"⏹ 已取消"})
        else:
            q.put({"type": "error", "data": str(e)})
        raise
    finally:
        _vd_current_cancel = None
        _vd_current_thread = None


_vd_current_cancel = None  # threading.Event for cancellation
_vd_current_thread = None  # 当前合成线程


def _cancel_vd_synthesis():
    """取消正在进行的 VoiceDesign 合成"""
    global _vd_current_cancel, _vd_current_thread
    if _vd_current_cancel is not None:
        _vd_current_cancel.set()
        _vd_current_cancel = None
        _vd_current_thread = None


def _do_vd_synthesis(engine, params, log_q, cancel_event):
    """在独立线程执行 VoiceDesign 合成，支持取消"""
    import threading as _th
    result_holder = {}
    error_holder = {}

    def _run():
        try:
            result_holder["audio"] = engine.text_to_speech(params)
        except Exception as e:
            error_holder["error"] = e

    t = _th.Thread(target=_run, daemon=True)
    t.start()
    dots = 0
    while t.is_alive():
        if cancel_event.is_set():
            log_q.put({"type": "log", "data": "⏹ 正在取消合成..."})
            # 线程是 daemon，主线程结束时会被强制终止
            raise RuntimeError("VoiceDesign 合成被取消")
        t.join(timeout=3)
        dots += 1
        log_q.put({"type": "log", "data": f"  生成中... 已耗时 {dots * 3}s"})

    t.join()
    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder["audio"]


def synthesize_sfx(prompt: str, duration: float) -> str:
    """音效生成，返回输出路径"""
    from woosh_generate_audio import generate_audio
    h = hashlib.md5(f"{prompt}{duration}".encode()).hexdigest()[:12]
    out_path = str(LAB_OUTPUT_DIR / f"sfx_{h}.wav")
    if os.path.exists(out_path):
        return str(Path(out_path).relative_to(BASE_DIR))
    result = generate_audio(prompt=prompt, duration=duration, output_path=out_path)
    if result:
        return str(Path(result).relative_to(BASE_DIR))
    raise RuntimeError("SFX 生成失败")


def synthesize_bgm(prompt: str, duration: float) -> str:
    """背景音生成，返回输出路径"""
    from stable_audio3_background_generate_audio import generate_audio_batch
    h = hashlib.md5(f"{prompt}{duration}".encode()).hexdigest()[:12]
    out_path = str(LAB_OUTPUT_DIR / f"bgm_{h}.wav")
    if os.path.exists(out_path):
        return str(Path(out_path).relative_to(BASE_DIR))
    # 如果输出路径缺少 .wav，模块会自动补后缀
    results = generate_audio_batch([{"prompt": prompt, "duration": duration, "output_path": out_path}])
    if results and results[0]:
        return str(Path(results[0]).relative_to(BASE_DIR))
    raise RuntimeError("BGM 生成失败")


# ======================== 单音频重新生成 ========================

def _find_script_json(novel_name: str, chapter_name: str):
    """根据 output 的小说名+章节名，反查剧本 JSON 文件路径"""
    # 候选剧本目录（小说剧本 / 小说剧本原稿下的各子目录）
    search_roots = [SCRIPT_BASE / novel_name]
    if SCRIPT_RAW_BASE.exists():
        for sub in _list_dir_safe(SCRIPT_RAW_BASE):
            if sub.is_dir():
                search_roots.append(sub)
                for s2 in _list_dir_safe(sub):
                    if s2.is_dir():
                        search_roots.append(s2)

    # 从章节名提取章节号
    ch_key = _chapter_sort_key(chapter_name)
    ch_num = ch_key[1] if ch_key[0] == 0 else None

    # 1. 优先精确匹配文件名（去扩展名 == 章节名）
    for root in search_roots:
        if not root.exists():
            continue
        exact = root / f"{chapter_name}.json"
        if exact.exists():
            return exact

    # 2. 按章节号匹配
    if ch_num is not None:
        for root in search_roots:
            if not root.exists():
                continue
            for f in _list_dir_safe(root):
                if f.is_file() and f.suffix == '.json':
                    fk = _chapter_sort_key(f.stem)
                    if fk[0] == 0 and fk[1] == ch_num:
                        return f
    return None


def get_regen_info(audio_rel_path: str):
    """根据音频相对路径，解析出对应的剧本文本信息（用于展示）"""
    p = Path(audio_rel_path)
    parts = p.parts  # e.g. ('output', '蜀山剑侠传_json', '第55回', '配音', 'voice_line_49.wav')
    if len(parts) < 4 or parts[0] != 'output':
        return {"error": "无法解析路径"}
    novel_name = parts[1]
    chapter_name = parts[2]
    kind = parts[3] if len(parts) >= 5 else 'final'
    stem = p.stem
    line_id = _extract_line_id(stem)

    json_path = _find_script_json(novel_name, chapter_name)
    if not json_path:
        return {"error": f"未找到对应剧本: {novel_name}/{chapter_name}", "novel": novel_name, "chapter": chapter_name}

    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
    except Exception as e:
        return {"error": f"剧本解析失败: {e}"}

    info = {"novel": novel_name, "chapter": chapter_name, "kind": kind,
            "line_id": line_id, "script": str(json_path.relative_to(BASE_DIR))}

    lines = data.get("data", [])
    if kind in ('配音', '混音') and line_id is not None and line_id < len(lines):
        line = lines[line_id]
        voice = line.get("api", {}).get("voice", {})
        info["role"] = line.get("role", "")
        info["text"] = voice.get("text", "")
        info["role_voice"] = voice.get("role_voice", "")
        info["speed"] = voice.get("speed", "+0%")
        info["volume"] = voice.get("volume", "+0%")
        info["pitch"] = voice.get("pitch", "+0Hz")
        info["instruct"] = voice.get("instruct", "")
        info["regen_type"] = "voice"
    elif kind == '音效' and line_id is not None and line_id < len(lines):
        effects = lines[line_id].get("api", {}).get("effects", [])
        # 从文件名匹配音效名: effect_line_{名称}_{N}
        m = re.match(r'effect_line_(.+)_\d+$', stem)
        eff_name = m.group(1) if m else None
        target = None
        for eff in effects:
            if eff_name and eff.get("name") == eff_name:
                target = eff
                break
        if target is None and effects:
            target = effects[0]
        if target:
            info["effect_name"] = target.get("name", "")
            info["prompt"] = target.get("sound_en", "")
            info["duration"] = target.get("duration", 5)
            info["regen_type"] = "sfx"
    elif kind == '背景音':
        layers = data.get("soundscape", {}).get("scene_layers", [])
        idx = line_id if line_id is not None else 0
        if idx < len(layers):
            layer = layers[idx]
            info["scene_name"] = layer.get("name", "")
            info["prompt"] = layer.get("prompt", "")
            info["regen_type"] = "bgm"
    else:
        # 成品音频 → 支持重新合成整章
        info["regen_type"] = "chapter"
        info["note"] = "点击将调用 audio_processing_module.py 重新合成整章音频"

    return info


def regenerate_audio(audio_rel_path: str, override_text: str = None):
    """重新生成单个音频文件，覆盖原文件"""
    info = get_regen_info(audio_rel_path)
    if info.get("error"):
        raise RuntimeError(info["error"])
    out_abs = BASE_DIR / audio_rel_path
    rtype = info.get("regen_type")

    if rtype == "voice":
        from audio_processing_module import VoiceParams
        engine = _get_tts_engine()
        text = override_text if override_text else info["text"]
        params = VoiceParams(text=text, role=info["role"], role_voice=info["role_voice"],
                             speed=info["speed"], volume=info["volume"], pitch=info["pitch"],
                             instruct=info.get("instruct") or None)
        audio = engine.text_to_speech(params)
        audio.export(str(out_abs), format=out_abs.suffix.lstrip('.'))
        return str(out_abs.relative_to(BASE_DIR))

    if rtype == "sfx":
        from woosh_generate_audio import generate_audio
        result = generate_audio(prompt=info["prompt"], duration=float(info.get("duration", 5)),
                                output_path=str(out_abs))
        if result:
            return str(Path(result).relative_to(BASE_DIR))
        raise RuntimeError("音效重生成失败")

    if rtype == "bgm":
        from stable_audio3_background_generate_audio import generate_audio_batch
        results = generate_audio_batch([{"prompt": info["prompt"], "duration": 30.0, "output_path": str(out_abs)}])
        if results and results[0]:
            return str(Path(results[0]).relative_to(BASE_DIR))
        raise RuntimeError("背景音重生成失败")

    raise RuntimeError("该音频类型不支持单独重生成（成品音频请重新生成整章）")


def start_regenerate(audio_rel_path: str, override_text: str = None):
    """异步重生成单音频，返回 task_id（用 SSE 推送日志）"""
    global _task_counter
    _task_counter += 1
    tid = f"regen_{_task_counter}_{int(time.time())}"
    with _gen_lock:
        _gen_tasks[tid] = {"status": "running", "logs": [], "paths": [audio_rel_path], "current": audio_rel_path}
    _log_queues[tid] = queue.Queue()

    def _run():
        q = _log_queues[tid]
        try:
            info = get_regen_info(audio_rel_path)
            if info.get("error"):
                raise RuntimeError(info["error"])
            rtype = info.get("regen_type")
            q.put({"type": "log", "data": f"重生成类型: {rtype} | {audio_rel_path}"})
            if rtype == "chapter":
                # 成品音频 → 重新合成整章
                _regen_chapter(info, tid)
            else:
                q.put({"type": "log", "data": "调用生成引擎中，请稍候（Woosh/SA3 首次需加载模型）..."})
                out = regenerate_audio(audio_rel_path, override_text)
                q.put({"type": "log", "data": f"✓ 已生成: {out}"})
                with _gen_lock:
                    _gen_tasks[tid]["result"] = out
            with _gen_lock:
                _gen_tasks[tid]["status"] = "done"
            q.put({"type": "done", "data": "done"})
        except Exception as e:
            q.put({"type": "error", "data": str(e)})
            with _gen_lock:
                _gen_tasks[tid]["status"] = "error"
            q.put({"type": "done", "data": "error"})
    threading.Thread(target=_run, daemon=True).start()
    return tid


def _regen_chapter(info: dict, tid: str):
    """重新合成整章音频，实时推送子进程日志"""
    q = _log_queues[tid]
    script_rel = info.get("script")
    if not script_rel:
        raise RuntimeError("未找到对应剧本")
    json_path = BASE_DIR / script_rel
    cmd = [sys.executable, str(SCRIPT_DIR / "audio_processing_module.py"), "--json-path", str(json_path)]
    env = os.environ.copy()
    env['HUGGINGFACE_HUB_DISABLE_REPO_ID_VALIDATION'] = '1'
    env['HF_HUB_OFFLINE'] = '1'
    # ── 所有 HF 模型统一使用项目 models/ 目录 ──
    env['HF_HOME'] = str(BASE_DIR / "models")
    env['HUGGINGFACE_HUB_CACHE'] = str(BASE_DIR / "models" / "hub")
    q.put({"type": "log", "data": f"重新合成整章: {json_path.name}"})
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, cwd=str(SCRIPT_DIR), env=env)
    with _gen_lock:
        _gen_tasks[tid]["proc"] = proc
    for line in iter(proc.stdout.readline, ''):
        q.put({"type": "log", "data": line.rstrip('\n')})
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"整章合成失败，退出码 {proc.returncode}")


# ======================== 剧本编辑与逐行重生成 ========================

def save_script(script_rel: str, lines: list):
    """保存编辑后的剧本行（覆盖 data[N] 的 role/voice 字段），直接覆盖原文件"""
    json_path = BASE_DIR / script_rel
    if not json_path.exists():
        raise RuntimeError(f"剧本不存在: {script_rel}")
    data = json.loads(json_path.read_text(encoding='utf-8'))
    script_lines = data.get("data", [])
    for edit in lines:
        lid = edit.get("id")
        if lid is None or lid >= len(script_lines):
            continue
        line = script_lines[lid]
        if "role" in edit:
            line["role"] = edit["role"]
        voice = line.setdefault("api", {}).setdefault("voice", {})
        for k in ("text", "role_voice", "speed", "volume", "pitch", "instruct"):
            if k in edit:
                voice[k] = edit[k]
        # role 同步到 voice.role
        if "role" in edit:
            voice["role"] = edit["role"]
        # 音效编辑
        if "effects" in edit:
            existing = line.setdefault("api", {}).setdefault("effects", [])
            for ef in edit["effects"]:
                ei = ef.get("idx")
                if ei is None or ei >= len(existing):
                    continue
                for k in ("name", "trigger_keyword", "trigger_delay", "duration", "sound_en", "sound_cn"):
                    if k in ef:
                        existing[ei][k] = ef[k]
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return {"status": "saved", "lines": len(lines)}


def get_line_audio(script_rel: str):
    """返回章节 output 目录下所有行级音频，按 line_id 分组。

    返回格式:
    {
      "voice": {"0": "output/.../配音/voice_line_0.wav", ...},
      "effects": {"0": ["output/.../音效/effect_line_xxx_0.wav", ...], ...},
      "mixed":   {"0": "output/.../混音/mixed_line_0.wav", ...},
      "bgm_layers": ["output/.../背景音/soundscape_layer_0.wav", ...]
    }
    """
    ch_dir = _find_output_chapter_dir(script_rel)
    if not ch_dir:
        return {"voice": {}, "effects": {}, "mixed": {}, "bgm_layers": []}

    def rel(p):
        return str(Path(p).relative_to(BASE_DIR))

    voice = {}
    for f in _list_dir_safe(ch_dir / "配音"):
        if f.is_file() and f.suffix == '.wav':
            lid = _extract_line_id(f.stem)
            if lid is not None:
                voice[str(lid)] = rel(f)

    effects: dict = {}
    for f in _list_dir_safe(ch_dir / "音效"):
        if f.is_file() and f.suffix == '.wav':
            lid = _extract_line_id(f.stem)
            if lid is not None:
                effects.setdefault(str(lid), []).append(rel(f))

    mixed = {}
    for f in _list_dir_safe(ch_dir / "混音"):
        if f.is_file() and f.suffix == '.wav':
            lid = _extract_line_id(f.stem)
            if lid is not None:
                mixed[str(lid)] = rel(f)

    bgm_layers = []
    bgm_dir = ch_dir / "背景音"
    if bgm_dir.is_dir():
        for f in sorted(_list_dir_safe(bgm_dir), key=lambda x: x.name):
            if f.is_file() and f.suffix == '.wav':
                bgm_layers.append(rel(f))

    return {"voice": voice, "effects": effects, "mixed": mixed, "bgm_layers": bgm_layers}


def _find_output_chapter_dir(script_rel: str):
    """根据剧本路径找到 output 下对应章节目录"""
    stem = Path(script_rel).stem
    # 遍历 output/*/{stem}/
    for novel_dir in _list_dir_safe(OUTPUT_DIR):
        if not novel_dir.is_dir():
            continue
        cand = novel_dir / stem
        if cand.is_dir():
            return cand
    # 按章节号匹配
    key = _chapter_sort_key(stem)
    if key[0] == 0:
        for novel_dir in _list_dir_safe(OUTPUT_DIR):
            if not novel_dir.is_dir():
                continue
            for ch_dir in _list_dir_safe(novel_dir):
                if ch_dir.is_dir() and _chapter_sort_key(ch_dir.name) == key:
                    return ch_dir
    return None


def start_regen_line(script_rel: str, line_id: int):
    """异步：重生成剧本某一行的配音+该行音效，替换 output 对应文件"""
    global _task_counter
    _task_counter += 1
    tid = f"regenline_{_task_counter}_{int(time.time())}"
    with _gen_lock:
        _gen_tasks[tid] = {"status": "running", "logs": [], "paths": [f"{script_rel}#{line_id}"]}
    _log_queues[tid] = queue.Queue()

    def _run():
        q = _log_queues[tid]
        try:
            json_path = BASE_DIR / script_rel
            data = json.loads(json_path.read_text(encoding='utf-8'))
            lines = data.get("data", [])
            if line_id >= len(lines):
                raise RuntimeError(f"行号越界: {line_id}")
            line = lines[line_id]
            ch_dir = _find_output_chapter_dir(script_rel)
            if not ch_dir:
                raise RuntimeError("未找到 output 对应章节目录")

            # 1. 重生成配音
            voice = line.get("api", {}).get("voice", {})
            text = voice.get("text", "")
            if text.strip():
                from audio_processing_module import VoiceParams
                q.put({"type": "log", "data": f"重生成配音 #{line_id}: {text[:30]}..."})
                engine = _get_tts_engine()
                params = VoiceParams(text=text, role=line.get("role", ""),
                                     role_voice=voice.get("role_voice", ""),
                                     speed=voice.get("speed", "+0%"), volume=voice.get("volume", "+0%"),
                                     pitch=voice.get("pitch", "+0Hz"), instruct=voice.get("instruct") or None)
                audio = engine.text_to_speech(params)
                voice_out = ch_dir / "配音" / f"voice_line_{line_id}.wav"
                voice_out.parent.mkdir(exist_ok=True)
                audio.export(str(voice_out), format="wav")
                q.put({"type": "log", "data": f"✓ 配音已替换: {voice_out.name}"})

            # 2. 重生成该行音效
            effects = line.get("api", {}).get("effects", [])
            if effects:
                from woosh_generate_audio import generate_audio
                for eff in effects:
                    name = eff.get("name", "sfx")
                    prompt = eff.get("sound_en", "")
                    if not prompt.strip():
                        continue
                    dur = float(eff.get("duration", 5))
                    eff_out = ch_dir / "音效" / f"effect_line_{name}_{line_id}.wav"
                    eff_out.parent.mkdir(exist_ok=True)
                    q.put({"type": "log", "data": f"重生成音效: {name}"})
                    generate_audio(prompt=prompt, duration=dur, output_path=str(eff_out))
                    q.put({"type": "log", "data": f"✓ 音效已替换: {eff_out.name}"})

            with _gen_lock:
                _gen_tasks[tid]["status"] = "done"
            q.put({"type": "done", "data": "done"})
        except Exception as e:
            q.put({"type": "error", "data": str(e)})
            with _gen_lock:
                _gen_tasks[tid]["status"] = "error"
            q.put({"type": "done", "data": "error"})
    threading.Thread(target=_run, daemon=True).start()
    return tid


def start_remix_line(script_rel: str, line_id: int):
    """异步：按原混音逻辑重新混音某一行（voice + 该行音效 + 背景音），生成 混音/mixed_line_N.wav"""
    global _task_counter
    _task_counter += 1
    tid = f"remix_{_task_counter}_{int(time.time())}"
    with _gen_lock:
        _gen_tasks[tid] = {"status": "running", "logs": [], "paths": [f"{script_rel}#{line_id}.mix"]}
    _log_queues[tid] = queue.Queue()

    def _run():
        q = _log_queues[tid]
        try:
            from pydub import AudioSegment
            from audio_processing_module import AudioEngine, MixConfig, EffectAudioParams
            json_path = BASE_DIR / script_rel
            data = json.loads(json_path.read_text(encoding='utf-8'))
            lines = data.get("data", [])
            if line_id >= len(lines):
                raise RuntimeError(f"行号越界: {line_id}")
            line = lines[line_id]
            ch_dir = _find_output_chapter_dir(script_rel)
            if not ch_dir:
                raise RuntimeError("未找到 output 对应章节目录")

            # 读取配音
            voice_path = ch_dir / "配音" / f"voice_line_{line_id}.wav"
            if not voice_path.exists():
                raise RuntimeError(f"配音不存在，请先重生成配音: {voice_path.name}")
            q.put({"type": "log", "data": f"读取配音: {voice_path.name}"})
            voice_audio = AudioSegment.from_wav(str(voice_path))

            # 读取该行音效
            effects_cfg = line.get("api", {}).get("effects", [])
            effect_audios = []
            effect_params = []
            for eff in effects_cfg:
                name = eff.get("name", "sfx")
                eff_path = ch_dir / "音效" / f"effect_line_{name}_{line_id}.wav"
                if not eff_path.exists():
                    q.put({"type": "log", "data": f"⚠ 音效缺失，跳过: {eff_path.name}"})
                    continue
                ea = AudioSegment.from_wav(str(eff_path))
                effect_audios.append(ea)
                effect_params.append(EffectAudioParams(
                    name=name, sound_cn=eff.get("sound_cn", ""), sound_en=eff.get("sound_en", ""),
                    volume=eff.get("volume", "+0%"), pitch=eff.get("pitch", "+0Hz"),
                    trigger_delay=float(eff.get("trigger_delay", 0.0)), duration=float(eff.get("duration", 1.0)),
                    process_mode=eff.get("process_mode", "overlay"),
                    trigger_keyword=eff.get("trigger_keyword", ""), trigger_offset=float(eff.get("trigger_offset", 0.0)),
                ))
                q.put({"type": "log", "data": f"读取音效: {eff_path.name}"})

            # 读取背景音（若有逐句 bgm 文件）
            bgm_audio = None

            engine = AudioEngine()
            mix_config = MixConfig(**line.get("mix", {"mode": "mix"}))
            q.put({"type": "log", "data": f"混音模式: {mix_config.mode}"})
            mixed = engine.mix_audio(voice=voice_audio, bgm=bgm_audio, effects=effect_audios,
                                     mix_config=mix_config, effect_params=effect_params,
                                     voice_text=line.get("api", {}).get("voice", {}).get("text", ""))
            mix_out = ch_dir / "混音" / f"mixed_line_{line_id}.wav"
            mix_out.parent.mkdir(exist_ok=True)
            mixed.export(str(mix_out), format="wav")
            q.put({"type": "log", "data": f"✓ 混音已生成: {mix_out.name}"})

            with _gen_lock:
                _gen_tasks[tid]["status"] = "done"
            q.put({"type": "done", "data": "done"})
        except Exception as e:
            q.put({"type": "error", "data": str(e)})
            with _gen_lock:
                _gen_tasks[tid]["status"] = "error"
            q.put({"type": "done", "data": "error"})
    threading.Thread(target=_run, daemon=True).start()
    return tid


def start_regen_effect(script_rel: str, line_id: int, effect_idx: int):
    """异步：只重生成某行的某个音效"""
    global _task_counter
    _task_counter += 1
    tid = f"regeneff_{_task_counter}_{int(time.time())}"
    with _gen_lock:
        _gen_tasks[tid] = {"status": "running", "logs": [], "paths": [f"{script_rel}#{line_id}.eff{effect_idx}"]}
    _log_queues[tid] = queue.Queue()

    def _run():
        q = _log_queues[tid]
        try:
            json_path = BASE_DIR / script_rel
            data = json.loads(json_path.read_text(encoding='utf-8'))
            lines = data.get("data", [])
            if line_id >= len(lines):
                raise RuntimeError(f"行号越界: {line_id}")
            effects = lines[line_id].get("api", {}).get("effects", [])
            if effect_idx >= len(effects):
                raise RuntimeError(f"音效索引越界: {effect_idx}")
            eff = effects[effect_idx]
            name = eff.get("name", "sfx")
            prompt = eff.get("sound_en", "")
            if not prompt.strip():
                raise RuntimeError("音效提示词(sound_en)为空")
            dur = float(eff.get("duration", 5))
            ch_dir = _find_output_chapter_dir(script_rel)
            if not ch_dir:
                raise RuntimeError("未找到 output 对应章节目录")
            from woosh_generate_audio import generate_audio
            eff_out = ch_dir / "音效" / f"effect_line_{name}_{line_id}.wav"
            eff_out.parent.mkdir(exist_ok=True)
            q.put({"type": "log", "data": f"重生成音效 [{name}]: {prompt[:40]}..."})
            r = generate_audio(prompt=prompt, duration=dur, output_path=str(eff_out))
            if r:
                q.put({"type": "log", "data": f"✓ 音效已替换: {eff_out.name}"})
            else:
                raise RuntimeError("音效生成失败")
            with _gen_lock:
                _gen_tasks[tid]["status"] = "done"
            q.put({"type": "done", "data": "done"})
        except Exception as e:
            q.put({"type": "error", "data": str(e)})
            with _gen_lock:
                _gen_tasks[tid]["status"] = "error"
            q.put({"type": "done", "data": "error"})
    threading.Thread(target=_run, daemon=True).start()
    return tid


def start_regen_layer(script_rel: str, layer_index: int):
    """异步：重生成 soundscape 某场景层背景音"""
    global _task_counter
    _task_counter += 1
    tid = f"regenlayer_{_task_counter}_{int(time.time())}"
    with _gen_lock:
        _gen_tasks[tid] = {"status": "running", "logs": [], "paths": [f"{script_rel}#layer{layer_index}"]}
    _log_queues[tid] = queue.Queue()

    def _run():
        q = _log_queues[tid]
        try:
            json_path = BASE_DIR / script_rel
            data = json.loads(json_path.read_text(encoding='utf-8'))
            layers = data.get("soundscape", {}).get("scene_layers", [])
            if layer_index >= len(layers):
                raise RuntimeError(f"场景层越界: {layer_index}")
            layer = layers[layer_index]
            prompt = layer.get("prompt", "")
            ch_dir = _find_output_chapter_dir(script_rel)
            if not ch_dir:
                raise RuntimeError("未找到 output 对应章节目录")
            from stable_audio3_background_generate_audio import generate_audio_batch
            bgm_out = ch_dir / "背景音" / f"soundscape_layer_{layer_index}.wav"
            bgm_out.parent.mkdir(exist_ok=True)
            q.put({"type": "log", "data": f"重生成背景音层 #{layer_index}: {layer.get('name','')}"})
            results = generate_audio_batch([{"prompt": prompt, "duration": 30.0, "output_path": str(bgm_out)}])
            if results and results[0]:
                q.put({"type": "log", "data": f"✓ 背景音已替换: {bgm_out.name}"})
            else:
                raise RuntimeError("背景音生成失败")
            with _gen_lock:
                _gen_tasks[tid]["status"] = "done"
            q.put({"type": "done", "data": "done"})
        except Exception as e:
            q.put({"type": "error", "data": str(e)})
            with _gen_lock:
                _gen_tasks[tid]["status"] = "error"
            q.put({"type": "done", "data": "error"})
    threading.Thread(target=_run, daemon=True).start()
    return tid


def _list_dir_safe(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return sorted([e for e in path.iterdir() if not e.name.startswith('.')])
    except PermissionError:
        return []


# 中文数字转阿拉伯数字（用于章节排序）
_CN_NUM = {'零':0,'〇':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,
           '十':10,'百':100,'千':1000}

def _cn_to_int(s: str) -> int:
    """把中文数字串转为整数，支持 '一'~'九十九' 和 '一百二十三' 等"""
    if s.isdigit():
        return int(s)
    total, section, num = 0, 0, 0
    for ch in s:
        if ch not in _CN_NUM:
            continue
        val = _CN_NUM[ch]
        if val >= 10:
            if num == 0:
                num = 1
            if val == 10:
                section += num * 10
            else:
                section = (section + num) * val
            num = 0
        else:
            num = val
    return total + section + num


def _chapter_sort_key(name: str):
    """从章节名/文件名提取章节号用于排序，如 '第55回'→55, '第十四回'→14"""
    m = re.search(r'第\s*([0-9]+|[一二三四五六七八九十百千零〇两]+)\s*[回章]', name)
    if m:
        try:
            return (0, _cn_to_int(m.group(1)))
        except:
            pass
    # 无法识别章节号的排在最后，按名称排
    return (1, 0, name)


def scan_scripts():
    trees = []
    for novel_dir in _list_dir_safe(SCRIPT_BASE):
        if not novel_dir.is_dir():
            continue
        chapters = []
        for f in _list_dir_safe(novel_dir):
            if f.is_file() and f.suffix == '.json':
                chapters.append({"name": f.stem, "path": str(f.relative_to(BASE_DIR))})
        chapters.sort(key=lambda c: _chapter_sort_key(c["name"]))
        trees.append({"name": novel_dir.name, "path": str(novel_dir.relative_to(BASE_DIR)), "chapters": chapters})
    return trees


def scan_outputs():
    trees = []
    # 排除的临时子目录
    SKIP_DIRS = {'stream_tmp', 'tmp'}
    for novel_dir in _list_dir_safe(OUTPUT_DIR):
        if not novel_dir.is_dir() or novel_dir.name in ('temp', '_lab', '片头片尾'):
            continue
        chapters = []
        for ch_dir in _list_dir_safe(novel_dir):
            if not ch_dir.is_dir():
                continue
            # 顶层成品音频（章节主输出）
            final_audios = []
            for f in _list_dir_safe(ch_dir):
                if f.is_file() and f.suffix.lower() in ('.mp3', '.wav', '.m4a'):
                    final_audios.append({"name": f.name, "path": str(f.relative_to(BASE_DIR)), "size": f.stat().st_size, "kind": "final"})
            # 子目录音频，按分类分组（混音/配音/音效/背景音）
            groups = []
            for sub in _list_dir_safe(ch_dir):
                if not sub.is_dir() or sub.name in SKIP_DIRS:
                    continue
                sub_audios = []
                for f in _list_dir_safe(sub):
                    if f.is_file() and f.suffix.lower() in ('.mp3', '.wav', '.m4a'):
                        line_id = _extract_line_id(f.stem)
                        sub_audios.append({"name": f.name, "path": str(f.relative_to(BASE_DIR)),
                                           "size": f.stat().st_size, "kind": sub.name, "line_id": line_id})
                # 按 line_id 数字顺序排序
                sub_audios.sort(key=lambda a: (a["line_id"] if a["line_id"] is not None else 99999, a["name"]))
                if sub_audios:
                    groups.append({"name": sub.name, "audios": sub_audios})
            has_any = bool(final_audios) or any(g["audios"] for g in groups)
            chapters.append({
                "name": ch_dir.name,
                "path": str(ch_dir.relative_to(BASE_DIR)),
                "final_audios": final_audios,
                "groups": groups,
                "status": "generated" if has_any else "none",
            })
        chapters.sort(key=lambda c: _chapter_sort_key(c["name"]))
        trees.append({"name": novel_dir.name, "path": str(novel_dir.relative_to(BASE_DIR)), "chapters": chapters})
    return trees


def _extract_line_id(stem: str):
    """从音频文件名提取 line_id：voice_line_49→49, effect_line_名称_42→42, mixed_line_5→5"""
    m = re.search(r'_(\d+)$', stem)
    return int(m.group(1)) if m else None


def scan_clone_voices():
    voices = []
    for f in _list_dir_safe(CLONE_AUDIO_DIR):
        if f.is_file() and f.suffix.lower() in ('.mp3', '.wav'):
            voices.append({"name": f.stem, "filename": f.name, "path": str(f.relative_to(BASE_DIR))})
    return voices


# ---- 克隆音频角色列表说明 MD ----
# 唯一权威文件：skill references 副本（clone-audio 下的旧副本已删除）
CLONE_VOICE_MD = BASE_DIR / ".comate" / "skills" / "novel-to-script" / "references" / "克隆音频角色列表说明.md"


def parse_clone_voice_md():
    """解析克隆音频角色列表说明.md，返回结构化数据（含新增字段 gender/age/lang/style）"""
    if not CLONE_VOICE_MD.exists():
        return []
    text = CLONE_VOICE_MD.read_text(encoding='utf-8')
    rows = []
    current_section = ''
    current_subsection = ''
    for line in text.splitlines():
        m2 = re.match(r'^##\s+(.+)', line)
        if m2:
            current_section = m2.group(1).strip()
            continue
        m3 = re.match(r'^###\s+(.+)', line)
        if m3:
            current_subsection = m3.group(1).strip()
            continue
        if not line.startswith('|'):
            continue
        parts = [p.strip() for p in line.strip('|').split('|')]
        if len(parts) < 3:
            continue
        if parts[0] in ('角色名', '---', '') or parts[0].startswith('---'):
            continue
        name = parts[0]
        filename = parts[1].strip('`')
        feature = parts[2] if len(parts) > 2 else ''
        scene = parts[3] if len(parts) > 3 else ''
        # 新字段：从 MD 中直接读取（col index 4-7），若不存在则留空
        gender = parts[4] if len(parts) > 4 else ''
        age = parts[5] if len(parts) > 5 else ''
        lang = parts[6] if len(parts) > 6 else ''
        style = parts[7] if len(parts) > 7 else ''
        if name:
            rows.append({
                'name': name, 'filename': filename,
                'feature': feature, 'scene': scene,
                'section': current_section, 'subsection': current_subsection,
                'gender': gender, 'age': age, 'lang': lang, 'style': style
            })
    return rows


def update_clone_voice_row(name: str, new_name: str, new_feature: str, new_scene: str,
                           new_gender: str = '', new_age: str = '', new_lang: str = '', new_style: str = ''):
    """更新克隆音频角色列表说明.md 中的一行（按角色名匹配），支持新增字段"""
    if not CLONE_VOICE_MD.exists():
        return {'error': 'MD 文件不存在'}
    lines = CLONE_VOICE_MD.read_text(encoding='utf-8').splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith('|'):
            parts = line.strip('|').split('|')
            if len(parts) >= 3 and parts[0].strip() == name:
                filename_raw = parts[1].strip()
                new_filename = filename_raw
                if new_name != name:
                    inner = filename_raw.strip('`')
                    ext = Path(inner).suffix if '.' in inner else '.mp3'
                    new_filename = f'`{new_name}{ext}`'
                parts[0] = f' {new_name} '
                parts[1] = f' {new_filename} '
                parts[2] = f' {new_feature} '
                if len(parts) > 3:
                    parts[3] = f' {new_scene} '
                # 确保有8列
                while len(parts) < 8:
                    parts.append('  ')
                parts[4] = f' {new_gender} '
                parts[5] = f' {new_age} '
                parts[6] = f' {new_lang} '
                parts[7] = f' {new_style} '
                line = '|' + '|'.join(parts) + '|'
                updated = True
        new_lines.append(line)
    if updated:
        content = '\n'.join(new_lines)
        CLONE_VOICE_MD.write_text(content, encoding='utf-8')
    return {'status': 'ok', 'updated': updated}


CHAR_VOICE_TABLE_DIR = BASE_DIR / "novel_tool" / "character_voice_tables"


def _normalize_novel_name(novel_name: str) -> str:
    """从配音表文件stem提取小说名用于查找 JSON/MD 文件
    支持:
      '蜀山剑侠传'          -> 文件 蜀山剑侠传角色配音表.json
      '蜀山剑侠传角色配音表 copy' -> 文件 蜀山剑侠传角色配音表 copy.json
    """
    # 如果直接对应一个文件 stem（即传入的是 file.stem），直接用
    json_path = CHAR_VOICE_TABLE_DIR / f"{novel_name}.json"
    if json_path.exists():
        return novel_name
    md_path = CHAR_VOICE_TABLE_DIR / f"{novel_name}.md"
    if md_path.exists():
        return novel_name
    return novel_name


def _get_char_voice_md_path(novel_name: str):
    """给定小说名，优先返回 JSON 文件路径，其次 MD"""
    # 优先：JSON 文件
    p_json = CHAR_VOICE_TABLE_DIR / f"{novel_name}.json"
    if p_json.exists():
        return p_json
    p2_json = CHAR_VOICE_TABLE_DIR / f"{novel_name}角色配音表.json"
    if p2_json.exists():
        return p2_json

    # 其次：MD（向后兼容）
    p = CHAR_VOICE_TABLE_DIR / f"{novel_name}.md"
    if p.exists():
        return p
    p2 = CHAR_VOICE_TABLE_DIR / f"{novel_name}角色配音表.md"
    if p2.exists():
        return p2
    for suffix in ('_json', 'json稿', 'JSON稿'):
        if novel_name.endswith(suffix):
            base = novel_name[:-len(suffix)]
            p3 = CHAR_VOICE_TABLE_DIR / f"{base}角色配音表.md"
            if p3.exists():
                return p3
    return None


def scan_char_voice_novels():
    """返回角色配音表目录下所有可用的小说名列表（JSON 优先，去重）"""
    seen = set()
    names = []
    # JSON 优先
    for f in _list_dir_safe(CHAR_VOICE_TABLE_DIR):
        if f.is_file() and '角色配音表' in f.name and f.suffix == '.json':
            if f.stem not in seen:
                names.append(f.stem)
                seen.add(f.stem)
    # MD 补充
    for f in _list_dir_safe(CHAR_VOICE_TABLE_DIR):
        if f.is_file() and '角色配音表' in f.name and f.suffix == '.md':
            if f.stem not in seen:
                names.append(f.stem)
                seen.add(f.stem)
    return names


def _parse_char_voice_md(novel_name: str):
    """解析角色配音表文件（优先 JSON），返回行列表"""
    file_path = _get_char_voice_md_path(novel_name)
    if not file_path or not file_path.exists():
        return []

    # JSON 格式
    if file_path.suffix == '.json':
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except Exception:
            return []
        rows = []
        LEVEL_ORDER = ["旁白", "主要角色", "重要角色", "次要角色", "临时角色"]
        for level in LEVEL_ORDER:
            if level not in data:
                continue
            for c in data[level]:
                rows.append({
                    'char': c.get('角色名', ''),
                    'voice': c.get('配音名', ''),
                    'category': c.get('角色级别', level),
                    'age': c.get('年龄', ''),
                    'gender': c.get('性别', ''),
                    'char_desc': c.get('性格', ''),
                    'vd_prompt': c.get('VoiceDesign_Prompt', ''),
                    'scope': c.get('使用范围', ''),
                    'note': c.get('备注', ''),
                    'category_raw': c.get('分类', ''),
                })
        return rows

    # 向后兼容：MD 格式
    text = file_path.read_text(encoding='utf-8')
    rows = []
    current_category = ''
    for line in text.splitlines():
        m = re.match(r'^##\s+(.+)', line)
        if m:
            current_category = m.group(1).strip()
            continue
        if not line.startswith('|'):
            continue
        parts = [p.strip() for p in line.strip('|').split('|')]
        if len(parts) < 2:
            continue
        if parts[0] in ('角色名', '---', '') or parts[0].startswith('---'):
            continue
        char_name = parts[0]
        voice_name = parts[1] if len(parts) > 1 else ''
        age = parts[2] if len(parts) > 2 else ''
        gender = parts[3] if len(parts) > 3 else ''
        char_desc = parts[4] if len(parts) > 4 else ''
        voice_suggestion = parts[5] if len(parts) > 5 else ''
        scope = parts[6] if len(parts) > 6 else ''
        note = parts[7] if len(parts) > 7 else ''
        vd_prompt = parts[8] if len(parts) > 8 else ''
        if char_name and voice_name:
            rows.append({
                'char': char_name, 'voice': voice_name, 'category': current_category,
                'age': age, 'gender': gender, 'char_desc': char_desc,
                'voice_suggestion': voice_suggestion, 'scope': scope, 'note': note,
                'vd_prompt': vd_prompt,
            })
    return rows


def get_char_voices(novel_name: str):
    """获取小说角色配音表"""
    rows = _parse_char_voice_md(novel_name)
    return {'novel': novel_name, 'rows': rows, 'count': len(rows)}


def update_char_voice(novel_name: str, char_name: str, new_voice: str,
                      new_char: str = '', category: str = '', char_desc: str = '', note: str = '',
                      age: str = '', gender: str = '', vd_prompt: str = ''):
    """更新角色配音表（优先 JSON），并同步修改所有对应 JSON 剧本中 roles_definition"""
    file_path = _get_char_voice_md_path(novel_name)
    if not file_path or not file_path.exists():
        return {'error': f'配音表不存在: {novel_name}'}

    # ── JSON 格式更新 ──
    if file_path.suffix == '.json':
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except Exception:
            return {'error': 'JSON 解析失败'}

        updated = False
        LEVEL_ORDER = ["旁白", "主要角色", "重要角色", "次要角色", "临时角色"]
        for level in LEVEL_ORDER:
            if level not in data:
                continue
            for c in data[level]:
                if c.get('角色名') == char_name:
                    c['配音名'] = new_voice
                    if new_char:
                        c['角色名'] = new_char
                    if age:
                        c['年龄'] = age
                    if gender:
                        c['性别'] = gender
                    if char_desc:
                        c['性格'] = char_desc
                    if vd_prompt:
                        c['VoiceDesign_Prompt'] = vd_prompt
                    if note:
                        c['备注'] = note
                    if category:
                        c['角色级别'] = category
                    updated = True
                    break
            if updated:
                break

        if updated:
            file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        # ── MD 格式更新（向后兼容）──
        lines = file_path.read_text(encoding='utf-8').splitlines()
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith('|'):
                parts = [p.strip() for p in line.strip('|').split('|')]
                if len(parts) >= 2 and parts[0] == char_name:
                    parts[0] = new_char or char_name
                    parts[1] = new_voice
                    if age: parts[2] = age
                    if gender: parts[3] = gender
                    if char_desc: parts[4] = char_desc
                    if voice_suggestion: parts[5] = voice_suggestion
                    if category or len(parts) > 6: parts[6] = category
                    if note and len(parts) > 7: parts[7] = note
                    line = '| ' + ' | '.join(parts) + ' |'
                    updated = True
            new_lines.append(line)
        file_path.write_text('\n'.join(new_lines), encoding='utf-8')

    # 2. 同步更新所有 JSON 剧本中的 roles_definition
    _pure = novel_name
    for _suf in ('角色配音表 copy', '角色配音表'):
        if _pure.endswith(_suf):
            _pure = _pure[:-len(_suf)].strip()
            break
    novel_script_dir = SCRIPT_BASE / f"{_pure}_json"
    if not novel_script_dir.exists():
        for d in SCRIPT_BASE.iterdir():
            if d.is_dir() and _pure in d.name:
                novel_script_dir = d
                break

    synced_files = []
    if novel_script_dir.exists():
        for jf in sorted(novel_script_dir.glob('*.json')):
            try:
                data = json.loads(jf.read_text(encoding='utf-8'))
                roles = data.get('roles_definition', {})
                changed = False
                for role_key, role_val in roles.items():
                    if isinstance(role_val, dict):
                        if role_val.get('role_name') == char_name or role_key == char_name:
                            if role_val.get('role_voice') != new_voice:
                                role_val['role_voice'] = new_voice
                                changed = True
                if changed:
                    jf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                    synced_files.append(jf.name)
            except Exception:
                pass

    return {
        'status': 'ok',
        'updated': updated,
        'synced_count': len(synced_files),
        'synced_files': synced_files
    }


def scan_raw_scripts():
    trees = []
    for novel_dir in _list_dir_safe(SCRIPT_RAW_BASE):
        if not novel_dir.is_dir():
            continue
        # 一层：本目录直接含 txt/json
        direct_files = []
        for f in _list_dir_safe(novel_dir):
            if f.is_file() and f.suffix in ('.json', '.txt'):
                direct_files.append({"name": f.name, "path": str(f.relative_to(BASE_DIR))})
        if direct_files:
            direct_files.sort(key=lambda x: _chapter_sort_key(x["name"]))
            trees.append({"name": novel_dir.name, "path": str(novel_dir.relative_to(BASE_DIR)), "files": direct_files})
        # 两层：子目录含 txt/json
        for sub in _list_dir_safe(novel_dir):
            if not sub.is_dir():
                continue
            files = []
            for f in _list_dir_safe(sub):
                if f.is_file() and f.suffix in ('.json', '.txt'):
                    files.append({"name": f.name, "path": str(f.relative_to(BASE_DIR))})
            if files:
                files.sort(key=lambda x: _chapter_sort_key(x["name"]))
                trees.append({"name": f"{novel_dir.name}/{sub.name}",
                              "path": str(sub.relative_to(BASE_DIR)), "files": files})
    return trees


# ======================== 生成执行 ========================

def run_single_generate(script_path: str, task_id: str, config: dict):
    json_path = BASE_DIR / script_path
    if not json_path.exists():
        msg = f"剧本文件不存在: {json_path}"
        with _gen_lock:
            _gen_tasks[task_id]["logs"].append(msg)
        _log_queues[task_id].put({"type": "error", "data": msg})
        return

    cmd = [sys.executable, str(SCRIPT_DIR / "audio_processing_module.py"), "--json-path", str(json_path)]
    for key, flag in [("tts_engine", "--tts-engine"), ("sfx_engine", "--sfx-engine"),
                      ("bgm_engine", "--bgm-engine"), ("platform", "--platform")]:
        if config.get(key):
            cmd += [flag, config[key]]

    env = os.environ.copy()
    env['HUGGINGFACE_HUB_DISABLE_REPO_ID_VALIDATION'] = '1'
    env['HF_HUB_OFFLINE'] = '1'
    # ── 所有 HF 模型统一使用项目 models/ 目录 ──
    env['HF_HOME'] = str(BASE_DIR / "models")
    env['HUGGINGFACE_HUB_CACHE'] = str(BASE_DIR / "models" / "hub")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, cwd=str(SCRIPT_DIR), env=env)
        with _gen_lock:
            _gen_tasks[task_id]["proc"] = proc
        for line in iter(proc.stdout.readline, ''):
            line = line.rstrip('\n')
            _log_queues[task_id].put({"type": "log", "data": line})
            with _gen_lock:
                _gen_tasks[task_id]["logs"].append(line)
        proc.wait()
        status = "done" if proc.returncode == 0 else "error"
    except Exception as e:
        _log_queues[task_id].put({"type": "error", "data": str(e)})
        status = "error"
    with _gen_lock:
        _gen_tasks[task_id]["status"] = status
    _log_queues[task_id].put({"type": "done", "data": status})


def start_generate(paths: list, config: dict):
    global _task_counter
    _task_counter += 1
    tid = f"gen_{_task_counter}_{int(time.time())}"
    with _gen_lock:
        _gen_tasks[tid] = {"status": "running", "logs": [], "paths": paths, "current": None}
    _log_queues[tid] = queue.Queue()

    def _run():
        total = len(paths)
        for i, p in enumerate(paths):
            with _gen_lock:
                _gen_tasks[tid]["current"] = p
            _log_queues[tid].put({"type": "log", "data": f"[{i+1}/{total}] {Path(p).name}"})
            run_single_generate(p, tid, config)
        with _gen_lock:
            _gen_tasks[tid]["status"] = "done"
        _log_queues[tid].put({"type": "done", "data": "all_done"})
    threading.Thread(target=_run, daemon=True).start()
    return tid


def start_generate_all(config: dict):
    global _task_counter
    _task_counter += 1
    tid = f"genall_{_task_counter}_{int(time.time())}"
    with _gen_lock:
        _gen_tasks[tid] = {"status": "running", "logs": [], "paths": ["ALL"], "current": None}
    _log_queues[tid] = queue.Queue()

    def _run():
        sh = SCRIPT_DIR / "novel_batch_manager.sh"
        try:
            proc = subprocess.Popen(["bash", str(sh)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, cwd=str(SCRIPT_DIR))
            with _gen_lock:
                _gen_tasks[tid]["proc"] = proc
            for line in iter(proc.stdout.readline, ''):
                _log_queues[tid].put({"type": "log", "data": line.rstrip('\n')})
            proc.wait()
            status = "done" if proc.returncode == 0 else "error"
        except Exception as e:
            _log_queues[tid].put({"type": "error", "data": str(e)})
            status = "error"
        with _gen_lock:
            _gen_tasks[tid]["status"] = status
        _log_queues[tid].put({"type": "done", "data": status})
    threading.Thread(target=_run, daemon=True).start()
    return tid


# ======================== HTTP Handler ========================

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, data, ct='application/json; charset=utf-8', code=200):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        elif isinstance(data, str):
            data = data.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, filepath: Path, ct='application/octet-stream'):
        try:
            data = filepath.read_bytes()
        except:
            self.send_error(404, 'File not found')
            return
        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file_ranged(self, filepath: Path, ct='application/octet-stream'):
        """支持 HTTP Range 请求的文件服务（音频拖动/播放必需）"""
        if not filepath.exists() or not filepath.is_file():
            self.send_error(404, 'File not found')
            return
        file_size = filepath.stat().st_size
        range_header = self.headers.get('Range')

        if range_header:
            # 解析 "bytes=start-end"
            try:
                units, rng = range_header.split('=')
                start_s, end_s = rng.split('-')
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1
                with open(filepath, 'rb') as fp:
                    fp.seek(start)
                    data = fp.read(length)
                self.send_response(206)
                self.send_header('Content-Type', ct)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(length))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
                return
            except (ValueError, OSError):
                pass

        # 无 Range，整文件返回，但声明支持 Range
        try:
            data = filepath.read_bytes()
        except OSError:
            self.send_error(404, 'File not found')
            return
        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def _stream_sse(self, tid: str):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        q = _log_queues.get(tid)
        if not q:
            self.wfile.write(f"data: {json.dumps({'type': 'error', 'data': 'task not found'})}\n\n".encode())
            self.wfile.flush()
            return
        while True:
            try:
                msg = q.get(timeout=25)
                self.wfile.write(f"data: {json.dumps(msg, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                if msg.get("type") == "done":
                    break
            except queue.Empty:
                self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()

    def _serve_static(self, filename):
        f = BASE_DIR / "visual_tool" / filename
        ct_map = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'application/javascript'}
        ct = ct_map.get(Path(filename).suffix, 'text/plain')
        return self._send_file(f, ct)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        path = p.path
        qs = urllib.parse.parse_qs(p.query)

        routes = {
            '/': lambda: self._serve_static('index.html'),
            '/api/scripts': lambda: self._send(scan_scripts()),
            '/api/raw-scripts': lambda: self._send(scan_raw_scripts()),
            '/api/outputs': lambda: self._send(scan_outputs()),
            '/api/clone-voices': lambda: self._send(scan_clone_voices()),
            '/api/char-voices-novels': lambda: self._send(scan_char_voice_novels()),
            '/api/clone-voice-table': lambda: self._send(parse_clone_voice_md()),
        }

        if path in routes:
            return routes[path]()

        if path == '/api/char-voices':
            novel = qs.get('novel', [None])[0]
            if not novel:
                return self._send({"error": "缺少 novel 参数"}, code=400)
            novel = urllib.parse.unquote(novel)
            return self._send(get_char_voices(novel))

        if path == '/api/script/line-audio':
            script_rel = qs.get('script', [None])[0]
            if not script_rel:
                return self._send({"error": "缺少 script 参数"}, code=400)
            script_rel = urllib.parse.unquote(script_rel)
            return self._send(get_line_audio(script_rel))

        if path.startswith('/api/file/'):
            rel = urllib.parse.unquote(path[10:])
            f = BASE_DIR / rel
            ct = {'.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.json': 'application/json', '.txt': 'text/plain'}.get(f.suffix, 'application/octet-stream')
            return self._send_file_ranged(f, ct)

        if path.startswith('/api/raw-script/'):
            rel = urllib.parse.unquote(path[16:])
            f = BASE_DIR / rel
            if f.suffix == '.json':
                try:
                    return self._send(json.loads(f.read_text(encoding='utf-8')))
                except:
                    self.send_error(500)
                    return
            return self._send_file(f, 'text/plain; charset=utf-8')

        if path == '/api/generate/status':
            tid = qs.get('task_id', [None])[0]
            t = _gen_tasks.get(tid, {})
            return self._send({"status": t.get("status", "not_found"), "current": t.get("current"),
                               "logs": (t.get("logs") or [])[-50:]})

        if path == '/api/generate/log':
            tid = qs.get('task_id', [None])[0]
            if tid:
                return self._stream_sse(tid)
            self.send_error(400)
            return

        # fallback static
        try:
            return self._serve_static(path.lstrip('/'))
        except:
            self.send_error(404)

    def do_POST(self):
        cl = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(cl)) if cl else {}
        path = urllib.parse.urlparse(self.path).path

        if path == '/api/generate':
            tid = start_generate(body.get('paths', []), body.get('config', {}))
            return self._send({"task_id": tid, "status": "started"})

        if path == '/api/generate-all':
            tid = start_generate_all(body.get('config', {}))
            return self._send({"task_id": tid, "status": "started"})

        if path == '/api/generate/cancel':
            tid = body.get('task_id')
            if tid and tid in _gen_tasks:
                p = _gen_tasks[tid].get("proc")
                if p:
                    p.terminate()
                with _gen_lock:
                    _gen_tasks[tid]["status"] = "cancelled"
                if tid in _log_queues:
                    _log_queues[tid].put({"type": "done", "data": "cancelled"})
                return self._send({"status": "cancelled"})
            return self._send({"status": "not_found"})

        if path == '/api/outputs/delete':
            fp = body.get('path')
            if not fp:
                return self._send({"error": "缺少 path"}, code=400)
            # 安全校验：只允许删除 output/ 目录内的内容
            target = (BASE_DIR / fp).resolve()
            output_abs = OUTPUT_DIR.resolve()
            if output_abs not in target.parents and target != output_abs:
                return self._send({"error": "只能删除 output 目录内的文件"}, code=403)
            if target == output_abs:
                return self._send({"error": "不能删除 output 根目录"}, code=403)
            if not target.exists():
                return self._send({"status": "not_found"}, code=404)
            try:
                if target.is_dir():
                    import shutil
                    shutil.rmtree(target)
                    return self._send({"status": "deleted", "type": "dir"})
                else:
                    target.unlink()
                    return self._send({"status": "deleted", "type": "file"})
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        # ======================== 声音实验室 ========================
        if path == '/api/lab/tts':
            text = body.get('text', '')
            voice = body.get('voice', '云健-低沉')
            speed = body.get('speed', '+0%')
            volume = body.get('volume', '+0%')
            pitch = body.get('pitch', '+0Hz')
            instruct = body.get('instruct', '')
            if not text.strip():
                return self._send({"error": "文本不能为空"}, code=400)
            try:
                output_path = synthesize_tts(text, voice, speed, volume, pitch, instruct)
                return self._send({"path": output_path, "status": "done"})
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        if path == '/api/lab/vd-preview':
            vd_prompt = body.get('vd_prompt', '')
            text = body.get('text', '我是角色，这是我的声音样本，欢迎收听蜀山剑侠传有声剧。')
            char_name = body.get('char_name', '')
            if not vd_prompt.strip():
                return self._send({"error": "VoiceDesign Prompt 不能为空"}, code=400)
            try:
                # 启动合成（后台线程），返回 task_id，前端通过 SSE 获取日志和结果
                import hashlib as _hl
                import queue as _q
                safe_name = char_name.replace('/', '_').replace('\\', '_').replace(':', '_') if char_name.strip() else ""
                tid = f"vd_{safe_name}" if safe_name else f"vd_{_hl.md5(f'vd_{vd_prompt}_{text}'.encode()).hexdigest()[:12]}"
                # 注册 task
                _cancel_vd_synthesis()  # 先取消上一个
                with _gen_lock:
                    _gen_tasks[tid] = {"status": "running", "logs": [], "paths": [], "current": ""}
                _log_queues[tid] = _q.Queue()

                def _run_vd():
                    q = _log_queues[tid]
                    try:
                        out = synthesize_vd_preview(vd_prompt, text, char_name)
                        with _gen_lock:
                            _gen_tasks[tid]["status"] = "done"
                            _gen_tasks[tid]["result"] = out
                        q.put({"type": "done", "data": out})
                    except Exception as e:
                        q.put({"type": "error", "data": str(e)})
                        with _gen_lock:
                            _gen_tasks[tid]["status"] = "error"

                _th = threading.Thread(target=_run_vd, daemon=True)
                _th.start()
                return self._send({"task_id": tid, "status": "running"})
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        if path == '/api/lab/vd-save':
            audio_path = body.get('audio_path', '')
            char_name = body.get('char_name', '')
            if not audio_path.strip():
                return self._send({"error": "audio_path 不能为空"}, code=400)
            if not char_name.strip():
                return self._send({"error": "char_name 不能为空"}, code=400)
            try:
                import shutil
                from pydub import AudioSegment
                src = BASE_DIR / audio_path
                if not src.exists():
                    return self._send({"error": f"音频文件不存在: {audio_path}"}, code=400)
                # 清理文件名中非法字符
                safe_name = char_name.replace('/', '_').replace('\\', '_').replace(':', '_')
                dest = CLONE_AUDIO_DIR / f"{safe_name}.mp3"
                os.makedirs(str(CLONE_AUDIO_DIR), exist_ok=True)
                audio = AudioSegment.from_file(str(src))
                audio.export(str(dest), format="mp3")
                relative_dest = str(dest.relative_to(BASE_DIR))
                return self._send({"status": "saved", "path": relative_dest, "name": char_name})
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        if path == '/api/clone-voice/delete':
            char_name = body.get('char_name', '')
            if not char_name.strip():
                return self._send({"error": "char_name 不能为空"}, code=400)
            try:
                safe_name = char_name.replace('/', '_').replace('\\', '_').replace(':', '_')
                file_path = CLONE_AUDIO_DIR / f"{safe_name}.mp3"
                if file_path.exists():
                    os.remove(str(file_path))
                    # 同时删除 _lab 下的对应缓存
                    lab_file = LAB_OUTPUT_DIR / f"vd_{safe_name}.wav"
                    if lab_file.exists():
                        os.remove(str(lab_file))
                    return self._send({"status": "deleted", "name": char_name})
                else:
                    return self._send({"status": "not_found", "name": char_name})
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        if path == '/api/lab/sfx':
            prompt = body.get('prompt', '')
            duration = body.get('duration', 5.0)
            if not prompt.strip():
                return self._send({"error": "提示词不能为空"}, code=400)
            try:
                output_path = synthesize_sfx(prompt, float(duration))
                return self._send({"path": output_path, "status": "done"})
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        if path == '/api/lab/bgm':
            prompt = body.get('prompt', '')
            duration = body.get('duration', 30.0)
            if not prompt.strip():
                return self._send({"error": "提示词不能为空"}, code=400)
            try:
                output_path = synthesize_bgm(prompt, float(duration))
                return self._send({"path": output_path, "status": "done"})
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        # ======================== 单音频重生成 ========================
        if path == '/api/regen/info':
            ap = body.get('path', '')
            return self._send(get_regen_info(ap))

        if path == '/api/regen':
            ap = body.get('path', '')
            override_text = body.get('text')
            tid = start_regenerate(ap, override_text)
            return self._send({"task_id": tid, "status": "started"})

        # ======================== 剧本编辑与逐行重生成 ========================
        if path == '/api/script/save':
            script_rel = body.get('script', '')
            lines = body.get('lines', [])
            try:
                return self._send(save_script(script_rel, lines))
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        if path == '/api/script/regen-line':
            script_rel = body.get('script', '')
            line_id = body.get('line_id')
            if line_id is None:
                return self._send({"error": "缺少 line_id"}, code=400)
            tid = start_regen_line(script_rel, int(line_id))
            return self._send({"task_id": tid, "status": "started"})

        if path == '/api/script/regen-layer':
            script_rel = body.get('script', '')
            layer_index = body.get('layer_index')
            if layer_index is None:
                return self._send({"error": "缺少 layer_index"}, code=400)
            tid = start_regen_layer(script_rel, int(layer_index))
            return self._send({"task_id": tid, "status": "started"})

        if path == '/api/script/regen-effect':
            script_rel = body.get('script', '')
            line_id = body.get('line_id')
            effect_idx = body.get('effect_idx')
            if line_id is None or effect_idx is None:
                return self._send({"error": "缺少 line_id/effect_idx"}, code=400)
            tid = start_regen_effect(script_rel, int(line_id), int(effect_idx))
            return self._send({"task_id": tid, "status": "started"})

        if path == '/api/script/remix-line':
            script_rel = body.get('script', '')
            line_id = body.get('line_id')
            if line_id is None:
                return self._send({"error": "缺少 line_id"}, code=400)
            tid = start_remix_line(script_rel, int(line_id))
            return self._send({"task_id": tid, "status": "started"})

        if path == '/api/char-voices/update':
            novel = body.get('novel', '')
            char_name = body.get('char', '')
            new_voice = body.get('voice', '')
            if not novel or not char_name or not new_voice:
                return self._send({"error": "缺少 novel/char/voice 参数"}, code=400)
            try:
                return self._send(update_char_voice(
                    novel, char_name, new_voice,
                    new_char=body.get('new_char', char_name),
                    category=body.get('category', ''),
                    char_desc=body.get('char_desc', ''),
                    note=body.get('note', ''),
                    age=body.get('age', ''),
                    gender=body.get('gender', ''),
                    vd_prompt=body.get('vd_prompt', ''),
                ))
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        if path == '/api/clone-voice-table/update':
            row_name = body.get('name', '')
            new_name = body.get('new_name', row_name)
            new_feature = body.get('feature', '')
            new_scene = body.get('scene', '')
            new_gender = body.get('gender', '')
            new_age = body.get('age', '')
            new_lang = body.get('lang', '')
            new_style = body.get('style', '')
            if not row_name:
                return self._send({"error": "缺少 name 参数"}, code=400)
            try:
                return self._send(update_clone_voice_row(
                    row_name, new_name, new_feature, new_scene,
                    new_gender, new_age, new_lang, new_style
                ))
            except Exception as e:
                return self._send({"error": str(e)}, code=500)

        self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def main():
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    print(f"\n=== Novel Audio Visual Tool ===")
    print(f"  URL:    http://localhost:{PORT}")
    print(f"  Script: {SCRIPT_BASE.relative_to(BASE_DIR)}")
    print(f"  Output: {OUTPUT_DIR.relative_to(BASE_DIR)}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == '__main__':
    main()
