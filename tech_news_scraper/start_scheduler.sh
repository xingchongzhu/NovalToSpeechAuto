#!/bin/bash

cd /Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/tech_news_scraper
nohup python3 scheduler.py > /dev/null 2>&1 &

echo "定时任务服务已启动"
echo "日志文件: scheduler.log"