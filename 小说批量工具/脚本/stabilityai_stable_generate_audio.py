import torch
import torchaudio
import os
import threading
import time
import concurrent.futures
from einops import rearrange
from stable_audio_tools import get_pretrained_model
from stable_audio_tools.inference.generation import generate_diffusion_cond

model = None
model_config = None
sample_rate = None
device = "cpu"

DEFAULT_STEPS = 60
DEFAULT_CFG_SCALE = 7
DEFAULT_SIGMA_MIN = 0.3
DEFAULT_SIGMA_MAX = 500
DEFAULT_SAMPLER_TYPE = "dpmpp-3m-sde"
# ========== 优化参数配置 ==========
# 根据官方文档：https://huggingface.co/stabilityai/stable-audio-open-1.0
# 最大生成时长：47秒
MAX_DURATION = 47  # 官方限制

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testoutput")

# 长音频生成相关常量
CROSSFADE_DURATION = 2.0  # 交叉淡入淡出时长（秒）
OVERLAP_DURATION = 3.0    # 片段重叠时长（秒）

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def print_parameters(prompt, duration, output_path):
    print("=" * 60)
    print("音频生成参数配置:")
    print("-" * 60)
    print(f"提示词 (prompt): {prompt}")
    print(f"生成时长 (duration): {duration} 秒")
    print(f"输出路径 (output_path): {output_path}")
    print("-" * 60)
    print("模型参数:")
    print(f"  运行设备 (device): {device}")
    print(f"  扩散步骤数 (steps): {DEFAULT_STEPS} (推荐范围: 20-500)")
    print(f"  提示词影响力 (cfg_scale): {DEFAULT_CFG_SCALE} (推荐范围: 5-15)")
    print(f"  最小噪声 (sigma_min): {DEFAULT_SIGMA_MIN} (推荐范围: 0.01-1.0)")
    print(f"  最大噪声 (sigma_max): {DEFAULT_SIGMA_MAX} (推荐范围: 100-1000)")
    print(f"  采样器类型 (sampler_type): {DEFAULT_SAMPLER_TYPE}")
    print("=" * 60)

def initialize_model():
    global model, model_config, sample_rate, device
    print(f"🚀 正在加载模型到 {device}...")
    start_time = time.time()
    model, model_config = get_pretrained_model("stabilityai/stable-audio-open-1.0")
    sample_rate = model_config["sample_rate"]
    model = model.to(device)
    model.eval()
    elapsed = time.time() - start_time
    print(f"✅ 模型加载完成！耗时: {elapsed:.2f} 秒")

def generate_audio(prompt, duration=10, output_path=None):
    """
    生成单个音频（主接口，不包含模型初始化检查）
    :param prompt: 提示词
    :param duration: 时长（秒），最大47秒
    :param output_path: 输出路径
    :return: 生成的音频文件路径
    """
    global model, model_config, sample_rate, device
    
    if output_path is None:
        output_path = f"generated_audio_{int(torch.rand(1).item() * 10000)}.wav"
    elif not output_path.endswith('.wav'):
        output_path += '.wav'
    
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 参数校验
    if duration > MAX_DURATION:
        print(f"⚠️ 时长 {duration}秒 超过模型最大限制 {MAX_DURATION}秒，已自动调整")
        duration = MAX_DURATION
    
    print_parameters(prompt, duration, output_path)
    
    # 计算采样大小
    sample_size = int(round(sample_rate * duration))
    sample_size = max(1024, min(sample_size, sample_rate * MAX_DURATION))
    
    conditioning = [{
        "prompt": prompt,
        "seconds_start": 0,
        "seconds_total": duration
    }]
    
    print(f"开始生成音频...")
    with torch.no_grad():
        output = generate_diffusion_cond(
            model,
            steps=DEFAULT_STEPS,
            cfg_scale=DEFAULT_CFG_SCALE,
            conditioning=conditioning,
            sample_size=sample_size,
            sigma_min=DEFAULT_SIGMA_MIN,
            sigma_max=DEFAULT_SIGMA_MAX,
            sampler_type=DEFAULT_SAMPLER_TYPE,
            device=device
        )
    
    output = rearrange(output, "b d n -> d (b n)")
    output = output.to(torch.float32).div(torch.max(torch.abs(output))).clamp(-1, 1).mul(32767).to(torch.int16).cpu()
    
    torchaudio.save(output_path, output, sample_rate)
    print(f"✅ 音频生成完成: {output_path}")
    return output_path

def generate_audio_with_init(prompt, duration=10, output_path=None):
    """
    生成单个音频（包含模型初始化检查的公共接口）
    :param prompt: 提示词
    :param duration: 时长（秒），最大47秒
    :param output_path: 输出路径
    :return: 生成的音频文件路径
    """
    global model
    
    if model is None:
        initialize_model()
    
    return generate_audio(prompt, duration, output_path)

def generate_audio_task(task):
    """
    单个音频生成任务（用于多线程）
    :param task: 任务参数，可以是：
                 - 元组格式: (prompt, duration, output_path)
                 - 字典格式: {"prompt": "...", "duration": 10, "output_path": None}
    """
    if isinstance(task, dict):
        prompt = task.get("prompt")
        duration = task.get("duration", 10)
        output_path = task.get("output_path", None)
    else:
        prompt, duration, output_path = task
    
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, f"generated_audio_{int(torch.rand(1).item() * 10000)}.wav")
    
    try:
        return generate_long_audio(prompt, duration, output_path)
    except Exception as e:
        print(f"❌ 生成失败 {output_path}: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_audio_batch(tasks, max_workers=5):
    """
    批量生成多个音频（多线程并行）
    :param tasks: 任务列表，每个任务是 (prompt, duration, output_path) 元组
    :param max_workers: 最大并行线程数（CPU上建议设为5，避免资源竞争）
    :return: 生成的音频文件路径列表
    """
    global model
    if model is None:
        initialize_model()
    
    print(f"\n📦 开始批量生成 {len(tasks)} 个音频，最大并行数: {max_workers}")
    
    results = []
    
    if max_workers == 1 or len(tasks) <= 1:
        for task in tasks:
            result = generate_audio_task(task)
            results.append(result)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(generate_audio_task, task) for task in tasks]
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"❌ 线程执行异常: {e}")
                    results.append(None)
    
    print(f"\n🎉 批量音频生成完成！成功: {sum(1 for r in results if r is not None)}/{len(results)}")
    return results

def generate_long_audio(prompt, duration, output_path=None):
    """
    生成超过47秒的长音频（通过分块生成+智能拼接实现）
    
    :param prompt: 提示词
    :param duration: 目标时长（秒），可超过47秒
    :param output_path: 输出路径
    :return: 生成的音频文件路径
    
    实现策略：
    1. 将长音频分成多个47秒的片段
    2. 每个片段使用相同的提示词生成
    3. 使用交叉淡入淡出技术平滑连接片段
    4. 添加重叠区域确保过渡自然
    """
    global model
    
    if model is None:
        initialize_model()
    
    if output_path is None:
        output_path = f"generated_long_audio_{int(torch.rand(1).item() * 10000)}.wav"
    elif not output_path.endswith('.wav'):
        output_path += '.wav'
    
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    if duration <= MAX_DURATION:
        print(f"⏱️  目标时长 {duration}秒 <= {MAX_DURATION}秒，直接生成")
        return generate_audio(prompt, duration, output_path)
    
    print("=" * 60)
    print(f"🔊 生成长音频: {duration}秒（超过{MAX_DURATION}秒限制）")
    print("=" * 60)
    
    # 计算需要多少个片段
    # 每个片段实际生成 MAX_DURATION 秒，但有效使用 MAX_DURATION - OVERLAP_DURATION 秒
    effective_duration_per_segment = MAX_DURATION - OVERLAP_DURATION
    num_segments = int((duration + effective_duration_per_segment - 1) // effective_duration_per_segment)
    
    print(f"📦 将分成 {num_segments} 个片段生成")
    print(f"   每个片段: {MAX_DURATION}秒")
    print(f"   重叠区域: {OVERLAP_DURATION}秒")
    print(f"   交叉淡入淡出: {CROSSFADE_DURATION}秒")
    
    segment_paths = []
    
    for i in range(num_segments):
        segment_output_path = f"{output_path}_segment_{i+1}.wav"
        
        # 计算这个片段应该覆盖的时间范围（用于条件生成）
        segment_start = i * effective_duration_per_segment
        segment_end = min(segment_start + MAX_DURATION, duration)
        segment_duration = segment_end - segment_start
        
        print(f"\n🔄 生成片段 {i+1}/{num_segments}: {segment_duration:.1f}秒")
        
        # 使用时间信息增强提示词，帮助保持连续性
        time_context = f", time segment {i+1} of {num_segments}"
        segment_prompt = prompt + time_context
        
        try:
            generated_path = generate_audio(segment_prompt, segment_duration, segment_output_path)
            segment_paths.append(generated_path)
        except Exception as e:
            print(f"❌ 生成片段 {i+1} 失败: {e}")
            raise
    
    print(f"\n🔗 合并 {len(segment_paths)} 个片段...")
    
    # 加载所有片段
    segments = []
    for path in segment_paths:
        waveform, sr = torchaudio.load(path)
        segments.append(waveform)
    
    # 计算交叉淡入淡出的采样数
    crossfade_samples = int(CROSSFADE_DURATION * sample_rate)
    overlap_samples = int(OVERLAP_DURATION * sample_rate)
    
    # 合并片段（使用交叉淡入淡出）
    result = segments[0]
    
    for i in range(1, len(segments)):
        prev_segment = result
        curr_segment = segments[i]
        
        # 取前一个片段的末尾部分进行交叉淡入淡出
        prev_segment_end = prev_segment[:, -crossfade_samples:]
        
        # 取当前片段的开头部分进行交叉淡入淡出
        curr_segment_start = curr_segment[:, :crossfade_samples]
        
        # 创建淡入淡出曲线
        fade_out_curve = torch.linspace(1.0, 0.0, crossfade_samples).view(1, -1)
        fade_in_curve = torch.linspace(0.0, 1.0, crossfade_samples).view(1, -1)
        
        # 应用淡入淡出
        prev_segment_end_faded = prev_segment_end * fade_out_curve
        curr_segment_faded = curr_segment_start * fade_in_curve
        
        # 混合重叠部分
        overlap_result = prev_segment_end_faded + curr_segment_faded
        
        # 拼接：前面部分（去掉交叉淡入淡出部分） + 混合部分 + 当前片段剩余部分
        result = torch.cat([
            prev_segment[:, :-crossfade_samples],
            overlap_result,
            curr_segment[:, crossfade_samples:]
        ], dim=1)
    
    # 归一化并转换格式
    result = result.to(torch.float32)
    result = result.div(torch.max(torch.abs(result))).clamp(-1, 1).mul(32767).to(torch.int16)
    
    # 保存最终结果
    torchaudio.save(output_path, result, sample_rate)
    print(f"✅ 长音频生成完成: {output_path}")
    print(f"   总时长: {result.shape[1] / sample_rate:.2f}秒")
    
    # 清理临时片段文件
    for path in segment_paths:
        os.remove(path)
        print(f"🗑️  删除临时片段: {path}")
    
    return output_path


if __name__ == "__main__":
    ensure_output_dir()
    
    tasks = [
        ("natural teenage sarcastic laugh, mocking and taunting tone, human voice, clear and smooth, warm timbre, not distorted", 3, os.path.join(OUTPUT_DIR, "讥讽笑声.wav")),
        ("footsteps on concrete floor, clear hard steps", 3, os.path.join(OUTPUT_DIR, "走路声.wav")),
        ("128 BPM tech house drum loop", 3, os.path.join(OUTPUT_DIR, "test.wav"))
    ]
    
    generate_audio_batch(tasks)