import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel
import argparse
import os


def main():
    parser = argparse.ArgumentParser(description="测试Qwen3-TTS base模型的语音克隆功能")
    parser.add_argument("--ref_audio", type=str, default="clone-audio/云健-中年男性磁性声音.mp3", help="参考音频文件路径")
    parser.add_argument("--ref_text", type=str, default="", help="参考音频对应的文本")
    parser.add_argument("--target_text", type=str, default="大家好，我是克隆出来的专属配音，这是一个测试。", help="要生成的文本")
    parser.add_argument("--output_path", type=str, default="cloned_voice.wav", help="输出音频文件路径")
    parser.add_argument("--model_path", type=str, default="./", help="模型路径")
    args = parser.parse_args()
    
    print(f"正在加载模型: {args.model_path}")
    
    # 加载base模型
    model = Qwen3TTSModel.from_pretrained(
        args.model_path,
        device_map="auto",
        dtype=torch.bfloat16,
    )
    
    # 检查模型类型
    model_type = getattr(model.model, 'tts_model_type', 'unknown')
    print(f"模型类型: {model_type}")
    
    if model_type != "base":
        print("错误：当前模型不是base类型，不支持语音克隆")
        return
    
    # 检查参考音频是否存在
    if not os.path.exists(args.ref_audio):
        print(f"错误：参考音频文件不存在: {args.ref_audio}")
        return
    
    print(f"\n使用参考音频: {args.ref_audio}")
    print(f"参考文本: {args.ref_text}")
    print(f"目标文本: {args.target_text}")
    
    # 生成克隆语音
    print("\n正在生成克隆语音...")
    wavs, sr = model.generate_voice_clone(
        text=args.target_text,
        language="Chinese",
        ref_audio=args.ref_audio,
        ref_text=args.ref_text,
        x_vector_only_mode=True,  # 仅使用说话人嵌入
        temperature=0.7,  # 控制生成的随机性，值越大越随机，值越小越确定
    )
    
    # 保存生成的音频
    print(f"\n生成成功！音频时长: {len(wavs[0])/sr:.2f}秒")
    sf.write(args.output_path, wavs[0], sr)
    print(f"音频已保存到: {args.output_path}")
    
    print("\n语音克隆测试完成！")


if __name__ == "__main__":
    main()
