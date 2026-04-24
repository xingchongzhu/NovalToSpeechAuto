import os

audio_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio"

files = [f for f in os.listdir(audio_dir) if f.endswith('.mp3')]

def classify_character(filename):
    name = filename.replace('.mp3', '')
    
    if '童声' in filename:
        if '女' in filename or 'girl' in filename.lower() or 'Girl' in filename:
            return ('童声', '女童声')
        elif '男' in filename or 'boy' in filename.lower() or 'Boy' in filename:
            return ('童声', '男童声')
        else:
            return ('童声', '童声')
    elif '老人' in filename or 'old' in filename.lower():
        if '女' in filename:
            return ('老人', '女老人')
        else:
            return ('老人', '男老人')
    elif '女声' in filename:
        if '少年' in filename or '少女' in filename or 'teen' in filename.lower():
            return ('女声', '女少年')
        elif '中年' in filename or '阿姨' in filename or '中年女' in filename:
            return ('女声', '女中年')
        elif '青年' in filename or '少女' in filename:
            return ('女声', '女青年')
        else:
            return ('女声', '女青年')
    elif '男声' in filename:
        if '少年' in filename or '少男' in filename:
            return ('男声', '男少年')
        elif '中年' in filename or '大叔' in filename or '中年男' in filename:
            return ('男声', '男中年')
        elif '青年' in filename:
            return ('男声', '男青年')
        elif '老年' in filename or '大爷' in filename:
            return ('男声', '男老年')
        else:
            return ('男声', '男青年')
    else:
        return ('其他', '特色角色')

categories = {}
for f in files:
    main_cat, sub_cat = classify_character(f)
    if main_cat not in categories:
        categories[main_cat] = {}
    if sub_cat not in categories[main_cat]:
        categories[main_cat][sub_cat] = []
    
    full_name = f.replace('.mp3', '')
    tags = full_name.split('-')[1:] if '-' in full_name else ['']
    style = '-'.join(tags)
    
    scenario = '通用配音场景'
    if '影视解说' in full_name:
        scenario = '影视解说、纪录片'
    elif '情感语录' in full_name:
        scenario = '情感电台、短视频'
    elif '故事' in full_name:
        scenario = '有声读物、故事讲述'
    elif '广告' in full_name:
        scenario = '广告配音、宣传片'
    elif '美食' in full_name:
        scenario = '美食视频、生活内容'
    
    categories[main_cat][sub_cat].append({
        'filename': f,
        'name': full_name,
        'style': style,
        'scenario': scenario
    })

doc_content = "# 克隆音频角色列表说明\n\n"
doc_content += "## 角色分类总览\n\n"

total = 0
for main_cat in sorted(categories.keys()):
    sub_total = sum(len(items) for items in categories[main_cat].values())
    total += sub_total
    doc_content += f"- **{main_cat}**: {sub_total} 个角色\n"
    for sub_cat in sorted(categories[main_cat].keys()):
        count = len(categories[main_cat][sub_cat])
        doc_content += f"  - {sub_cat}: {count} 个\n"
doc_content += f"\n**总计**: {total} 个角色\n\n"

for main_cat in sorted(categories.keys()):
    doc_content += f"## {main_cat}\n\n"
    for sub_cat in sorted(categories[main_cat].keys()):
        items = categories[main_cat][sub_cat]
        doc_content += f"### {sub_cat}（共 {len(items)} 个）\n\n"
        doc_content += f"| 角色名 | 音频文件 | 角色特色 | 试用场景 |\n"
        doc_content += f"| --- | --- | --- | --- |\n"
        for item in items:
            doc_content += f"| {item['name']} | `{item['filename']}` | {item['style']} | {item['scenario']} |\n"
        doc_content += "\n"

doc_path = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/剧本生成skill/克隆音频角色列表说明.md"
with open(doc_path, 'w', encoding='utf-8') as f:
    f.write(doc_content)

print(f"文档已更新: {doc_path}")