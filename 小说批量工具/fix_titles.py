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
        
        # 处理标题：去掉章节序号部分
        # 匹配模式：第X回 或 第XX回 或 第XXX回（包括中文数字和阿拉伯数字）
        # 示例：
        # "第一回 月夜棹孤舟..." → "月夜棹孤舟..."
        # "第165回\n教主返仙山..." → "教主返仙山..."
        # "第三十二回 弥天星雨..." → "弥天星雨..."
        
        # 使用正则表达式匹配并移除章节序号
        # 匹配：第[一二三四五六七八九十百千万\d]+回\s*
        pattern = r'第[一二三四五六七八九十百千万\d]+回\s*'
        new_title = re.sub(pattern, '', original_title).strip()
        
        # 如果新标题为空，保留原标题
        if not new_title:
            new_title = original_title
        
        # 更新标题
        if new_title != original_title:
            data['data'][0]['api']['voice']['text'] = new_title
            
            with open(file_path, 'w') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            modified_count += 1
            filename = file_path.split('/')[-1]
            print(f'修改: {filename}')
            print(f'  原标题: {original_title[:50]}...')
            print(f'  新标题: {new_title[:50]}...')
            print()
        
        processed_count += 1
    except Exception as e:
        print(f'处理失败: {file_path} - {e}')

print(f'\n处理完成！共处理 {processed_count} 个文件，修改 {modified_count} 个文件。')
