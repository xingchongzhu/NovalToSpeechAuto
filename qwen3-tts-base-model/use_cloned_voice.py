import torch
import soundfile as sf
import argparse
import os
from qwen_tts import Qwen3TTSModel


def load_voice_list():
    """加载角色列表"""
    voice_list_path = "voice_list.txt"
    if not os.path.exists(voice_list_path):
        print(f"警告：角色列表文件 {voice_list_path} 不存在")
        return [], []
    
    built_in_voices = []
    generated_voices = []
    current_section = None
    
    with open(voice_list_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                if "内置角色" in line:
                    current_section = "built_in"
                elif "生成的角色" in line:
                    current_section = "generated"
                continue
            
            if current_section == "built_in":
                built_in_voices.append(line)
            elif current_section == "generated":
                generated_voices.append(line)
    
    return built_in_voices, generated_voices


def main():
    parser = argparse.ArgumentParser(description="使用保存的speaker embedding生成语音")
    parser.add_argument("--speaker_emb", type=str, help="保存的speaker embedding文件路径或名称")
    parser.add_argument("--text", type=str, help="要生成语音的文本")
    parser.add_argument("--output", type=str, default="output.wav", help="输出音频文件路径")
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", help="模型名称")
    parser.add_argument("--temperature", type=float, default=0.7, help="生成温度")
    parser.add_argument("--speaker_dir", type=str, default="./output_speaker", help="speaker embedding文件目录")
    parser.add_argument("--list_voices", action="store_true", help="列出所有可用角色")
    args = parser.parse_args()
    
    # 列出所有可用角色
    if args.list_voices:
        built_in_voices, generated_voices = load_voice_list()
        print("\n可用角色列表：")
        print("\n内置角色：")
        for voice in built_in_voices:
            print(f"  - {voice}")
        print("\n生成的角色：")
        for voice in generated_voices:
            print(f"  - {voice}")
        print(f"\n总角色数：{len(built_in_voices) + len(generated_voices)}")
        return
    
    # 检查必要参数
    if args.speaker_emb is None or args.text is None:
        parser.error("当不使用 --list_voices 时，必须提供 --speaker_emb 和 --text 参数")
    
    print(f"正在加载模型: {args.model_name}")
    # 使用Qwen3TTSModel加载模型
    tts_model = Qwen3TTSModel.from_pretrained(
        args.model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto"
    )
    
    # 检查speaker_emb是否是内置角色
    built_in_voices, generated_voices = load_voice_list()
    is_built_in = args.speaker_emb in built_in_voices
    
    # 处理speaker_emb参数
    speaker_emb = None
    if is_built_in:
        # 使用内置角色
        print(f"正在使用内置角色: {args.speaker_emb}")
    else:
        # 处理自定义角色
        speaker_emb_path = args.speaker_emb
        if not os.path.exists(speaker_emb_path):
            # 检查是否是带后缀的文件名
            if not speaker_emb_path.endswith('.pt') and not speaker_emb_path.endswith('.pth'):
                speaker_emb_path = f"{speaker_emb_path}.pt"
            # 从speaker_dir目录查找
            speaker_emb_path = os.path.join(args.speaker_dir, speaker_emb_path)
        
        print(f"正在加载自定义音色: {speaker_emb_path}")
        if not os.path.exists(speaker_emb_path):
            raise FileNotFoundError(f"speaker embedding文件不存在: {speaker_emb_path}")
        
        speaker_emb = torch.load(speaker_emb_path, map_location=tts_model.model.device)
    
    print(f"正在生成语音，文本: {args.text}")
    
    # 生成语音
    if is_built_in:
        # 使用内置角色生成
        wavs, sr = tts_model.generate_custom_voice(
            text=args.text,
            language="Chinese",
            speaker=args.speaker_emb,
            temperature=args.temperature
        )
        
        # 保存音频
        print(f"正在保存音频: {args.output}")
        sf.write(args.output, wavs[0], sr)
    else:
        # 使用自定义角色生成
        # 注意：这里需要根据模型类型选择不同的生成方法
        if tts_model.model.tts_model_type == "base":
            # base模型使用generate方法
            output = tts_model.model.generate(
                text=args.text,
                speaker_embedding=speaker_emb,
                temperature=args.temperature
            )
            
            # 保存音频
            print(f"正在保存音频: {args.output}")
            sf.write(args.output, output.audio[0].cpu().numpy(), tts_model.model.config.sampling_rate)
        else:
            # custom_voice模型使用generate_custom_voice方法
            print(f"警告：当前模型类型是 {tts_model.model.tts_model_type}，不支持直接使用speaker_embedding")
            print("请使用base类型的模型来生成自定义角色语音")
            return
    
    print(f"音频已保存到: {args.output}")
    print(f"\n验证克隆效果：")
    print(f"1. 生成的音频文件：{args.output}")
    print(f"2. 使用的角色：{args.speaker_emb}")
    print(f"3. 生成的文本：{args.text}")
    print(f"\n请播放音频文件 {args.output} 来验证克隆效果")


if __name__ == "__main__":
    main()
