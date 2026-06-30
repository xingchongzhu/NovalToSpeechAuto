import json
import glob
import re

# 获取所有JSON文件
files = glob.glob('/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/蜀山剑侠转json/*.json')

processed_count = 0
modified_count = 0

for file_path in files:
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # 获取原始标题
        original_title = data['data'][0]['api']['voice']['text']
        
        # 从文件名提取章节序号
        filename = file_path.split('/')[-1]
        # 匹配：第[一二三四五六七八九十百千万\d]+回
        pattern = r'第[一二三四五六七八九十百千万\d]+回'
        match = re.search(pattern, filename)
        
        if match:
            new_title = match.group(0)
        else:
            new_title = original_title
        
        # 更新标题
        if new_title != original_title:
            data['data'][0]['api']['voice']['text'] = new_title
            
            with open(file_path, 'w') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            modified_count += 1
            print(f'修改: {filename}')
            print(f'  原标题: {original_title[:50]}...')
            print(f'  新标题: {new_title}')
            print()
        
        processed_count += 1
    except Exception as e:
        print(f'处理失败: {filename} - {e}')

print(f'\n处理完成！共处理 {processed_count} 个文件，修改 {modified_count} 个文件。')
