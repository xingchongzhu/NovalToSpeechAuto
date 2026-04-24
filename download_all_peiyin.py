import os
import requests
import json

audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"
os.makedirs(audio_dir, exist_ok=True)

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.pdd5.com/lbpeiyin.html'
})

all_characters = []
page = 1
total_pages = 59

while page <= total_pages:
    url = f"https://www.pdd5.com/api/peiyin/roleList?page={page}&pagesize=16&search=&type=&area=&cate=&timbre=&language="
    try:
        response = session.get(url, timeout=10)
        data = response.json()
        
        if 'data' in data and 'data' in data['data']:
            for item in data['data']['data']:
                char_id = str(item.get('id', ''))
                name = item.get('nickname', '')
                tags = item.get('tags', [])
                timbre = item.get('timbre', '')
                language = item.get('language', '')
                mood_list = item.get('mood_list', [])
                
                style = ""
                if timbre == 'man':
                    style = "男声"
                elif timbre == 'woman':
                    style = "女声"
                elif timbre == 'child':
                    style = "童声"
                elif timbre == 'old':
                    style = "老人"
                else:
                    style = "特色"
                
                if tags:
                    style += "-" + ",".join(tags[:2])
                
                all_characters.append({
                    'id': char_id,
                    'name': name,
                    'style': style,
                    'tags': tags,
                    'language': language,
                    'mood_list': mood_list
                })
            
            total_pages = data['data'].get('last_page', 59)
            print(f"获取第 {page}/{total_pages} 页，累计 {len(all_characters)} 个角色")
            page += 1
        else:
            break
    except Exception as e:
        print(f"获取第 {page} 页失败: {e}")
        page += 1
        continue

print(f"\n共获取到 {len(all_characters)} 个角色")

success_count = 0
downloaded_chars = []

for char in all_characters:
    if char['mood_list']:
        first_mood = char['mood_list'][0]
        audio_url = first_mood.get('mood_audio', '')
    else:
        audio_url = f"https://pdd5.oss-cn-shanghai.aliyuncs.com/static/tts/audio/{char['id']}_default.mp3"
    
    if audio_url:
        try:
            response = session.get(audio_url, timeout=10)
            if response.status_code == 200:
                filename = f"{char['name']}-{char['style']}.mp3"
                filepath = os.path.join(audio_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"下载成功: {filename}")
                success_count += 1
                downloaded_chars.append(char)
            else:
                print(f"下载失败({response.status_code}): {char['name']}")
        except Exception as e:
            print(f"下载失败: {char['name']} - {e}")

print(f"\n下载完成！成功下载 {success_count}/{len(all_characters)} 个音频文件")

category_groups = {}
for char in downloaded_chars:
    if '男声' in char['style']:
        cat = '男声'
    elif '女声' in char['style']:
        cat = '女声'
    elif '童声' in char['style']:
        cat = '童声'
    elif '老人' in char['style']:
        cat = '老人'
    else:
        cat = '特色角色'
    
    if cat not in category_groups:
        category_groups[cat] = []
    category_groups[cat].append(char)

doc_content = "# 克隆音频角色列表说明\n\n"
doc_content += "## 角色分类总览\n\n"
for category in sorted(category_groups.keys()):
    doc_content += f"- **{category}**: {len(category_groups[category])} 个角色\n"
doc_content += "\n"

for category in sorted(category_groups.keys()):
    doc_content += f"## {category}\n\n"
    for char in category_groups[category]:
        filename = f"{char['name']}-{char['style']}.mp3"
        scenario = ""
        if '影视解说' in char['tags']:
            scenario = '影视解说、纪录片'
        elif '情感语录' in char['tags']:
            scenario = '情感电台、短视频'
        elif '故事' in char['tags']:
            scenario = '有声读物、故事讲述'
        elif '广告' in char['tags']:
            scenario = '广告配音、宣传片'
        elif '美食' in char['tags']:
            scenario = '美食视频、生活内容'
        else:
            scenario = '通用配音场景'
        
        doc_content += f"### {char['name']}\n\n"
        doc_content += f"| 属性 | 内容 |\n"
        doc_content += f"| --- | --- |\n"
        doc_content += f"| 音频文件 | `{filename}` |\n"
        doc_content += f"| 角色特色 | {char['style']} |\n"
        doc_content += f"| 试用场景 | {scenario} |\n"
        doc_content += "\n"

doc_path = os.path.join(audio_dir, "克隆音频角色列表说明.md")
with open(doc_path, 'w', encoding='utf-8') as f:
    f.write(doc_content)

print(f"介绍文档已创建: {doc_path}")