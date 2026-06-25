#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from scraper import TechNewsScraper

def main():
    parser = argparse.ArgumentParser(description='科技AI资讯抓取工具')
    parser.add_argument('-c', '--count', type=int, default=20, help='显示/保存资讯数量')
    parser.add_argument('-d', '--detail', action='store_true', help='是否抓取新闻详情')
    parser.add_argument('-o', '--output', type=str, default=None, help='输出文件名')
    parser.add_argument('-a', '--audio', action='store_true', help='是否生成音频')
    parser.add_argument('-v', '--voice', type=str, default='阿辉-官方新闻,资讯', help='配音角色名称')
    args = parser.parse_args()
    
    scraper = TechNewsScraper()
    news = scraper.scrape_all(fetch_detail=args.detail, limit=args.count)
    
    if news:
        scraper.print_news(count=args.count, show_summary=True)
        if args.output:
            output_path = scraper.save_to_file(args.output)
        else:
            output_path = scraper.save_to_file()
        
        if args.audio and output_path:
            from news_to_audio import news_to_audio
            print("\n🎵 开始生成音频...")
            news_to_audio(
                news_json_path=output_path,
                output_dir='news',
                voice_name=args.voice
            )

if __name__ == "__main__":
    main()