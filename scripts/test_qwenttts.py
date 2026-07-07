#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import threading
import concurrent.futures
from queue import Queue

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'novel_tool', 'scripts'))

from audio_processing_module import AudioEngine, VoiceParams

OUTPUT_DIR = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/temp_audio"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_audio(audio, filename):
    """保存音频到指定目录"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    audio.export(filepath, format="wav")
    print(f"💾 音频已保存: {filepath}")
    return filepath

def generate_voice_thread(engine, params, result_queue, thread_id):
    try:
        print(f"线程 {thread_id} 开始生成语音...")
        start_time = time.time()
        audio = engine.text_to_speech(params)
        elapsed_time = time.time() - start_time
        
        filename = f"test_thread_{thread_id}.wav"
        save_audio(audio, filename)
        
        result_queue.put((thread_id, True, audio, elapsed_time))
        print(f"线程 {thread_id} 完成，耗时: {elapsed_time:.2f} 秒")
    except Exception as e:
        result_queue.put((thread_id, False, str(e), 0))
        print(f"线程 {thread_id} 失败: {e}")

def test_single_engine_multithread():
    print("\n=== 测试1: 单个引擎实例多线程调用 ===")
    
    audio_engine = AudioEngine()
    
    test_texts = [
        "亲爱的听众朋友们，大家好！我是您的AI声音主播。很高兴与您相遇。我具备多风格音色转换能力，无论是温润儒雅的学者风范，还是沉稳大气的旁白演绎，都能为您专业呈现。希望通过我的声音，为您开启美妙的听觉之旅。",
    ]
    
    params_list = []
    for i, text in enumerate(test_texts):
        params = VoiceParams(
            text=text,
            role="旁白",
            role_voice="温润学者-磁性,浑厚",
            speed="+0%",
            volume="+0%",
            pitch="+0Hz"
        )
        params_list.append(params)
    
    result_queue = Queue()
    threads = []
    
    start_time = time.time()
    
    for i, params in enumerate(params_list):
        thread = threading.Thread(
            target=generate_voice_thread,
            args=(audio_engine, params, result_queue, i)
        )
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    
    success_count = 0
    failure_count = 0
    while not result_queue.empty():
        thread_id, success, data, elapsed = result_queue.get()
        if success:
            success_count += 1
        else:
            failure_count += 1
    
    print(f"\n=== 测试1 结果 ===")
    print(f"总耗时: {total_time:.2f} 秒")
    print(f"成功: {success_count} 个")
    print(f"失败: {failure_count} 个")
    print(f"输出目录: {OUTPUT_DIR}")
    
    return success_count == len(test_texts)

def generate_voice_with_new_engine(params, thread_id):
    try:
        print(f"线程 {thread_id} 创建新引擎实例...")
        engine = AudioEngine()
        print(f"线程 {thread_id} 开始生成语音...")
        start_time = time.time()
        audio = engine.text_to_speech(params)
        elapsed_time = time.time() - start_time
        
        filename = f"test_multi_engine_{thread_id}.wav"
        save_audio(audio, filename)
        
        return (thread_id, True, audio, elapsed_time)
    except Exception as e:
        return (thread_id, False, str(e), 0)

def test_multiple_engine_instances():
    print("\n=== 测试2: 每个线程使用独立引擎实例 ===")
    
    test_texts = [
        "清晨的阳光透过窗户洒进房间，照亮了书桌上的笔墨纸砚。",
        "少年手持长剑，在院子里练习着祖传的剑法，身姿矫健。",
        "窗外的桃花开得正艳，微风拂过，花瓣轻轻飘落。",
        "老者坐在藤椅上，品着香茗，看着远处的青山，若有所思。",
    ]
    
    params_list = []
    for i, text in enumerate(test_texts):
        params = VoiceParams(
            text=text,
            role="旁白",
            role_voice="知浩-男青年",
            speed="+0%",
            volume="+0%",
            pitch="+0Hz"
        )
        params_list.append(params)
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for i, params in enumerate(params_list):
            future = executor.submit(generate_voice_with_new_engine, params, i)
            futures.append(future)
        
        success_count = 0
        failure_count = 0
        for future in concurrent.futures.as_completed(futures):
            thread_id, success, data, elapsed = future.result()
            if success:
                success_count += 1
                print(f"线程 {thread_id} 完成，耗时: {elapsed:.2f} 秒")
            else:
                failure_count += 1
                print(f"线程 {thread_id} 失败: {data}")
    
    total_time = time.time() - start_time
    
    print(f"\n=== 测试2 结果 ===")
    print(f"总耗时: {total_time:.2f} 秒")
    print(f"成功: {success_count} 个")
    print(f"失败: {failure_count} 个")
    print(f"输出目录: {OUTPUT_DIR}")
    
    return success_count == len(test_texts)

def test_sequential():
    print("\n=== 测试3: 串行处理（基准对比） ===")
    
    audio_engine = AudioEngine()
    
    test_texts = [
        "夜幕降临，小镇渐渐安静下来，只有偶尔传来的犬吠声。",
        "月光如水，洒在青石板路上，泛起淡淡的银光。",
        "陈平安坐在门槛上，望着星空，思绪飘向远方。",
        "明天又是新的一天，充满了未知和希望。",
    ]
    
    start_time = time.time()
    success_count = 0
    
    for i, text in enumerate(test_texts):
        params = VoiceParams(
            text=text,
            role="旁白",
            role_voice="知浩-男青年",
            speed="+0%",
            volume="+0%",
            pitch="+0Hz"
        )
        try:
            print(f"处理第 {i+1} 段文本...")
            audio = audio_engine.text_to_speech(params)
            filename = f"test_sequential_{i}.wav"
            save_audio(audio, filename)
            success_count += 1
        except Exception as e:
            print(f"第 {i+1} 段失败: {e}")
    
    total_time = time.time() - start_time
    
    print(f"\n=== 测试3 结果 ===")
    print(f"总耗时: {total_time:.2f} 秒")
    print(f"成功: {success_count} 个")
    print(f"输出目录: {OUTPUT_DIR}")
    
    return success_count == len(test_texts)

if __name__ == "__main__":
    print("=" * 60)
    print("Qwen3-TTS 多线程合成测试")
    print("=" * 60)
    print(f"输出目录: {OUTPUT_DIR}")
    
    test_single_engine_multithread()
    
    #test_multiple_engine_instances()
    #test_sequential()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)