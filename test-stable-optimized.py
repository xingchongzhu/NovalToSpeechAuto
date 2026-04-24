import torch
import torchaudio
import os
import threading
import time
from einops import rearrange
from stable_audio_tools import get_pretrained_model
from stable_audio_tools.inference.generation import generate_diffusion_cond

model = None
model_config = None
sample_rate = None
device = None

# ========== 优化参数配置 ==========
# 根据官方文档：https://huggingface.co/stabilityai/stable-audio-open-1.0
# 最大生成时长：47秒
MAX_DURATION = 47  # 官方限制

# 速度/质量权衡配置
QUALITY_PRESETS = {
    "fast": {
        "steps": 20,
        "cfg_scale": 5,
        "sigma_min": 0.5,
        "sigma_max": 200
    },
    "balanced": {
        "steps": 50,
        "cfg_scale": 7,
        "sigma_min": 0.3,
        "sigma_max": 500
    },
    "high": {
        "steps": 100,
        "cfg_scale": 10,
        "sigma_min": 0.1,
        "sigma_max": 1000
    },
    "ultra": {
        "steps": 200,
        "cfg_scale": 12,
        "sigma_min": 0.05,
        "sigma_max": 1000
    }
}

DEFAULT_PRESET = "balanced"
DEFAULT_SAMPLER_TYPE = "dpmpp-3m-sde"  # 最快的采样器之一

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testoutput")

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def print_parameters(prompt, duration, output_path, preset):
    params = QUALITY_PRESETS[preset]
    print("=" * 70)
    print("🎵 音频生成参数配置:")
    print("-" * 70)
    print(f"提示词 (prompt): {prompt[:50]}..." if len(prompt) > 50 else f"提示词 (prompt): {prompt}")
    print(f"生成时长 (duration): {duration} 秒 (最大支持: {MAX_DURATION}秒)")
    print(f"输出路径 (output_path): {output_path}")
    print(f"质量预设 (preset): {preset}")
    print("-" * 70)
    print("⚙️ 模型参数:")
    print(f"  运行设备 (device): {device}")
    print(f"  扩散步骤数 (steps): {params['steps']}")
    print(f"  提示词影响力 (cfg_scale): {params['cfg_scale']}")
    print(f"  最小噪声 (sigma_min): {params['sigma_min']}")
    print(f"  最大噪声 (sigma_max): {params['sigma_max']}")
    print(f"  采样器类型 (sampler_type): {DEFAULT_SAMPLER_TYPE}")
    print("=" * 70)

def initialize_model(force_cpu=False):
    """优化的模型初始化"""
    global model, model_config, sample_rate, device
    
    # 自动检测设备
    if force_cpu:
        device = "cpu"
    else:
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    
    print(f"🚀 正在加载模型到 {device}...")
    start_time = time.time()
    
    model, model_config = get_pretrained_model("stabilityai/stable-audio-open-1.0")
    sample_rate = model_config["sample_rate"]
    
    # 优化：使用float16加速（仅GPU）
    if device != "cpu":
        model = model.to(device, dtype=torch.float16)
        print(f"✅ 使用混合精度 (float16) 加速")
    else:
        model = model.to(device)
    
    model.eval()
    
    elapsed = time.time() - start_time
    print(f"✅ 模型加载完成！耗时: {elapsed:.2f} 秒")

def generate_audio(prompt, duration=10, output_path=None, preset=DEFAULT_PRESET):
    """优化的音频生成函数"""
    global model, model_config, sample_rate, device
    
    # 参数校验
    if duration > MAX_DURATION:
        print(f"⚠️ 时长 {duration}秒 超过模型最大限制 {MAX_DURATION}秒，已自动调整")
        duration = MAX_DURATION
    
    # 输出路径处理
    if output_path is None:
        output_path = f"generated_audio_{int(time.time())}.wav"
    elif not output_path.endswith('.wav'):
        output_path += '.wav'
    
    output_path = os.path.join(OUTPUT_DIR, output_path)
    
    # 检查是否已存在
    if os.path.exists(output_path):
        print(f"⚠️ 文件已存在，跳过生成: {output_path}")
        return output_path
    
    print_parameters(prompt, duration, output_path, preset)
    
    # 计算采样大小
    sample_size = int(round(sample_rate * duration))
    sample_size = max(1024, min(sample_size, sample_rate * MAX_DURATION))
    
    # 构建条件
    conditioning = [{
        "prompt": prompt,
        "seconds_start": 0,
        "seconds_total": duration
    }]
    
    # 获取预设参数
    params = QUALITY_PRESETS[preset]
    
    print(f"🎯 开始生成音频...")
    start_time = time.time()
    
    with torch.no_grad():
        output = generate_diffusion_cond(
            model,
            steps=params["steps"],
            cfg_scale=params["cfg_scale"],
            conditioning=conditioning,
            sample_size=sample_size,
            sigma_min=params["sigma_min"],
            sigma_max=params["sigma_max"],
            sampler_type=DEFAULT_SAMPLER_TYPE,
            device=device
        )
    
    elapsed = time.time() - start_time
    print(f"⏱️ 生成耗时: {elapsed:.2f} 秒")
    
    # 后处理优化
    output = rearrange(output, "b d n -> d (b n)")
    output = output.to(torch.float32).div(torch.max(torch.abs(output))).clamp(-1, 1).mul(32767).to(torch.int16).cpu()
    
    # 保存
    torchaudio.save(output_path, output, sample_rate)
    print(f"✅ 音频生成完成: {output_path}")
    
    return output_path

def generate_audio_thread(prompt, duration, output_path, preset=DEFAULT_PRESET):
    """线程安全的生成函数"""
    try:
        generate_audio(prompt, duration, output_path, preset)
    except Exception as e:
        print(f"❌ 生成失败 {output_path}: {e}")
        import traceback
        traceback.print_exc()

def generate_audio_batch(tasks, preset=DEFAULT_PRESET, parallel=True):
    """批量生成音频"""
    print(f"\n📦 批量生成 {len(tasks)} 个音频...")
    start_time = time.time()
    
    if parallel and device != "cpu" and len(tasks) > 1:
        # GPU环境下使用多线程
        threads = []
        for prompt, duration, output_path in tasks:
            t = threading.Thread(
                target=generate_audio_thread, 
                args=(prompt, duration, output_path, preset)
            )
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
    else:
        # CPU环境下串行执行（避免GIL锁问题）
        for prompt, duration, output_path in tasks:
            generate_audio(prompt, duration, output_path, preset)
    
    elapsed = time.time() - start_time
    print(f"\n🎉 批量生成完成！总耗时: {elapsed:.2f} 秒")

if __name__ == "__main__":
    ensure_output_dir()
    initialize_model()
    
    # 测试任务
    tasks = [
        ("footsteps on concrete floor, clear hard steps", 3, "走路声.wav"),
        ("gentle rain falling on leaves, soft ambient sound", 5, "雨声.wav"),
        ("birds chirping in a forest, morning atmosphere", 4, "鸟鸣.wav")
    ]
    
    # 使用 balanced 预设生成
    generate_audio_batch(tasks, preset="balanced")
    
    # 演示不同预设
    print("\n\n📊 预设对比示例:")
    print("-" * 70)
    print("| 预设 | steps | 速度 | 质量 | 适用场景 |")
    print("|------|-------|------|------|----------|")
    print("| fast | 20    | 最快 | 较低 | 快速预览 |")
    print("| balanced | 50  | 中等 | 良好 | 日常使用 |")
    print("| high | 100   | 较慢 | 较高 | 高质量输出 |")
    print("| ultra | 200  | 最慢 | 最高 | 最终成品 |")
    print("-" * 70)