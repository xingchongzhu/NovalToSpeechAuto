import os
import sys
import time
from voxcpm import VoxCPM

def test_voxcpm_clone():
    """测试 voxcpm 语音克隆功能 - 不同情绪场景"""
    
    # 克隆音频目录
    clone_audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"
    
    # 列出可用的克隆音频
    audio_files = [f for f in os.listdir(clone_audio_dir) if f.endswith('.mp3')]
    if not audio_files:
        print("❌ 未找到克隆音频文件")
        return
    
    print("📁 可用的克隆音频文件:")
    for i, audio_file in enumerate(audio_files[:5], 1):
        print(f"  {i}. {audio_file}")
    if len(audio_files) > 5:
        print(f"  ... 还有 {len(audio_files) - 5} 个文件")
    
    # 选择一个测试音频
    test_audio = os.path.join(clone_audio_dir, "云闯-男声-磁性,青年男声.mp3")
    if not os.path.exists(test_audio):
        test_audio = os.path.join(clone_audio_dir, audio_files[0])
    
    print(f"\n🎯 使用测试音频: {os.path.basename(test_audio)}")
    
    # 克隆音频对应的文本（用于语音克隆）
    prompt_text = "欢迎使用语音克隆功能，这是一段测试文本。"
    
    # 测试不同情绪场景的文本
    emotion_tests = [
        {"name": "正常叙述", "text": "今天天气很好，阳光明媚，适合出门散步。"},
        {"name": "开心喜悦", "text": "太棒了！我终于完成了这个项目！"},
        {"name": "悲伤难过", "text": "他离开了，留下我一个人在这里。"},
        {"name": "愤怒生气", "text": "你怎么能这样做？这太过分了！"},
        {"name": "温柔低语", "text": "宝贝，晚安，做个好梦。"},
        {"name": "惊讶惊喜", "text": "哇！这简直太不可思议了！"},
        {"name": "严肃认真", "text": "这个问题非常重要，我们必须认真对待。"},
        {"name": "幽默轻松", "text": "为什么程序员总是分不清圣诞节和万圣节？因为 Dec 25 等于 Oct 31！"}
    ]
    
    try:
        # 初始化 VoxCPM
        print("\n🚀 初始化 VoxCPM 模型...")
        start_time = time.time()
        
        vox = VoxCPM.from_pretrained(
            hf_model_id="openbmb/VoxCPM-0.5B",
            load_denoiser=True,
            cache_dir="/Users/zhuxingchong/.cache/huggingface/hub"
        )
        
        init_time = time.time() - start_time
        print(f"✅ 模型初始化完成，耗时: {init_time:.2f}秒")
        
        # 进行语音克隆测试 - 不同情绪场景
        for i, test_case in enumerate(emotion_tests, 1):
            print(f"\n🔊 [{i}/{len(emotion_tests)}] {test_case['name']}")
            print(f"   文本: {test_case['text']}")
            
            start_time = time.time()
            audio = vox.generate(
                text=test_case['text'],
                prompt_wav_path=test_audio,
                prompt_text=prompt_text,  # 需要提供克隆音频对应的文本
                cfg_value=2.0,
                inference_timesteps=10,
                max_length=4096
            )
            gen_time = time.time() - start_time
            
            # 保存输出
            output_dir = "voxcpm_output"
            os.makedirs(output_dir, exist_ok=True)
            safe_name = test_case['name'].replace('/', '_').replace('\\', '_')
            output_path = os.path.join(output_dir, f"emotion_{safe_name}.wav")
            
            vox.save_wav(audio, output_path)
            print(f"💾 保存到: {output_path}")
            print(f"⏱️  耗时: {gen_time:.2f}秒")
            print(f"📊 音频长度: {len(audio) / 16000:.2f}秒")
        
        print("\n🎉 所有情绪场景测试完成！")
        print(f"📂 输出目录: {os.path.abspath(output_dir)}")
        print("\n📋 测试总结:")
        print("  - 克隆音频: ", os.path.basename(test_audio))
        print("  - 克隆文本: ", prompt_text)
        print("  - 测试情绪: 正常叙述、开心喜悦、悲伤难过、愤怒生气、温柔低语、惊讶惊喜、严肃认真、幽默轻松")
        print("  - 输出文件: 每个情绪一个 WAV 文件")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_voxcpm_clone()