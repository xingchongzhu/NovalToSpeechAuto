import requests
import os
from bs4 import BeautifulSoup

BASE_URL = "http://www.xheiyan.info"
NOVEL_NAME = "剑来"
OUTPUT_DIR = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本/剑来"

def get_chapter_links():
    response = requests.get(f"{BASE_URL}/jianlai/")
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    links = []
    for a in soup.find_all('a', href=True):
        if '/jianlai/' in a['href'] and '.html' in a['href']:
            title = a.get_text(strip=True)
            if title and (title.startswith('第') or title.startswith('新书') or title.startswith('上架')):
                links.append((title, a['href']))
    
    return links

def get_filename(title):
    filename = f"{NOVEL_NAME}{title}.txt"
    filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
    return filename

def download_chapter(url, title):
    filename = get_filename(title)
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    if os.path.exists(filepath):
        return True
    
    try:
        response = requests.get(f"{BASE_URL}{url}")
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        content_div = soup.find('div', class_='contentbox')
        if not content_div:
            content_div = soup.find('div', id='content')
        if not content_div:
            content_div = soup.find('div', class_='content')
        
        if content_div:
            content = content_div.get_text(separator='\n', strip=True)
            
            content = content.replace('本章有错误，我要提交', '')
            content = content.replace('返回目录', '')
            content = content.replace('上一章', '')
            content = content.replace('下一章', '')
            content = content.replace('剑来最新章节', '')
            content = content.replace('手机看剑来', '')
            content = content.replace('欢迎收藏', '')
            content = content.replace('http://www.xheiyan.info/jianlai/', '')
            content = content.replace('http://m.xheiyan.info/jianlai/', '')
            content = content.replace('x23US.COM更新最快', '')
            content = content.replace('Ｘ２３ＵＳ．ＣＯＭ更新最快', '')
            
            lines = content.split('\n')
            lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('ps') and not line.strip().startswith('PS')]
            content = '\n\n'.join(lines)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"{title}\n\n")
                f.write(content)
            print(f"下载成功: {filename}")
            return True
        else:
            print(f"未找到内容: {title}")
            return False
    except Exception as e:
        print(f"下载失败 {title}: {e}")
        return False

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    links = get_chapter_links()
    print(f"共找到 {len(links)} 个章节")
    
    existing_files = set()
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith('.txt'):
            existing_files.add(f)
    
    skipped_count = 0
    success_count = 0
    failed_count = 0
    
    for title, url in links:
        filename = get_filename(title)
        if filename in existing_files:
            skipped_count += 1
            continue
        
        if download_chapter(url, title):
            success_count += 1
        else:
            failed_count += 1
    
    print(f"\n下载完成！")
    print(f"跳过已存在: {skipped_count}")
    print(f"成功下载: {success_count}")
    print(f"下载失败: {failed_count}")

if __name__ == "__main__":
    main()