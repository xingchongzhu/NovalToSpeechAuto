import concurrent.futures
import hashlib
import os
import subprocess
from typing import Dict, List, Tuple, Union

TaskType = Union[Tuple[str, float, str], Dict[str, object]]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../.."))
MLX_DIR = os.path.join(PROJECT_ROOT, "stable-audio3-lab", "stable-audio-3", "optimized", "mlx")
SA3_BIN = os.path.join(MLX_DIR, "sa3")
DEFAULT_DECODER = "same-s"
DEFAULT_SECONDS = 120.0


def _ensure_runtime() -> None:
    if not os.path.exists(SA3_BIN):
        raise FileNotFoundError(
            f"未找到 Stable Audio 3 MLX 入口: {SA3_BIN}。"
            "请先在项目根目录完成 stable-audio3-lab 环境安装。"
        )


def _normalize_task(task: TaskType) -> Dict[str, object]:
    if isinstance(task, dict):
        prompt = str(task.get("prompt", "")).strip()
        duration = float(task.get("duration", DEFAULT_SECONDS) or DEFAULT_SECONDS)
        output_path = str(task.get("output_path", "")).strip()
    else:
        prompt, duration, output_path = task
        prompt = str(prompt).strip()
        duration = float(duration)
        output_path = str(output_path).strip()

    if not prompt:
        raise ValueError("背景音提示词不能为空")
    if not output_path:
        raise ValueError("背景音输出路径不能为空")
    if not output_path.endswith(".wav"):
        output_path += ".wav"

    return {
        "prompt": prompt,
        "duration": max(1.0, duration),
        "output_path": output_path,
    }


def _pick_dit_model(prompt: str) -> str:
    lowered = prompt.lower()
    music_keywords = [
        "music", "melody", "instrumental", "piano", "orchestral",
        "guitar", "drone", "choir", "bpm", "rhythm", "theme",
    ]
    if any(keyword in lowered for keyword in music_keywords):
        return "sm-music"
    return "sm-sfx"


def _build_command(task: Dict[str, object]) -> List[str]:
    prompt = str(task["prompt"])
    duration = float(task["duration"])
    output_path = str(task["output_path"])
    dit = _pick_dit_model(prompt)
    return [
        SA3_BIN,
        "--prompt", prompt,
        "--dit", dit,
        "--decoder", DEFAULT_DECODER,
        "--seconds", str(duration),
        "--out", output_path,
    ]


def _run_task(task: TaskType) -> str:
    _ensure_runtime()
    normalized = _normalize_task(task)
    output_path = str(normalized["output_path"])
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    prompt = str(normalized["prompt"])
    duration = float(normalized["duration"])
    dit = _pick_dit_model(prompt)
    cache_key = hashlib.md5(f"{prompt}|{duration}|{dit}".encode("utf-8")).hexdigest()[:8]
    print(f"[StableAudio3-BGM] 生成背景音 | model={dit} | duration={duration:.1f}s | cache={cache_key}")
    print(f"[StableAudio3-BGM] 输出路径: {output_path}")

    command = _build_command(normalized)
    result = subprocess.run(
        command,
        cwd=MLX_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Stable Audio 3 背景音生成失败: {output_path}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return output_path


def generate_audio_batch(tasks: List[TaskType], max_workers: int = 2):
    if not tasks:
        return []

    worker_count = max(1, min(max_workers or 1, len(tasks), 2))
    if worker_count == 1:
        results = []
        for task in tasks:
            try:
                results.append(_run_task(task))
            except Exception as exc:
                print(f"[StableAudio3-BGM] 生成失败: {exc}")
                results.append(None)
        return results

    ordered_results = [None] * len(tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(_run_task, task): index
            for index, task in enumerate(tasks)
        }
        for future in concurrent.futures.as_completed(future_map):
            index = future_map[future]
            try:
                ordered_results[index] = future.result()
            except Exception as exc:
                print(f"[StableAudio3-BGM] 生成失败: {exc}")
                ordered_results[index] = None
    return ordered_results
