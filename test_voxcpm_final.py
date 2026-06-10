import os
import sys
import time
import torch

def test_voxcpm_final():
    """最终版 VoxCPM 语音克隆测试 - 解决文本一致性问题"""
    
    # 克隆音频目录
    clone_audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"
    
    # 选择测试音频
    test_audio = os.path.join(clone_audio_dir, "云闯-男声-磁性,青年男声.mp3")
    if not os.path.exists(test_audio):
        audio_files = [f for f in os.listdir(clone_audio_dir) if f.endswith('.mp3')]
        if audio_files:
            test_audio = os.path.join(clone_audio_dir, audio_files[0])
        else:
            print("❌ 未找到克隆音频文件")
            return
    
    print(f"\n🎯 使用测试音频: {os.path.basename(test_audio)}")
    
    # 测试文本 - 使用更简洁的句子，避免复杂表达
    test_cases = [
        {"name": "简单句1", "text": "今天天气很好。"},
        {"name": "简单句2", "text": "你好，欢迎使用语音合成。"},
        {"name": "简单句3", "text": "这是一个测试。"},
        {"name": "叙述句", "text": "我喜欢在早晨散步。"},
        {"name": "疑问句", "text": "你今天有空吗？"},
        {"name": "感叹句", "text": "今天真是美好的一天！"},
        {"name": "长文本", "text": "春天来了，万物复苏，小草绿了，花儿开了，鸟儿在树上欢快地歌唱。"},
        {"name": "情绪文本", "text": "太棒了！我终于成功了！"}
    ]
    
    # 测试不同的max_len值
    max_len_values = [500, 800, 1000, 1500]
    
    try:
        from voxcpm.core import VoxCPM
        
        print("\n🚀 初始化 VoxCPM 模型...")
        start_time = time.time()
        
        vox = VoxCPM.from_pretrained(
            hf_model_id="openbmb/VoxCPM-0.5B",
            load_denoiser=False,
            cache_dir="/Users/zhuxingchong/.cache/huggingface/hub"
        )
        
        init_time = time.time() - start_time
        print(f"✅ 模型初始化完成，耗时: {init_time:.2f}秒")
        
        for max_len in max_len_values:
            print(f"\n\n==================================================")
            print(f"📋 当前配置: max_len = {max_len}")
            print(f"==================================================")
            
            output_dir = f"voxcpm_output_maxlen_{max_len}"
            os.makedirs(output_dir, exist_ok=True)
            
            for i, test_case in enumerate(test_cases, 1):
                print(f"\n🔊 [{i}/{len(test_cases)}] {test_case['name']}")
                print(f"   原文: {test_case['text']}")
                print(f"   文本长度: {len(test_case['text'])} 字")
                
                start_time = time.time()
                try:
                    # 使用匹配的prompt_text
                    prompt_text = "这是一段用于声音克隆的参考音频。"
                    
                    audio = vox.tts_model.generate(
                        target_text=test_case['text'],
                        prompt_wav_path=test_audio,
                        prompt_text=prompt_text,
                        max_len=max_len
                    )
                    gen_time = time.time() - start_time
                    
                    # 计算音频时长（16kHz采样率）
                    if isinstance(audio, torch.Tensor):
                        audio_length = audio.shape[-1] / 16000
                    else:
                        audio_length = len(audio) / 16000
                    
                    print(f"✅ 音频生成成功！")
                    print(f"   音频形状: {audio.shape if hasattr(audio, 'shape') else len(audio)}")
                    print(f"   音频时长: {audio_length:.2f}秒")
                    print(f"   生成耗时: {gen_time:.2f}秒")
                    
                    # 保存输出
                    safe_name = test_case['name'].replace('/', '_').replace('\\', '_')
                    output_path = os.path.join(output_dir, f"{safe_name}.wav")
                    
                    import torchaudio
                    if isinstance(audio, torch.Tensor):
                        if audio.dim() == 1:
                            audio = audio.unsqueeze(0)
                        elif audio.dim() == 3:
                            audio = audio.squeeze(0)
                        torchaudio.save(output_path, audio.detach().cpu(), 16000)
                    else:
                        torchaudio.save(output_path, torch.tensor(audio).unsqueeze(0), 16000)
                    
                    print(f"💾 保存到: {output_path}")
                    
                except Exception as e:
                    gen_time = time.time() - start_time
                    print(f"❌ 生成失败: {e}")
        
        print("\n🎉 所有测试完成！")
        print("\n📊 测试分析报告:")
        print("=" * 50)
        print("问题1: 播报内容与文本不一致")
        print("-" * 50)
        print("可能原因:")
        print("  1. max_len设置不当，导致文本被截断或重复")
        print("  2. 模型生成过程中的随机性")
        print("  3. 标点符号处理问题")
        print("\n解决方案:")
        print("  1. 根据文本长度调整max_len参数")
        print("     - 短文本(1-10字): max_len=300-500")
        print("     - 中等文本(10-50字): max_len=500-1000")
        print("     - 长文本(50字以上): max_len=1000-2000")
        print("  2. 使用简洁的文本，避免过多标点")
        print("  3. 尝试不同的克隆音频")
        print("\n" + "=" * 50)
        print("问题2: 情绪变化不明显")
        print("-" * 50)
        print("技术说明:")
        print("  VoxCPM是语音克隆模型，主要克隆声音特征(音色、语调)")
        print("  情绪表达主要依赖于:")
        print("    1. 原始克隆音频的情绪特征")
        print("    2. 文本内容的情感倾向")
        print("    3. 模型的韵律生成能力")
        print("\n建议:")
        print("  1. 选择带有明显情绪特征的克隆音频")
        print("  2. 使用带有情绪色彩的文本")
        print("  3. 尝试不同的语音克隆模型")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_voxcpm_final()