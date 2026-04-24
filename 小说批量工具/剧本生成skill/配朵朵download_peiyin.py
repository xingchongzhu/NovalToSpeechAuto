import os
import requests

audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"
os.makedirs(audio_dir, exist_ok=True)

characters = [
    {"id": "1140", "name": "晨宝", "category": "童声", "style": "可爱童声", "scenario": "儿童故事、动画配音、亲子内容"},
    {"id": "1142", "name": "笑笑", "category": "女声", "style": "活泼女声", "scenario": "短视频、广告、解说"},
    {"id": "1145", "name": "明叔", "category": "男声", "style": "稳重男声", "scenario": "纪录片、新闻、企业宣传片"},
    {"id": "1147", "name": "凡少", "category": "男声", "style": "阳光少年", "scenario": "青春校园、游戏解说、Vlog"},
    {"id": "197", "name": "麦克", "category": "英语", "style": "英语男声", "scenario": "英语教学、国际宣传片、外语配音"},
    {"id": "188", "name": "云希", "category": "女声", "style": "温柔女声", "scenario": "情感电台、有声小说、睡前故事"},
    {"id": "1056", "name": "毒少", "category": "男声", "style": "冷酷男声", "scenario": "悬疑小说、游戏角色、反派配音"},
    {"id": "660", "name": "巴达", "category": "其他", "style": "异域风情", "scenario": "民族特色内容、文化介绍"},
    {"id": "742", "name": "吹灯", "category": "男声", "style": "神秘沧桑", "scenario": "盗墓题材、历史故事、评书"},
    {"id": "661", "name": "王几", "category": "男声", "style": "儒雅男声", "scenario": "文学朗诵、诗词解读、知识科普"},
    {"id": "179", "name": "晓辰", "category": "女声", "style": "清新女声", "scenario": "美妆教程、生活分享、购物推荐"},
    {"id": "641", "name": "宏少", "category": "男声", "style": "雄厚男声", "scenario": "体育解说、励志演讲、产品发布"},
    {"id": "1146", "name": "毅少", "category": "男声", "style": "坚毅男声", "scenario": "军事内容、历史讲解、正能量视频"},
    {"id": "1144", "name": "宇少", "category": "男声", "style": "磁性男声", "scenario": "广告配音、品牌宣传、有声读物"},
    {"id": "806", "name": "小亮", "category": "男声", "style": "俏皮男声", "scenario": "搞笑视频、娱乐解说、综艺节目"},
    {"id": "182", "name": "风吟", "category": "女声", "style": "古风女声", "scenario": "古风故事、诗词朗诵、传统文化"},
]

base_url = "https://pdd5.oss-cn-shanghai.aliyuncs.com/static/tts/audio/"

def download_audio(char):
    url1 = f"{base_url}{char['id']}_default.mp3"
    url2 = f"{base_url}{char['id']}_0.mp3"
    
    for url in [url1, url2]:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                filename = f"{char['name']}-{char['style']}.mp3"
                filepath = os.path.join(audio_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"下载成功: {filename}")
                return True
        except Exception as e:
            continue
    print(f"下载失败: {char['name']}")
    return False

success_count = 0
downloaded_chars = []
for char in characters:
    if download_audio(char):
        success_count += 1
        downloaded_chars.append(char)

print(f"\n下载完成！成功下载 {success_count}/{len(characters)} 个音频文件")

category_groups = {}
for char in downloaded_chars:
    cat = char['category']
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
        doc_content += f"### {char['name']}\n\n"
        doc_content += f"| 属性 | 内容 |\n"
        doc_content += f"| --- | --- |\n"
        doc_content += f"| 音频文件 | `{filename}` |\n"
        doc_content += f"| 角色特色 | {char['style']} |\n"
        doc_content += f"| 试用场景 | {char['scenario']} |\n"
        doc_content += "\n"

doc_path = os.path.join(audio_dir, "克隆音频角色列表说明.md")
with open(doc_path, 'w', encoding='utf-8') as f:
    f.write(doc_content)

print(f"介绍文档已创建: {doc_path}")