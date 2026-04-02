import torch
import librosa
import argparse
import os
import glob
from qwen_tts import Qwen3TTSModel


def get_built_in_voices(tts_model):
    """获取内置角色列表"""
    if hasattr(tts_model.model, 'supported_speakers'):
        return list(tts_model.model.supported_speakers)
    else:
        # 默认内置角色列表
        return [
            "uncle_fu",
            "Vivian",
            "Ryan",
            "XiaoWang",
            "ZhangYe",
            "LiSi",
            "WangWu"
        ]


def generate_voice_list(output_dir, tts_model=None):
    """生成角色列表，包括Qwen自带的和生成的"""
    # 加载内置角色列表
    built_in_voices = get_built_in_voices(tts_model) if tts_model else []
    
    # 获取生成的角色列表
    generated_voices = []
    if os.path.exists(output_dir):
        for file in os.listdir(output_dir):
            if file.endswith('.pt'):
                voice_name = os.path.splitext(file)[0]
                generated_voices.append(voice_name)
    
    # 合并所有角色
    all_voices = built_in_voices + generated_voices
    
    # 保存角色列表
    with open("voice_list.txt", "w", encoding="utf-8") as f:
        f.write("# Qwen3-TTS 角色列表\n")
        f.write("# 内置角色\n")
        for voice in built_in_voices:
            f.write(f"{voice}\n")
        
        f.write("\n# 生成的角色\n")
        for voice in generated_voices:
            f.write(f"{voice}\n")
    
    print(f"\n已生成角色列表: voice_list.txt")
    print(f"内置角色: {len(built_in_voices)} 个")
    print(f"生成角色: {len(generated_voices)} 个")
    print(f"总角色数: {len(all_voices)} 个")
    print(f"\n内置角色列表:")
    for voice in built_in_voices:
        print(f"  - {voice}")
    print(f"\n生成角色列表:")
    for voice in generated_voices:
        print(f"  - {voice}")


def process_single_audio(tts_model, ref_audio_path, output_path):
    """处理单个音频文件，提取并保存speaker embedding"""
    # 检查输出文件是否已存在，如果存在则跳过
    if os.path.exists(output_path):
        print(f"\n跳过已存在的音色文件: {output_path}")
        return output_path
    
    print(f"\n正在处理音频: {ref_audio_path}")
    
    # 1. 加载音频
    ref_audio, sr = librosa.load(ref_audio_path, sr=24000)  # Qwen3-TTS使用24000采样率
    
    # 2. 提取音色特征
    print(f"正在提取音色特征...")
    with torch.no_grad():
        # 使用Qwen3TTSModel的extract_speaker_embedding方法
        speaker_embedding = tts_model.model.extract_speaker_embedding(audio=ref_audio, sr=sr)
    
    # 保存音色文件
    print(f"正在保存音色文件: {output_path}")
    torch.save(speaker_embedding, output_path)
    print(f"已保存自定义音色：{output_path}")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="克隆声音并保存speaker embedding")
    parser.add_argument("--ref_audio", type=str, help="参考音频文件路径（单个文件模式）")
    parser.add_argument("--output_path", type=str, help="保存speaker embedding的文件路径（单个文件模式）")
    parser.add_argument("--input_dir", type=str, default="./clone-audio", help="输入音频目录路径（目录模式）")
    parser.add_argument("--output_dir", type=str, default="./output_speaker", help="输出音色文件目录路径")
    parser.add_argument("--model_path", type=str, default="./", help="模型路径")
    parser.add_argument("--only_generate_list", action="store_true", help="仅生成角色列表，不进行克隆")
    args = parser.parse_args()
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    
    tts_model = None
    if not args.only_generate_list:
        print(f"正在加载模型: {args.model_path}")
        # 使用Qwen3TTSModel加载本地模型
        tts_model = Qwen3TTSModel.from_pretrained(
            args.model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        
        # 检查模型类型
        if tts_model.model.tts_model_type != "base":
            print(f"\n警告：当前使用的模型类型是 {tts_model.model.tts_model_type}，不是 base 类型")
            print("只有 base 类型的模型支持提取 speaker embedding")
            print("CustomVoice 模型使用内置音色，通过 speaker 参数指定")
            print("\n支持的内置音色：")
            for speaker in get_built_in_voices(tts_model):
                print(f"  - {speaker}")
    
    # 仅生成角色列表
    if args.only_generate_list:
        print(f"\n正在生成角色列表...")
        generate_voice_list(args.output_dir, tts_model)
        return
    
    # 检查模型类型
    if tts_model.model.tts_model_type != "base":
        print(f"\n当前模型不支持speaker embedding提取，仅生成角色列表")
        generate_voice_list(args.output_dir, tts_model)
        return
    
    # 处理单个文件模式
    if args.ref_audio:
        if not args.output_path:
            # 如果没有指定输出路径，使用原文件名+.pt
            base_name = os.path.splitext(os.path.basename(args.ref_audio))[0]
            args.output_path = os.path.join(args.output_dir, f"{base_name}.pt")
        
        if not os.path.exists(args.ref_audio):
            raise FileNotFoundError(f"参考音频文件不存在: {args.ref_audio}")
        
        print(f"\n正在处理单个音频文件: {args.ref_audio}")
        # 使用base模型的extract_speaker_embedding方法提取speaker embedding
        process_single_audio(tts_model, args.ref_audio, args.output_path)
    
    # 处理目录模式
    else:
        print(f"\n正在扫描目录: {args.input_dir}")
        # 支持mp3和wav格式
        audio_files = glob.glob(os.path.join(args.input_dir, "*.wav")) + glob.glob(os.path.join(args.input_dir, "*.mp3"))
        
        if not audio_files:
            print(f"警告：在目录 {args.input_dir} 中未找到任何wav或mp3音频文件")
        else:
            print(f"找到 {len(audio_files)} 个音频文件：")
            for i, file in enumerate(audio_files):
                print(f"{i+1}. {os.path.basename(file)}")
            
            # 处理每个音频文件
            for audio_file in audio_files:
                # 使用原文件名+.pt作为输出文件名
                base_name = os.path.splitext(os.path.basename(audio_file))[0]
                output_path = os.path.join(args.output_dir, f"{base_name}.pt")
                
                process_single_audio(tts_model, audio_file, output_path)
    
    # 生成角色列表
    generate_voice_list(args.output_dir, tts_model)
    
    print(f"\n操作完成！")
    print(f"\n提示：")
    print(f"1. 对于 CustomVoice 模型，使用内置音色：")
    print(f"   python3 use_cloned_voice.py --speaker_emb uncle_fu --text '要生成的文本' --output output.wav")
    print(f"2. 对于生成的角色，需要使用 base 模型来提取 speaker embedding")
    print(f"3. 角色列表已保存到 voice_list.txt 文件")


if __name__ == "__main__":
    main()
