import re

input_file = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来角色配配音表.md"
output_file = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来角色配配音表.md"

with open(input_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed_lines = []
for line in lines:
    if line.startswith('| 傅噤') or line.startswith('| 冯雪涛') or line.startswith('| 刘景龙') or \
       line.startswith('| 刘材') or line.startswith('| 卢白象') or line.startswith('| 吴承霈') or \
       line.startswith('| 周米粒') or line.startswith('| 周肥') or line.startswith('| 孙怀中') or \
       line.startswith('| 孙道长') or line.startswith('| 宋睦') or line.startswith('| 宋长镜') or \
       line.startswith('| 宋集薪') or line.startswith('| 宋雨烧') or line.startswith('| 寇名') or \
       line.startswith('| 崔嵬') or line.startswith('| 崔诚') or line.startswith('| 庞兰溪') or \
       line.startswith('| 张山峰') or line.startswith('| 徐远霞') or line.startswith('| 曹峻') or \
       line.startswith('| 曹慈') or line.startswith('| 朱敛') or line.startswith('| 李二') or \
       line.startswith('| 李柳') or line.startswith('| 杜俞') or line.startswith('| 杜懋') or \
       line.startswith('| 杨凝性') or line.startswith('| 林君璧') or line.startswith('| 林守一') or \
       line.startswith('| 柳赤诚') or line.startswith('| 温飞卿') or line.startswith('| 王朱') or \
       line.startswith('| 白也') or line.startswith('| 白裳') or line.startswith('| 石柔') or \
       line.startswith('| 祁真') or line.startswith('| 翠花') or line.startswith('| 范峻茂') or \
       line.startswith('| 蔡金简') or line.startswith('| 许白') or line.startswith('| 谢实') or \
       line.startswith('| 谢松花') or line.startswith('| 贾生') or line.startswith('| 赵天籁') or \
       line.startswith('| 邵宝卷') or line.startswith('| 郑大风') or line.startswith('| 郑居中') or \
       line.startswith('| 郭竹酒') or line.startswith('| 钟魁') or line.startswith('| 阮邛') or \
       line.startswith('| 隋右边') or line.startswith('| 马兰') or line.startswith('| 马婆婆') or \
       line.startswith('| 马苦玄') or line.startswith('| 黄粱') or line.startswith('| 齐景龙'):
        
        parts = line.split('|')
        if len(parts) >= 6:
            voice_desc = parts[4].strip() + ' | ' + parts[5].strip()
            fixed_line = f"| {parts[1].strip()} | {parts[2].strip()} | {parts[3].strip()} | {voice_desc} |\n"
            fixed_lines.append(fixed_line)
        else:
            fixed_lines.append(line)
    else:
        fixed_lines.append(line)

with open(output_file, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print("格式修复完成")