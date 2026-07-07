#!/usr/bin/env python3
import requests
import re
import os
import time
import random

# 章节URL列表（从目录页提取）
chapter_urls = [
    ("第一回 月夜棹孤舟 巫峡啼猿登栈道 天涯逢知己 移家结伴隐名山", "https://www.yueguji.com/book/735/6b5c08427e945.html"),
    ("第二回 舞长剑 师徒逞身手 上峨眉 烟雨锁空濛", "https://www.yueguji.com/book/735/17675069d7b94.html"),
    ("第三回 云中鹤深山话前因 多臂熊截江逢侠士", "https://www.yueguji.com/book/735/45ee26e3d06da.html"),
    ("第四回 见首神龙 醉道人挥金纵饮 离巢孤雏 赵燕儿别母从师", "https://www.yueguji.com/book/735/876ed396e4149.html"),
    ("第五回 鹤舞空山 侠客惊蛇怪 云迷蜀岭 孝子拜仙师", "https://www.yueguji.com/book/735/b1565e7370ec6.html"),
    ("第六回 名山借灵物 仙侠夜话 古洞斩妖蛇 父女重逢", "https://www.yueguji.com/book/735/a97c8a5c78e8d.html"),
    ("第七回 擒淫贼 大闹施家巷 逢狭路 智敌八指僧", "https://www.yueguji.com/book/735/d4fe6938d7240.html"),
    ("第八回 林中比剑 云中鹤绝处逢生 寺内谈心 小火神西行求救", "https://www.yueguji.com/book/735/ef88f5193c01f.html"),
    ("第九回 古庙逢凶 众孝廉禅堂遭毒手 石牢逃命 憨公子夜雨越东墙", "https://www.yueguji.com/book/735/ccb99c755bb4e.html"),
    ("第十回 风雨同舟 穷途怜弱女 仙缘遇合 佛法伏凶僧", "https://www.yueguji.com/book/735/151e6b4d1c951.html"),
]

output_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/novel_tool/novel_scripts_raw/蜀山剑侠传"

def download_chapter(title, url, chapter_num):
    """下载单个章节"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.yueguji.com/novel/729.html',
        }
        
        # 随机延迟，模拟人类访问
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        
        # 提取内容（在标题和上一章之间）
        text = response.text
        
        # 找到标题位置
        title_start = text.find(f'### {title}')
        if title_start == -1:
            title_start = text.find('<h1')
            if title_start != -1:
                title_end = text.find('</h1>', title_start)
                title = text[title_start:title_end].replace('<h1>', '').replace('</h1>', '').strip()
        
        # 找到上一章位置
        prev_link_start = text.find('[上一章]')
        
        # 提取内容
        if title_start != -1 and prev_link_start != -1:
            content = text[title_start:prev_link_start]
            # 清理HTML标签
            content = re.sub(r'<[^>]+>', '\n', content)
            content = re.sub(r'\s+', '\n', content)
            content = content.strip()
        else:
            # 备选方案：提取body内容
            body_start = text.find('<body')
            body_end = text.find('</body>')
            if body_start != -1 and body_end != -1:
                content = text[body_start:body_end]
                content = re.sub(r'<[^>]+>', '\n', content)
                content = re.sub(r'\s+', '\n', content)
                content = content.strip()
            else:
                print(f"✗ 第{chapter_num}回: 内容提取失败")
                return False
        
        # 生成文件名
        title_short = title[:10] if len(title) > 10 else title
        filename = f"蜀山剑侠传第{chapter_num}回-{title_short}.txt"
        filepath = os.path.join(output_dir, filename)
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(title + '\n\n')
            f.write(content)
        
        print(f"✓ 第{chapter_num}回: {title}")
        return True
        
    except Exception as e:
        print(f"✗ 第{chapter_num}回: {str(e)}")
        return False

if __name__ == "__main__":
    os.makedirs(output_dir, exist_ok=True)
    
    success_count = 0
    fail_count = 0
    
    for i, (title, url) in enumerate(chapter_urls, 1):
        # 检查是否已存在
        title_short = title[:10] if len(title) > 10 else title
        filename = f"蜀山剑侠传第{i}回-{title_short}.txt"
        filepath = os.path.join(output_dir, filename)
        
        if os.path.exists(filepath):
            print(f"✓ 第{i}回: {title} (已存在，跳过)")
            success_count += 1
            continue
        
        print(f"\n正在下载第{i}回: {title}")
        if download_chapter(title, url, i):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\n\n下载完成！成功: {success_count}, 失败: {fail_count}")
    print(f"文件保存到: {output_dir}")