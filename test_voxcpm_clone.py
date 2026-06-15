import argparse
import inspect
import json
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
        "clone_text": "山路渐远，旧事如潮，这一段旁白用于验证沉稳男声的克隆效果。",
        "style_text": "（语速稍慢，叙事感更强）山风拂过小镇，尘封往事也随之苏醒。",
    },
    {
        "role": "齐先生",
        "audio_file": "云健-中年男性磁性声音.mp3",
        "clone_text": "先生语气平稳，这一段用于验证成熟沉稳角色的克隆配音效果。",
        "style_text": "（更从容一些，带一点长者气度）有些道理，要走过很远的路之后，才会真正明白。",
    },
    {
        "role": "阮邛",
        "audio_file": "云健-中年男性磁性声音.mp3",
        "clone_text": "中年男子缓缓开口，这一段用于验证厚重磁性音色的克隆表现。",
        "style_text": "（低沉一些，压迫感更强）该来的总会来，急也没有用。",
    },
    {
        "role": "陈平安",
        "audio_file": "风发少年-男声-潇洒,磁性.mp3",
        "clone_text": "少年抬头望向远方，这一段用于验证青年男性角色的克隆配音效果。",
        "style_text": "（带一点朝气，语气更轻快）原来前路还长，我总要自己去看看。",
    },
    {
        "role": "李槐",
        "audio_file": "风发少年-男声-潇洒,磁性.mp3",
        "clone_text": "少年嗓音清亮，这一段用于验证轻快活泼路线的克隆效果。",
        "style_text": "（更跳脱一些，带一点少年感）我就不信这点小事，还能难得住我。",
    },
    {
        "role": "董水井",
        "audio_file": "风发少年-男声-潇洒,磁性.mp3",
        "clone_text": "年轻人语速平稳，这一段用于验证青年男声的日常对白克隆效果。",
        "style_text": "（自然一点，语气更生活化）今天铺子里不忙，正好可以坐下来慢慢聊。",
    },
    {
        "role": "宁姚",
        "audio_file": "高冷姐-女声-知性,冷漠.mp3",
        "clone_text": "她神色平静地开口，这一段用于验证冷感女声角色的克隆配音效果。",
        "style_text": "（冷静克制，语速略慢）别着急，下一个决定，最好先想清楚。",
    },
    {
        "role": "阮秀",
        "audio_file": "高冷姐-女声-知性,冷漠.mp3",
        "clone_text": "少女声线清冷，这一段用于验证知性偏冷女声的克隆效果。",
        "style_text": "（柔一点，但依旧克制）很多事情，不说出来，不代表心里没有答案。",
    },
    {
        "role": "妇人",
        "audio_file": "高冷姐-女声-知性,冷漠.mp3",
        "clone_text": "女子语气平淡，这一段用于验证成熟女性的对白克隆表现。",
        "style_text": "（更稳一些，带一点距离感）你先坐下，事情一件一件说，别乱。",
    },
]


PLACEHOLDER_PROMPT_PREFIXES = (
    "请填写",
    "待填写",
    "todo",
    "tbd",
)



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



def _load_prompt_texts(clone_audio_dir):
    prompt_texts_path = os.path.join(clone_audio_dir, "prompt_texts.json")
    if not os.path.exists(prompt_texts_path):
        raise FileNotFoundError(
            f"未找到参考转写文件: {prompt_texts_path}，请先补充参考音频原文。"
        )

    with open(prompt_texts_path, "r", encoding="utf-8") as file:
        return json.load(file)



def _is_placeholder_prompt(text):
    if not isinstance(text, str):
        return True
    normalized = text.strip()
    if not normalized:
        return True
    lower_text = normalized.lower()
    return any(lower_text.startswith(prefix) for prefix in PLACEHOLDER_PROMPT_PREFIXES)



def _get_prompt_text(prompt_texts, audio_path):
    prompt_key = os.path.splitext(os.path.basename(audio_path))[0]
    prompt_text = prompt_texts.get(prompt_key)
    if not isinstance(prompt_text, str) or not prompt_text.strip():
        return None, False
    prompt_text = prompt_text.strip()
    return prompt_text, not _is_placeholder_prompt(prompt_text)



def _pick_reference_audio(clone_audio_dir, explicit_name=None):
    if explicit_name:
        candidate = os.path.join(clone_audio_dir, explicit_name)
        if os.path.exists(candidate):
            return candidate
        raise FileNotFoundError(f"指定参考音频不存在: {candidate}")

    preferred_names = [
        "云健-中年男性磁性声音.mp3",
        "风发少年-男声-潇洒,磁性.mp3",
        "高冷姐-女声-知性,冷漠.mp3",
    ]
    for name in preferred_names:
        candidate = os.path.join(clone_audio_dir, name)
        if os.path.exists(candidate):
            return candidate

    for file_name in sorted(os.listdir(clone_audio_dir)):
        if file_name.lower().endswith((".mp3", ".wav", ".m4a")):
            return os.path.join(clone_audio_dir, file_name)

    raise FileNotFoundError(f"未在目录中找到可用参考音频: {clone_audio_dir}")



def _build_role_cases(clone_audio_dir, prompt_texts, limit=None):
    role_cases = []
    for role_test in ROLE_TESTS:
        audio_path = os.path.join(clone_audio_dir, role_test["audio_file"])
        if not os.path.exists(audio_path):
            continue

        prompt_text, has_real_prompt_text = _get_prompt_text(prompt_texts, audio_path)
        role_cases.append(
            {
                "role": role_test["role"],
                "audio_path": audio_path,
                "prompt_text": prompt_text,
                "has_real_prompt_text": has_real_prompt_text,
                "clone_text": role_test["clone_text"],
                "style_text": role_test["style_text"],
            }
        )

    if limit is not None:
        role_cases = role_cases[:limit]

    if not role_cases:
        raise RuntimeError("未找到可用于多角色克隆验证的参考音频，请先补充样本。")

    return role_cases



def _generate_and_save(model, sample_rate, output_path, text, **kwargs):
    start_time = time.time()
    audio = model.generate(text=text, **kwargs)
    gen_time = time.time() - start_time
    _save_audio(audio, output_path, sample_rate)
    audio_length = len(audio) / sample_rate if not isinstance(audio, torch.Tensor) else audio.shape[-1] / sample_rate
    return gen_time, audio_length



def test_voxcpm2_demo(reference_audio_name=None, role_limit=None):
    """按官方场景 + 多角色克隆场景验证 VoxCPM2 方案。"""

    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"当前 Python 版本为 {sys.version.split()[0]}，VoxCPM2 官方要求 Python >= 3.10。"
        )

    generate_signature = inspect.signature(VoxCPM.generate)
    supports_reference_wav = "reference_wav_path" in generate_signature.parameters
    if not supports_reference_wav:
        raise RuntimeError(
            "当前安装的 voxcpm 包接口仍为旧版，不包含 reference_wav_path。"
            "请在 Python 3.10+ 环境升级到支持 VoxCPM2 的最新版后再验证。"
        )

    clone_audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"
    output_dir = "voxcpm2_demo_output"
    os.makedirs(output_dir, exist_ok=True)

    prompt_texts = _load_prompt_texts(clone_audio_dir)
    reference_audio = _pick_reference_audio(clone_audio_dir, reference_audio_name)
    prompt_text, has_real_prompt_text = _get_prompt_text(prompt_texts, reference_audio)
    role_cases = _build_role_cases(clone_audio_dir, prompt_texts, role_limit)
    role_cases_with_real_prompt = [item for item in role_cases if item["has_real_prompt_text"]]

    official_cases = [
        {
            "name": "01_basic_tts",
            "text": "VoxCPM2 支持多语种语音合成，也支持高保真声音克隆。",
            "kwargs": {"cfg_value": 2.0, "inference_timesteps": 10},
        },
        {
            "name": "02_voice_design",
            "text": "（沉稳的中年男声，语速稍慢，带一点故事感）山风吹过小镇，旧故事也跟着醒来。",
            "kwargs": {"cfg_value": 2.0, "inference_timesteps": 10},
        },
        {
            "name": "03_controllable_clone",
            "text": "（语气轻快一些）这是一段使用参考音色生成的可控克隆示例。",
            "kwargs": {
                "reference_wav_path": reference_audio,
                "cfg_value": 2.0,
                "inference_timesteps": 10,
            },
        },
    ]

    if has_real_prompt_text:
        official_cases.append(
            {
                "name": "04_ultimate_clone",
                "text": "这是一段结合参考音频与精确转写生成的高保真克隆示例。",
                "kwargs": {
                    "reference_wav_path": reference_audio,
                    "prompt_wav_path": reference_audio,
                    "prompt_text": prompt_text,
                    "cfg_value": 2.0,
                    "inference_timesteps": 10,
                },
            }
        )

    try:
        print("\n🚀 初始化 VoxCPM2 模型...")
        start_time = time.time()
        vox = VoxCPM.from_pretrained(
            hf_model_id="OpenBMB/VoxCPM2",
            load_denoiser=False,
            cache_dir="/Users/zhuxingchong/.cache/huggingface/hub",
        )
        init_time = time.time() - start_time
        sample_rate = getattr(vox.tts_model, "sample_rate", 48000)
        print(f"✅ 模型初始化完成，耗时: {init_time:.2f}秒")
        print(f"🎚️ 输出采样率: {sample_rate}Hz")
        print(f"🎤 官方 demo 参考音频: {reference_audio}")
        print(f"🎭 多角色克隆样本数: {len(role_cases)}")
        print(f"🧾 具备真实转写的角色数: {len(role_cases_with_real_prompt)}")

        if not has_real_prompt_text:
            print("⚠️ 官方 demo 参考音频当前没有真实 prompt_text，已跳过 04 高保真克隆验证。")
        if not role_cases_with_real_prompt:
            print("⚠️ 当前所有角色都缺少真实转写，多角色部分仅验证 reference_wav_path 克隆，不做高保真 prompt 克隆。")

        print("\n================ 官方场景验证 ================")
        for index, case in enumerate(official_cases, 1):
            print(f"\n🎯 [{index}/{len(official_cases)}] {case['name']}")
            print(f"   文本: {case['text']}")
            output_path = os.path.join(output_dir, f"{case['name']}.wav")
            gen_time, audio_length = _generate_and_save(
                vox,
                sample_rate,
                output_path,
                case["text"],
                **case["kwargs"],
            )
            print(f"💾 保存到: {output_path}")
            print(f"⏱️ 耗时: {gen_time:.2f}秒")
            print(f"📊 音频长度: {audio_length:.2f}秒")

        print("\n================ 多角色克隆验证 ================")
        for index, role_case in enumerate(role_cases, 1):
            role_name = role_case["role"]
            role_slug = _safe_name(role_name)
            print(f"\n🎭 [{index}/{len(role_cases)}] 角色: {role_name}")
            print(f"   参考音频: {role_case['audio_path']}")

            clone_output = os.path.join(output_dir, f"role_{index:02d}_{role_slug}_clone.wav")
            clone_time, clone_length = _generate_and_save(
                vox,
                sample_rate,
                clone_output,
                role_case["clone_text"],
                reference_wav_path=role_case["audio_path"],
                cfg_value=2.0,
                inference_timesteps=10,
            )
            print(f"   🧬 克隆文本: {role_case['clone_text']}")
            print(f"   💾 克隆输出: {clone_output}")
            print(f"   ⏱️ 克隆耗时: {clone_time:.2f}秒")
            print(f"   📊 克隆时长: {clone_length:.2f}秒")

            if role_case["has_real_prompt_text"]:
                style_output = os.path.join(output_dir, f"role_{index:02d}_{role_slug}_style_clone.wav")
                style_time, style_length = _generate_and_save(
                    vox,
                    sample_rate,
                    style_output,
                    role_case["style_text"],
                    reference_wav_path=role_case["audio_path"],
                    prompt_wav_path=role_case["audio_path"],
                    prompt_text=role_case["prompt_text"],
                    cfg_value=2.0,
                    inference_timesteps=10,
                )
                print(f"   🎨 风格文本: {role_case['style_text']}")
                print(f"   💾 风格克隆输出: {style_output}")
                print(f"   ⏱️ 风格耗时: {style_time:.2f}秒")
                print(f"   📊 风格时长: {style_length:.2f}秒")
            else:
                print("   ⚠️ 缺少真实 prompt_text，已跳过高保真风格克隆。")

        print("\n🎉 VoxCPM2 demo 与多角色克隆验证完成！")
        print(f"📂 输出目录: {os.path.abspath(output_dir)}")
        print("✅ 现在更适合先对比不同角色的 reference_wav_path 克隆效果，等补齐真实转写后再做高保真 prompt 克隆复测。")

    except Exception as error:
        print(f"\n❌ 测试失败: {error}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VoxCPM2 官方场景 + 多角色克隆验证脚本")
    parser.add_argument(
        "--reference-audio",
        type=str,
        default=None,
        help="官方 demo 使用的参考音频文件名，默认自动从 clone-audio 中选择",
    )
    parser.add_argument(
        "--role-limit",
        type=int,
        default=None,
        help="限制多角色克隆验证数量，默认使用全部可用角色",
    )
    arguments = parser.parse_args()
    test_voxcpm2_demo(
        reference_audio_name=arguments.reference_audio,
        role_limit=arguments.role_limit,
    )
