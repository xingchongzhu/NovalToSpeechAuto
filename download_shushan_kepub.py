#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 m.kepub.net 下载《蜀山剑侠传》全部章节"""

import requests
import re
import os
import time
import random
from bs4 import BeautifulSoup

output_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/novel_tool/novel_scripts_raw/蜀山剑侠传"

# URL映射：章节号 -> URL ID
# 第一卷（第1-60回）：10001-10060
# 第二卷（第61-102回）：20001-20042
# 第三卷（第103-137回）：30001-30035
# 第四卷（第138-174回）：40001-40037
# 第五卷（第175-193回）：50001-50019
# 第六卷（第194-213回）：60001-60020
# 第七卷（第214-234回）：70001-70021
# 第八卷（第235-254回）：80001-80020
# 第九卷（第255-281回）：90001-90027
# 第十卷（第282-309回）：100001-100028

def get_url_id(chapter_num):
    """根据章节号获取URL ID"""
    if chapter_num <= 60:
        return 10000 + chapter_num
    elif chapter_num <= 102:
        return 20000 + chapter_num - 60
    elif chapter_num <= 137:
        return 30000 + chapter_num - 102
    elif chapter_num <= 174:
        return 40000 + chapter_num - 137
    elif chapter_num <= 193:
        return 50000 + chapter_num - 174
    elif chapter_num <= 213:
        return 60000 + chapter_num - 193
    elif chapter_num <= 234:
        return 70000 + chapter_num - 213
    elif chapter_num <= 254:
        return 80000 + chapter_num - 234
    elif chapter_num <= 281:
        return 90000 + chapter_num - 254
    elif chapter_num <= 309:
        return 100000 + chapter_num - 281
    else:
        return None

def download_chapter(chapter_num):
    """下载单个章节"""
    url_id = get_url_id(chapter_num)
    if url_id is None:
        print(f"✗ 第{chapter_num}回: URL ID计算失败")
        return False
    
    url = f"https://m.kepub.net/book/1042/{url_id}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://m.kepub.net/book/1042',
        }
        
        # 随机延迟，避免被封
        time.sleep(random.uniform(0.5, 1.5))
        
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"✗ 第{chapter_num}回: HTTP {response.status_code}")
            return False
        
        text = response.text
        
        # 使用BeautifulSoup解析
        soup = BeautifulSoup(text, 'html.parser')
        
        # 获取标题
        title_tag = soup.find('h1')
        if title_tag:
            title = title_tag.get_text(strip=True)
        else:
            title = f"第{chapter_num}回"
        
        # 获取内容 - kepub.net的内容通常在特定的div中
        content_div = soup.find('div', id='content')
        if not content_div:
            content_div = soup.find('div', class_='content')
        if not content_div:
            # 尝试获取所有文本
            content = soup.get_text()
        else:
            content = content_div.get_text(strip=False)
        
        # 清理内容
        content = re.sub(r'\s+', '\n', content)
        content = content.strip()
        
        # 移除广告和无关内容
        content = re.sub(r'关注公众号.*?每天推送阅读内容', '', content)
        content = re.sub(r'可阅日刊', '', content)
        
        # 检查内容长度
        if len(content) < 500:
            print(f"✗ 第{chapter_num}回: 内容过短 ({len(content)}字)")
            return False
        
        # 生成文件名
        title_short = title[:10] if len(title) > 10 else title
        filename = f"蜀山剑侠传第{chapter_num}回-{title_short}.txt"
        filepath = os.path.join(output_dir, filename)
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(title + '\n\n')
            f.write(content)
        
        print(f"✓ 第{chapter_num}回: {title} ({len(content)}字)")
        return True
        
    except Exception as e:
        print(f"✗ 第{chapter_num}回: {str(e)}")
        return False

if __name__ == "__main__":
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查已存在的章节
    existing_chapters = []
    for f in os.listdir(output_dir):
        if f.startswith("蜀山剑侠传第") and f.endswith(".txt"):
            try:
                num = int(re.search(r'第(\d+)回', f).group(1))
                existing_chapters.append(num)
            except:
                pass
    
    print(f"已存在章节: {sorted(existing_chapters)}")
    print(f"总计: {len(existing_chapters)} 章")
    
    # 下载缺失的章节
    total_chapters = 309
    missing_chapters = [i for i in range(1, total_chapters + 1) if i not in existing_chapters]
    
    print(f"\n缺失章节: {len(missing_chapters)} 章")
    print(f"开始下载...")
    
    success_count = 0
    fail_count = 0
    
    for chapter_num in missing_chapters:
        if download_chapter(chapter_num):
            success_count += 1
        else:
            fail_count += 1
        
        # 每10章显示进度
        if (success_count + fail_count) % 10 == 0:
            print(f"\n进度: {success_count + fail_count}/{len(missing_chapters)} (成功: {success_count}, 失败: {fail_count})")
    
    print(f"\n\n下载完成！")
    print(f"成功下载: {success_count}")
    print(f"下载失败: {fail_count}")
    print(f"文件保存到: {output_dir}")