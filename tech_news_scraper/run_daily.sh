#!/bin/bash

cd /Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/tech_news_scraper

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

python3 main.py -c 20 -a >> /Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/tech_news_scraper/cron.log 2>&1

echo "Daily news task completed at $(date)" >> /Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/tech_news_scraper/cron.log