#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import threading
import concurrent.futures
from queue import Queue

# 添加脚本目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '小说批量工具', '脚本'))

from audio_processing_module import AudioEngine, VoiceParams

def generate_voice_thread(engine, params, result_queue, thread_id):
    """线程函数：生成语音"""
    try:
        print(f"线程 {thread_id} 开始生成语音...")
        start_time = time.time()
        audio = engine.text_to_speech(params)
        elapsed_time = time.time() - start_time
        result_queue.put((thread_id, True, audio, elapsed_time))
        print(f"线程 {thread_id} 完成，耗时: {elapsed_time:.2f} 秒")
    except Exception as e:
        result_queue.put((thread_id, False, str(e), 0))
        print(f"线程 {thread_id} 失败: {e}")

def test_single_engine_multithread():
    """测试单个引擎实例多线程调用"""
    print("\n=== 测试1: 单个引擎实例多线程调用 ===")
    
    # 初始化音频引擎
    audio_engine = AudioEngine()
    
    # 测试文本
    test_texts = [
        "四月的春风拂过青石板街，带着江南特有的温润气息。",
        "陈平安背着竹篓行走在小镇上，竹篓里装着刚从铁匠铺打好的铁器。",
        "他脚步沉稳，眼神清澈，嘴角微微上扬，似乎对未来充满了期待。",
        "小镇的清晨总是格外宁静，只有远处传来的几声鸡鸣打破寂静。",
    ]
    
    # 创建语音参数
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
    
    # 使用线程池测试
    result_queue = Queue()
    threads = []
    
    start_time = time.time()
    
    # 创建并启动线程
    for i, params in enumerate(params_list):
        thread = threading.Thread(
            target=generate_voice_thread,
            args=(audio_engine, params, result_queue, i)
        )
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    
    # 统计结果
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
    
    return success_count == len(test_texts)

def generate_voice_with_new_engine(params, thread_id):
    """使用新引擎实例生成语音"""
    try:
        print(f"线程 {thread_id} 创建新引擎实例...")
        # 每个线程创建独立的引擎实例
        engine = AudioEngine()
        print(f"线程 {thread_id} 开始生成语音...")
        start_time = time.time()
        audio = engine.text_to_speech(params)
        elapsed_time = time.time() - start_time
        return (thread_id, True, audio, elapsed_time)
    except Exception as e:
        return (thread_id, False, str(e), 0)

def test_multiple_engine_instances():
    """测试每个线程使用独立引擎实例"""
    print("\n=== 测试2: 每个线程使用独立引擎实例 ===")
    
    # 测试文本
    test_texts = [
        "清晨的阳光透过窗户洒进房间，照亮了书桌上的笔墨纸砚。",
        "少年手持长剑，在院子里练习着祖传的剑法，身姿矫健。",
        "窗外的桃花开得正艳，微风拂过，花瓣轻轻飘落。",
        "老者坐在藤椅上，品着香茗，看着远处的青山，若有所思。",
    ]
    
    # 创建语音参数
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
    
    # 使用线程池，每个任务创建独立引擎
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # 提交任务
        futures = []
        for i, params in enumerate(params_list):
            future = executor.submit(generate_voice_with_new_engine, params, i)
            futures.append(future)
        
        # 收集结果
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
    
    return success_count == len(test_texts)

def test_sequential():
    """测试串行处理作为对比基准"""
    print("\n=== 测试3: 串行处理（基准对比） ===")
    
    # 初始化音频引擎
    audio_engine = AudioEngine()
    
    # 测试文本
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
            success_count += 1
        except Exception as e:
            print(f"第 {i+1} 段失败: {e}")
    
    total_time = time.time() - start_time
    
    print(f"\n=== 测试3 结果 ===")
    print(f"总耗时: {total_time:.2f} 秒")
    print(f"成功: {success_count} 个")
    
    return success_count == len(test_texts)

if __name__ == "__main__":
    print("=" * 60)
    print("Qwen3-TTS 多线程合成测试")
    print("=" * 60)
    
    # 测试1：单个引擎实例多线程（通常会失败，因为模型不是线程安全的）
    test_single_engine_multithread()
    
    # 测试2：每个线程独立引擎实例（应该可以工作，但初始化开销大）
    test_multiple_engine_instances()
    
    # 测试3：串行处理（基准对比）
    test_sequential()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)