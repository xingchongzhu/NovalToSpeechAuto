#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻定时抓取服务
每天8:30和18:00自动抓取新闻并生成音频
支持实时进度显示
"""

import os
import sys
import time
import glob
import logging
from datetime import datetime
from threading import Thread

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

TARGET_TIMES = [
    (8, 30),    # 早上8:30
    (19, 30)    # 晚上19:30
]

def print_progress(message):
    """打印进度信息"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\r[{timestamp}] {message}", end='', flush=True)

def run_news_scraper():
    """执行新闻抓取和音频生成"""
    try:
        logger.info("开始执行新闻抓取任务...")
        print_progress("开始执行新闻抓取任务...")
        
        today_date_str = datetime.now().strftime('%Y-%m-%d')
        news_dir = os.path.join('news', today_date_str)
        
        # 检查今天是否已有新闻数据
        existing_json = []
        if os.path.isdir(news_dir):
            existing_json = glob.glob(os.path.join(news_dir, 'tech_news_*.json'))
        
        if existing_json:
            # 当天新闻已抓取，直接使用已有 JSON 合成音频
            existing_json.sort(reverse=True)
            output_path = existing_json[0]
            print_progress(f"当天新闻已存在，跳过抓取: {output_path}")
            logger.info(f"当天新闻已存在，跳过抓取，使用: {output_path}")
        else:
            from scraper import TechNewsScraper
            
            print_progress("初始化爬虫...")
            scraper = TechNewsScraper()
            
            print_progress("正在抓取新闻...")
            news = scraper.scrape_all(fetch_detail=True, limit=10)
            
            if not news:
                logger.warning("未获取到任何新闻")
                print_progress("未获取到任何新闻")
                print()
                return
            
            print_progress("新闻抓取完成，正在保存...")
            scraper.print_news(count=10, show_summary=True)
            output_path = scraper.save_to_file()
        
        if output_path:
            print_progress("正在生成音频...")
            from news_to_audio import news_to_audio
            news_to_audio(
                news_json_path=output_path,
                output_dir='news',
                voice_name="阿辉-官方新闻,资讯"
            )
        
        logger.info("新闻抓取任务完成")
        print_progress("任务完成！")
        print()
        
    except Exception as e:
        logger.error(f"新闻抓取任务失败: {e}", exc_info=True)
        print_progress(f"任务失败: {e}")
        print()

def get_seconds_until_next_target():
    """计算距离下一个目标时间还有多少秒"""
    now = datetime.now()
    today = now.date()
    
    next_target = None
    min_seconds = float('inf')
    
    for hour, minute in TARGET_TIMES:
        target = datetime(today.year, today.month, today.day, hour, minute)
        
        if now < target:
            seconds = (target - now).total_seconds()
            if seconds < min_seconds:
                min_seconds = seconds
                next_target = target
        else:
            tomorrow = today.replace(day=today.day + 1)
            target = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute)
            seconds = (target - now).total_seconds()
            if seconds < min_seconds:
                min_seconds = seconds
                next_target = target
    
    return min_seconds, next_target

def update_progress_display(next_target):
    """实时更新进度显示"""
    while True:
        now = datetime.now()
        delta = next_target - now
        
        if delta.total_seconds() <= 0:
            break
        
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        seconds = int(delta.total_seconds() % 60)
        
        status = f"等待下次执行 [{next_target.strftime('%H:%M')}] - 剩余 {hours:02d}:{minutes:02d}:{seconds:02d}"
        print_progress(status)
        
        time.sleep(1)

def scheduler_loop():
    """定时任务循环"""
    logger.info("定时任务服务已启动")
    logger.info(f"执行时间: {', '.join([f'{h}:{m:02d}' for h, m in TARGET_TIMES])}")
    print(f"定时任务服务已启动")
    print(f"执行时间: {', '.join([f'{h}:{m:02d}' for h, m in TARGET_TIMES])}")
    
    # 启动时先立即执行一次抓取
    print("启动时立即执行一次新闻抓取任务...")
    run_news_scraper()
    
    while True:
        seconds, next_target = get_seconds_until_next_target()
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        logger.info(f"距离下次执行 ({next_target.strftime('%H:%M')}) 还有 {hours} 小时 {minutes} 分钟 {secs} 秒")
        
        progress_thread = Thread(target=update_progress_display, args=(next_target,))
        progress_thread.daemon = True
        progress_thread.start()
        
        time.sleep(seconds)
        
        print_progress("⏰ 到达预定时间，开始执行任务")
        run_news_scraper()
        
        time.sleep(60)

def main():
    """主函数"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    scheduler_loop()

if __name__ == "__main__":
    main()