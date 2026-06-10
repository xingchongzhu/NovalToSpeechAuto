#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Woosh-DFlow 音效生成模块
使用 Sony AI 的 Woosh-DFlow 蒸馏模型生成音效，适用于短音效场景

与 stabilityai_stable_generate_audio.py 接口兼容，可灵活切换

特点：
- 单次生成固定约 5 秒音频，48kHz 高质量
- 支持指定任意时长：超过 5 秒自动多段生成 + 交叉淡入淡出拼接
- 推理速度快（M5 上约 0.4 秒/条）
- 专精音效生成，不适合音乐/BGM 生成

实现方式：
- Woosh 依赖 Python 3.12+，通过子进程调用 Woosh 虚拟环境
- 主项目 Python 3.9 无需安装 Woosh 依赖
"""

import os
import sys
import time
import json
import hashlib
import subprocess
import tempfile

# Woosh 仓库和虚拟环境路径
WOOSH_REPO_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "Woosh"
))
WOOSH_VENV_PYTHON = os.path.join(WOOSH_REPO_DIR, ".venv", "bin", "python3")

# 默认推理参数
DEFAULT_CFG = 7.0
DEFAULT_NUM_STEPS = 4
WOOSH_SAMPLE_RATE = 48000
WOOSH_MAX_DURATION = 5.0  # Woosh 单次生成最大时长（秒）
CROSSFADE_DURATION = 0.05  # 交叉淡入淡出时长（秒），50ms


def _check_woosh_env():
    """检查 Woosh 环境是否可用"""
    if not os.path.exists(WOOSH_VENV_PYTHON):
        return False, f"Woosh 虚拟环境未找到: {WOOSH_VENV_PYTHON}"
    checkpoint = os.path.join(WOOSH_REPO_DIR, "checkpoints", "Woosh-DFlow", "weights.safetensors")
    if not os.path.exists(checkpoint):
        return False, f"Woosh 模型权重未找到: {checkpoint}"
    return True, "OK"


# 内嵌的 Woosh 推理脚本（在 Woosh 虚拟环境中执行）
# 每次调用只生成单个 ~5 秒片段，不做拼接
_WOOSH_INFER_SCRIPT = r'''
import os
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')

import sys
import json
import time
import hashlib
import torch
import torchaudio

# 推理脚本位于 Woosh 仓库根目录下，通过 __file__ 定位
script_path = os.path.abspath(__file__)
woosh_repo = os.path.dirname(script_path)
if woosh_repo not in sys.path:
    sys.path.insert(0, woosh_repo)

# 切换工作目录到 Woosh 仓库（模型使用相对路径 checkpoints/ 加载）
original_cwd = os.getcwd()
os.chdir(woosh_repo)

from woosh.inference.flowmap_sampler import sample_euler
from woosh.model.flowmap_from_pretrained import FlowMapFromPretrained
from woosh.components.base import LoadConfig

# 模型单例
_model = None
_device = None

def get_model():
    global _model, _device
    if _model is not None:
        return _model, _device

    if torch.cuda.is_available():
        _device = "cuda"
    elif torch.backends.mps.is_available():
        _device = "mps"
    else:
        _device = "cpu"

    checkpoint_path = os.path.join(woosh_repo, "checkpoints", "Woosh-DFlow")
    _model = FlowMapFromPretrained(LoadConfig(path=checkpoint_path))
    _model = _model.eval().to(_device)
    return _model, _device

def generate_segment(prompt, seed=None, cfg=7.0, num_steps=4):
    """生成单个 ~5 秒音频片段，返回归一化后的 1D tensor"""
    ldm, device = get_model()

    if seed is None:
        seed = (int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)) % (2**31)
    torch.manual_seed(seed)

    renoise = [0] + [0.5] * (num_steps - 2) + [0.3] if num_steps > 2 else [0, 0.3]
    noise = torch.randn(1, 128, 501).to(device)
    cond = ldm.get_cond(
        {"audio": None, "description": [prompt]},
        no_dropout=True,
        device=device,
    )

    with torch.inference_mode():
        x_fake = sample_euler(model=ldm, noise=noise, cond=cond,
                              num_steps=num_steps, renoise=renoise, cfg=cfg)
        audio_fake = ldm.autoencoder.inverse(x_fake)

    audio_fake = audio_fake.cpu()
    max_abs = torch.max(torch.abs(audio_fake[0]))
    norm_factor = max_abs if max_abs > 1.0 else 1.0
    scaled = audio_fake[0] / norm_factor
    return scaled

# 主入口：从 stdin 读取 JSON 任务列表
# 每个 task 可能有多个 segments 需要生成
if __name__ == "__main__":
    WOOSH_MAX_DURATION = 5.0
    CROSSFADE_DURATION = 0.05
    tasks_json = sys.stdin.read()
    tasks = json.loads(tasks_json)

    for task in tasks:
        try:
            prompt = task["prompt"]
            output_path = task["output_path"]
            target_duration = task.get("duration", 5.0)
            cfg = task.get("cfg", 7.0)
            num_steps = task.get("num_steps", 4)
            base_seed = task.get("seed")

            if base_seed is None:
                base_seed = (int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)) % (2**31)

            # 计算需要多少个片段
            num_segments = max(1, int(target_duration / WOOSH_MAX_DURATION) + (1 if target_duration % WOOSH_MAX_DURATION > 0 else 0))

            segments = []
            for seg_idx in range(num_segments):
                seg_seed = base_seed + seg_idx
                seg = generate_segment(prompt, seed=seg_seed, cfg=cfg, num_steps=num_steps)
                segments.append(seg)

            if len(segments) == 1:
                # 单片段，直接截取到目标时长
                #target_samples = int(target_duration * 48000)
                #final = segments[0][:target_samples]
                final = segments[0]
            else:
                # 多片段拼接：用交叉淡入淡出
                crossfade_samples = int(0.05 * 48000)  # 50ms 交叉淡入淡出
                final = segments[0]
                for i in range(1, len(segments)):
                    seg = segments[i]
                    # 创建淡入淡出权重
                    fade_out = torch.linspace(1.0, 0.0, crossfade_samples)
                    fade_in = torch.linspace(0.0, 1.0, crossfade_samples)
                    # 重叠区域
                    overlap_out = final[-crossfade_samples:] * fade_out
                    overlap_in = seg[:crossfade_samples] * fade_in
                    # 拼接：前面部分（去掉尾部 crossfade）+ 重叠区 + 后面部分（去掉头部 crossfade）
                    final = torch.cat([
                        final[:-crossfade_samples],
                        overlap_out + overlap_in,
                        seg[crossfade_samples:]
                    ])
                # 截取到精确目标时长
                target_samples = int(target_duration * 48000)
                final = final[:target_samples]

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            torchaudio.save(output_path, final, sample_rate=48000)
            print(json.dumps({"status": "ok", "output": output_path, "segments": num_segments, "duration": target_duration}))

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(json.dumps({"status": "error", "output": task.get("output_path", ""), "error": str(e)}))
'''


def generate_audio(prompt, duration=5, output_path=None, seed=None):
    """
    生成单个音效

    :param prompt: 英文提示词（必须详细，至少8个单词）
    :param duration: 目标时长（秒），超过 5 秒自动多段拼接
    :param output_path: 输出路径
    :param seed: 随机种子
    :return: 生成的音频文件路径
    """
    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), f"woosh_{int(time.time()*1000)}.wav")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if seed is None:
        seed = (int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)) % (2**31)

    tasks = [{
        "prompt": prompt,
        "output_path": output_path,
        "duration": duration,
        "seed": seed,
        "cfg": DEFAULT_CFG,
        "num_steps": DEFAULT_NUM_STEPS,
    }]

    results = _run_woosh_subprocess(tasks)
    if results and results[0].get("status") == "ok":
        return results[0]["output"]
    return None


def generate_audio_task(task):
    """
    单个音效生成任务（兼容 stabilityai 接口）

    :param task: 任务参数，支持字典或元组格式
    """
    MAX_RETRIES = 3

    if isinstance(task, dict):
        prompt = task.get("prompt")
        duration = task.get("duration", 5)
        output_path = task.get("output_path", None)
    else:
        prompt, duration, output_path = task

    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), f"woosh_{int(time.time()*1000)}.wav")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            seed = (int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16) + attempt) % (2**31)
            result = generate_audio(prompt, duration, output_path, seed=seed)
            if result is not None:
                return result
        except Exception as e:
            print(f"[Woosh] 生成失败 (第{attempt}/{MAX_RETRIES}次) {output_path}: {e}")
            if attempt == MAX_RETRIES:
                return None
            time.sleep(0.5)

    return None


def generate_audio_batch(tasks, max_workers=1):
    """
    批量生成多个音效

    :param tasks: 任务列表
    :param max_workers: 保留参数（兼容接口）
    :return: 生成的音频文件路径列表
    """
    print(f"\n[Woosh] 开始批量生成 {len(tasks)} 个音效")

    # 构建子进程任务列表
    subprocess_tasks = []
    for task in tasks:
        if isinstance(task, dict):
            prompt = task.get("prompt")
            duration = task.get("duration", 5)
            output_path = task.get("output_path")
        else:
            prompt, duration, output_path = task

        if output_path is None:
            output_path = os.path.join(tempfile.gettempdir(), f"woosh_{int(time.time()*1000)}.wav")

        seed = (int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)) % (2**31)
        subprocess_tasks.append({
            "prompt": prompt,
            "output_path": output_path,
            "duration": duration,
            "seed": seed,
            "cfg": DEFAULT_CFG,
            "num_steps": DEFAULT_NUM_STEPS,
        })

    results = _run_woosh_subprocess(subprocess_tasks)

    # 提取输出路径
    output_paths = []
    for r in results:
        if r.get("status") == "ok":
            output_paths.append(r["output"])
        else:
            output_paths.append(None)

    success = sum(1 for p in output_paths if p is not None)
    print(f"[Woosh] 批量生成完成！成功: {success}/{len(output_paths)}")
    return output_paths


def _run_woosh_subprocess(tasks):
    """
    通过子进程调用 Woosh 虚拟环境执行推理

    :param tasks: 任务列表，每个任务为 dict
    :return: 结果列表
    """
    available, msg = _check_woosh_env()
    if not available:
        print(f"[Woosh] 环境不可用: {msg}")
        return [{"status": "error", "error": msg} for _ in tasks]

    # 写推理脚本到临时文件
    script_path = os.path.join(WOOSH_REPO_DIR, "_infer_runner.py")
    with open(script_path, "w") as f:
        f.write(_WOOSH_INFER_SCRIPT)

    try:
        tasks_json = json.dumps(tasks, ensure_ascii=False)

        env = os.environ.copy()
        env['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'

        # 超时按任务数和每任务片段数估算
        max_duration = max(t.get("duration", 5) for t in tasks)
        num_segments_per_task = max(1, int(max_duration / WOOSH_MAX_DURATION) + 1)
        timeout = max(300, len(tasks) * num_segments_per_task * 30)

        result = subprocess.run(
            [WOOSH_VENV_PYTHON, script_path],
            input=tasks_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )

        if result.returncode != 0:
            print(f"[Woosh] 子进程错误: {result.stderr[:500]}")
            return [{"status": "error", "error": result.stderr[:200]} for _ in tasks]

        if result.stderr.strip():
            print(f"[Woosh] 子进程 stderr: {result.stderr[:1000]}")

        # 解析输出（每行一个 JSON 结果）
        results = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        return results

    except subprocess.TimeoutExpired:
        print("[Woosh] 子进程超时")
        return [{"status": "error", "error": "timeout"} for _ in tasks]
    except Exception as e:
        print(f"[Woosh] 子进程异常: {e}")
        return [{"status": "error", "error": str(e)} for _ in tasks]
    finally:
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
            except:
                pass


if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testoutput")
    os.makedirs(output_dir, exist_ok=True)

    tasks = [
        {"prompt": "old wooden door creaking open slowly, rusty hinges squeaking, heavy wood swinging",
         "duration": 2, "output_path": os.path.join(output_dir, "woosh_test_2s.wav")},
        {"prompt": "light footsteps with straw sandals on stone alley, soft tapping, walking pace",
         "duration": 5, "output_path": os.path.join(output_dir, "woosh_test_5s.wav")},
        {"prompt": "heavy rain pouring down continuously, steady rainfall on surface",
         "duration": 8, "output_path": os.path.join(output_dir, "woosh_test_8s.wav")},
        {"prompt": "campfire crackling and popping with wood hissing, embers snapping",
         "duration": 12, "output_path": os.path.join(output_dir, "woosh_test_12s.wav")},
    ]

    generate_audio_batch(tasks)
