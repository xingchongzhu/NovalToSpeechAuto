#!/usr/bin/env python3
import requests
import re
import os
import time
import random
from bs4 import BeautifulSoup

output_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/蜀山剑侠传"

sources = [
    "https://www.shushanxia.com/10154/{}.html",
    "https://www.sjxsw.org/book/10154/{}.html",
    "https://www.xbiquge.la/10/10154/{}.html",
    "https://www.biquge66.net/10154/{}.html",
    "https://www.xxbiquge.com/10_10154/{}.html",
]

chapter_titles = {
    1: "月夜棹孤舟 巫峡啼猿登栈道 天涯逢知己 移家结伴隐名山",
    2: "舞长剑 师徒逞身手 上峨眉 烟雨锁空濛",
    3: "云中鹤深山话前因 多臂熊截江逢侠士",
    4: "见首神龙 醉道人挥金纵饮 离巢孤雏 赵燕儿别母从师",
    5: "鹤舞空山 侠客惊蛇怪 云迷蜀岭 孝子拜仙师",
    6: "名山借灵物 仙侠夜话 古洞斩妖蛇 父女重逢",
    7: "擒淫贼 大闹施家巷 逢狭路 智敌八指僧",
    8: "林中比剑 云中鹤绝处逢生 寺内谈心 小火神西行求救",
    9: "古庙逢凶 众孝廉禅堂遭毒手 石牢逃命 憨公子夜雨越东墙",
    10: "拯孤穷淑女垂青 订良缘醉仙作伐",
    11: "潜心避祸小住碧筠庵 一念真诚情感追云叟",
    12: "白日宣淫真人现形 黑夜炼魔侠女纵火",
    13: "周轻云学道辟邪村 笑和尚大闹慈云寺",
    14: "九华山白侠逢凶 湘江岸红娃盗宝",
    15: "齐漱溟访道遇妖童 吕灵姑下山逢鬼女",
    16: "散家财严父训子 试仙缘孝子寻师",
    17: "闲寻幽壑采灵兰 偶遇仙娥得宝刃",
    18: "惊怪异深宵闻鬼泣 报亲仇千里走风尘",
    19: "独抱热肠穷途怜弱女 广施佛法苦海渡群迷",
    20: "金蝉初会碧莲姊 一笑相逢恍旧识",
    21: "金罗汉访友紫金泷 许飞娘传书五云步",
    22: "晤薛蟒女侠收徒 试屠龙神僧绝艺",
    23: "见不平拔刀相助 闻怪异入洞逢凶",
    24: "诛妖邪大闹紫云宫 救生灵巧得青索剑",
    25: "轻身剑初试锋芒 斩莽妖又逢劲敌",
    26: "巧计安排深宵拒敌 仙缘遇合宝剑通灵",
    27: "飞剑惊芒诛蛇怪 灵符遁水斩妖鼋",
    28: "得青霓剑斩独龙 收神砂珠除巨寇",
    29: "金鞭崖陶钧学剑 水帘洞石生拜师",
    30: "烛影忽摇红喜得宝珠归匣 剑光惊掣电惊看飞剑穿云",
    31: "力诛四寇",
    32: "弥天星雨",
    33: "秘箩误",
    34: "小灵猴僧舍宣淫",
    35: "密室困昆仑",
    36: "诛淫孽",
    37: "访能人",
}

def download_chapter(chapter_num):
    title = chapter_titles.get(chapter_num, f"第{chapter_num}回")
    
    for source in sources:
        try:
            url = source.format(chapter_num)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.baidu.com/',
            }
            
            time.sleep(random.uniform(0.5, 1.5))
            
            response = requests.get(url, headers=headers, timeout=30)
            response.encoding = response.apparent_encoding if response.encoding == 'ISO-8859-1' else 'utf-8'
            
            if response.status_code != 200:
                continue
            
            text = response.text
            
            if "404" in text or "页面不存在" in text or "not found" in text.lower():
                continue
            
            try:
                soup = BeautifulSoup(text, 'html.parser')
                title_tag = soup.find('h1')
                actual_title = title_tag.get_text(strip=True) if title_tag else f"第{chapter_num}回 {title}"
                
                content_tags = soup.find_all(['div', 'article'], id=lambda x: x and 'content' in x.lower())
                if not content_tags:
                    content_tags = soup.find_all(['div', 'article'], class_=lambda x: x and 'content' in x.lower())
                if not content_tags:
                    content_tags = soup.find_all('div', id='txtContent')
                if not content_tags:
                    content_tags = soup.find_all('div', class_='txtContent')
                
                if content_tags:
                    content = content_tags[0].get_text(strip=False)
                else:
                    continue
                
                content = re.sub(r'\s+', '\n', content)
                content = content.strip()
                
            except:
                title_start = text.find('<h1>')
                if title_start != -1:
                    title_end = text.find('</h1>', title_start)
                    actual_title = text[title_start:title_end].replace('<h1>', '').replace('</h1>', '').strip()
                else:
                    actual_title = f"第{chapter_num}回 {title}"
                
                patterns = [
                    r'<div id="content">(.*?)</div>',
                    r'<div class="content">(.*?)</div>',
                    r'<div id="txtContent">(.*?)</div>',
                    r'<div class="txtContent">(.*?)</div>',
                    r'<article[^>]*>(.*?)</article>',
                ]
                
                content = None
                for pattern in patterns:
                    match = re.search(pattern, text, re.DOTALL)
                    if match:
                        content = match.group(1)
                        break
                
                if content is None:
                    prev_link_start = text.find('[上一章]')
                    next_link_start = text.find('[下一章]')
                    if prev_link_start != -1 and next_link_start != -1:
                        content = text[prev_link_start:next_link_start]
                
                if content is None:
                    continue
                
                content = re.sub(r'<[^>]+>', '\n', content)
                content = re.sub(r'\s+', '\n', content)
                content = content.strip()
            
            if len(content) < 500:
                continue
            
            title_short = title[:10] if len(title) > 10 else title
            filename = f"蜀山剑侠传第{chapter_num}回-{title_short}.txt"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(actual_title + '\n\n')
                f.write(content)
            
            print(f"✓ 第{chapter_num}回: {title}")
            return True
            
        except Exception as e:
            continue
    
    print(f"✗ 第{chapter_num}回: 所有源均无法获取")
    return False

if __name__ == "__main__":
    os.makedirs(output_dir, exist_ok=True)
    
    total_chapters = 329
    start_chapter = 38
    
    existing_chapters = []
    for f in os.listdir(output_dir):
        if f.startswith("蜀山剑侠传第") and f.endswith(".txt"):
            try:
                num = int(re.search(r'第(\d+)回', f).group(1))
                existing_chapters.append(num)
            except:
                pass
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    print(f"已存在章节: {sorted(existing_chapters)}")
    print(f"开始下载第{start_chapter}-{total_chapters}回...")
    
    for chapter_num in range(start_chapter, total_chapters + 1):
        if chapter_num in existing_chapters:
            title = chapter_titles.get(chapter_num, f"第{chapter_num}回")
            print(f"✓ 第{chapter_num}回: {title} (已存在，跳过)")
            skip_count += 1
            success_count += 1
            continue
        
        title = chapter_titles.get(chapter_num, f"第{chapter_num}回")
        print(f"\n正在下载第{chapter_num}回: {title}")
        if download_chapter(chapter_num):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\n\n下载完成！")
    print(f"已存在跳过: {skip_count}")
    print(f"成功下载: {success_count - skip_count}")
    print(f"下载失败: {fail_count}")
    print(f"文件保存到: {output_dir}")