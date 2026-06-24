import argparse
import inspect
import os
import sys
import time
import torch
import torchaudio
import soundfile as sf
from voxcpm import VoxCPM


ROLE_TESTS = [
    {
        "role": "旁白",
        "audio_file": "云健-中年男性磁性声音.mp3",
        "text": "山路渐远，旧事如潮，这一段旁白用于验证沉稳男声的克隆效果。",
    },
    {
        "role": "齐先生",
        "audio_file": "云健-中年男性磁性声音.mp3",
        "text": "先生语气平稳，这一段用于验证成熟沉稳角色的克隆配音效果。",
    },
    {
        "role": "阮邛",
        "audio_file": "云健-中年男性磁性声音.mp3",
        "text": "中年男子缓缓开口，这一段用于验证厚重磁性音色的克隆表现。",
    },
    {
        "role": "陈平安",
        "audio_file": "风发少年-男声-潇洒,磁性.mp3",
        "text": "少年抬头望向远方，这一段用于验证青年男性角色的克隆配音效果。",
    },
    {
        "role": "李槐",
        "audio_file": "风发少年-男声-潇洒,磁性.mp3",
        "text": "少年嗓音清亮，这一段用于验证轻快活泼路线的克隆效果。",
    },
    {
        "role": "董水井",
        "audio_file": "风发少年-男声-潇洒,磁性.mp3",
        "text": "年轻人语速平稳，这一段用于验证青年男声的日常对白克隆效果。",
    },
    {
        "role": "宁姚",
        "audio_file": "高冷姐-女声-知性,冷漠.mp3",
        "text": "她神色平静地开口，这一段用于验证冷感女声角色的克隆配音效果。",
    },
    {
        "role": "阮秀",
        "audio_file": "高冷姐-女声-知性,冷漠.mp3",
        "text": "少女声线清冷，这一段用于验证知性偏冷女声的克隆效果。",
    },
    {
        "role": "妇人",
        "audio_file": "高冷姐-女声-知性,冷漠.mp3",
        "text": "女子语气平淡，这一段用于验证成熟女性的对白克隆表现。",
    },
]


DEFAULT_REFERENCE_FILES = [
    "云健-中年男性磁性声音.mp3",
    "风发少年-男声-潇洒,磁性.mp3",
    "高冷姐-女声-知性,冷漠.mp3",
]


DEFAULT_TIMESTEPS = 4
DEFAULT_CFG_VALUE = 1.8
DEFAULT_MAX_LEN = 1536



def _safe_name(value):
    return value.replace('/', '_').replace('\\', '_').replace(' ', '_')



def _save_audio(audio, output_path, sample_rate):
    if isinstance(audio, torch.Tensor):
        waveform = audio.detach().cpu().to(torch.float32)
        if waveform.dim() == 3:
            waveform = waveform.squeeze(0)
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        waveform = torch.clamp(waveform, -1.0, 1.0)
        torchaudio.save(output_path, waveform, sample_rate)
        return

    sf.write(output_path, audio, sample_rate)



def _pick_reference_audio(clone_audio_dir, explicit_name=None):
    if explicit_name:
        candidate = os.path.join(clone_audio_dir, explicit_name)
        if os.path.exists(candidate):
            return candidate
        raise FileNotFoundError(f"指定参考音频不存在: {candidate}")

    for name in DEFAULT_REFERENCE_FILES:
        candidate = os.path.join(clone_audio_dir, name)
        if os.path.exists(candidate):
            return candidate

    for file_name in sorted(os.listdir(clone_audio_dir)):
        if file_name.lower().endswith((".mp3", ".wav", ".m4a")):
            return os.path.join(clone_audio_dir, file_name)

    raise FileNotFoundError(f"未在目录中找到可用参考音频: {clone_audio_dir}")



def _build_role_cases(clone_audio_dir, role_limit=None):
    role_cases = []
    for role_test in ROLE_TESTS:
        audio_path = os.path.join(clone_audio_dir, role_test["audio_file"])
        if not os.path.exists(audio_path):
            continue
        role_cases.append(
            {
                "role": role_test["role"],
                "audio_path": audio_path,
                "text": role_test["text"],
            }
        )

    if role_limit is not None:
        role_cases = role_cases[:role_limit]

    if not role_cases:
        raise RuntimeError("未找到可用于克隆验证的参考音频，请先补充样本。")

    return role_cases



def _generate_and_save(
    model,
    sample_rate,
    output_path,
    text,
    reference_wav_path,
    cfg_value,
    inference_timesteps,
    max_len,
):
    start_time = time.time()
    audio = model.generate(
        text=text,
        reference_wav_path=reference_wav_path,
        cfg_value=cfg_value,
        inference_timesteps=inference_timesteps,
        max_len=max_len,
    )
    gen_time = time.time() - start_time
    _save_audio(audio, output_path, sample_rate)
    audio_length = len(audio) / sample_rate if not isinstance(audio, torch.Tensor) else audio.shape[-1] / sample_rate
    return gen_time, audio_length



def test_voxcpm2_clone_demo(
    reference_audio_name=None,
    role_limit=None,
    inference_timesteps=DEFAULT_TIMESTEPS,
    cfg_value=DEFAULT_CFG_VALUE,
    max_len=DEFAULT_MAX_LEN,
    skip_warmup=True,
):
    """只使用参考音频做 VoxCPM2 声音克隆验证。"""

    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"当前 Python 版本为 {sys.version.split()[0]}，VoxCPM2 官方要求 Python >= 3.10。"
        )

    internal_generate_signature = inspect.signature(VoxCPM._generate)
    if "reference_wav_path" not in internal_generate_signature.parameters:
        raise RuntimeError(
            "当前安装的 voxcpm 包不支持 reference_wav_path。"
            "请升级到支持 VoxCPM2 克隆接口的版本后再验证。"
        )

    clone_audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"
    output_dir = "voxcpm2_clone_only_output"
    os.makedirs(output_dir, exist_ok=True)

    reference_audio = _pick_reference_audio(clone_audio_dir, reference_audio_name)
    role_cases = _build_role_cases(clone_audio_dir, role_limit)

    single_reference_cases = [
        {
            "name": "single_reference_clone_01",
            "text": "这是一段仅使用参考音频进行声音克隆的验证示例。",
            "reference_audio": reference_audio,
        },
        {
            "name": "single_reference_clone_02",
            "text": "如果这段音频的音色接近参考音频，就说明直接克隆方案是成立的。",
            "reference_audio": reference_audio,
        },
    ]

    try:
        print("\n🚀 初始化 VoxCPM2 模型...")
        start_time = time.time()
        vox = VoxCPM.from_pretrained(
            hf_model_id="OpenBMB/VoxCPM2",
            load_denoiser=False,
            cache_dir="/Users/zhuxingchong/.cache/huggingface/hub",
            optimize=not skip_warmup,
        )
        init_time = time.time() - start_time
        sample_rate = getattr(vox.tts_model, "sample_rate", 48000)
        print(f"✅ 模型初始化完成，耗时: {init_time:.2f}秒")
        print(f"🎚️ 输出采样率: {sample_rate}Hz")
        print(f"🎤 主参考音频: {reference_audio}")
        print(f"🎭 多角色克隆样本数: {len(role_cases)}")
        print(f"⚙️ timesteps={inference_timesteps}, cfg={cfg_value}, max_len={max_len}, skip_warmup={skip_warmup}")

        print("\n================ 单参考音频克隆验证 ================")
        for index, case in enumerate(single_reference_cases, 1):
            print(f"\n🎯 [{index}/{len(single_reference_cases)}] {case['name']}")
            print(f"   文本: {case['text']}")
            output_path = os.path.join(output_dir, f"{case['name']}.wav")
            gen_time, audio_length = _generate_and_save(
                vox,
                sample_rate,
                output_path,
                case["text"],
                case["reference_audio"],
                cfg_value,
                inference_timesteps,
                max_len,
            )
            print(f"💾 保存到: {output_path}")
            print(f"⏱️ 耗时: {gen_time:.2f}秒")
            print(f"📊 音频长度: {audio_length:.2f}秒")

        print("\n================ 多角色参考音频克隆验证 ================")
        for index, role_case in enumerate(role_cases, 1):
            role_name = role_case["role"]
            role_slug = _safe_name(role_name)
            print(f"\n🎭 [{index}/{len(role_cases)}] 角色: {role_name}")
            print(f"   参考音频: {role_case['audio_path']}")
            print(f"   克隆文本: {role_case['text']}")
            output_path = os.path.join(output_dir, f"role_{index:02d}_{role_slug}_clone.wav")
            gen_time, audio_length = _generate_and_save(
                vox,
                sample_rate,
                output_path,
                role_case["text"],
                role_case["audio_path"],
                cfg_value,
                inference_timesteps,
                max_len,
            )
            print(f"   💾 克隆输出: {output_path}")
            print(f"   ⏱️ 克隆耗时: {gen_time:.2f}秒")
            print(f"   📊 克隆时长: {audio_length:.2f}秒")

        print("\n🎉 纯参考音频克隆 demo 验证完成！")
        print(f"📂 输出目录: {os.path.abspath(output_dir)}")
        print("✅ 重点听不同角色之间的音色差异，以及生成音色和参考音频的相似度。")

    except Exception as error:
        print(f"\n❌ 测试失败: {error}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VoxCPM2 纯参考音频克隆验证脚本")
    parser.add_argument(
        "--reference-audio",
        type=str,
        default=None,
        help="主参考音频文件名，默认自动从 clone-audio 中选择",
    )
    parser.add_argument(
        "--role-limit",
        type=int,
        default=None,
        help="限制多角色克隆验证数量，默认使用全部可用角色",
    )
    parser.add_argument(
        "--timesteps",
        type=int,
        default=DEFAULT_TIMESTEPS,
        help="推理步数，越小越快，默认 4",
    )
    parser.add_argument(
        "--cfg",
        type=float,
        default=DEFAULT_CFG_VALUE,
        help="CFG guidance，默认 1.8",
    )
    parser.add_argument(
        "--max-len",
        type=int,
        default=DEFAULT_MAX_LEN,
        help="最大生成长度，默认 1536",
    )
    parser.add_argument(
        "--with-warmup",
        action="store_true",
        help="启用模型 warm-up；默认关闭以缩短首次等待时间",
    )
    arguments = parser.parse_args()
    test_voxcpm2_clone_demo(
        reference_audio_name=arguments.reference_audio,
        role_limit=arguments.role_limit,
        inference_timesteps=arguments.timesteps,
        cfg_value=arguments.cfg,
        max_len=arguments.max_len,
        skip_warmup=not arguments.with_warmup,
    )
