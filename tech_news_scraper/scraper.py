#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
import os
import re
import html

class TechNewsScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.news_data = []

    def fetch_url(self, url, timeout=15):
        try:
            response = self.session.get(url, timeout=timeout)
            content_type = response.headers.get('Content-Type', '')
            if 'xml' in content_type.lower() or url.endswith(('.xml', '/rss', '/feed')):
                response.encoding = 'utf-8'
            else:
                response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            print(f"请求失败: {url} - {e}")
            return None

    def extract_article_content(self, url, source):
        content = self.fetch_url(url)
        if not content:
            return None
        
        soup = BeautifulSoup(content, 'html.parser')
        text = ""
        
        try:
            if source == '新浪科技':
                article = soup.find('article', class_='article')
                if article:
                    text = article.get_text(strip=True)
                else:
                    content_div = soup.find('div', id='articleContent')
                    if content_div:
                        text = content_div.get_text(strip=True)
            
            elif source == '36氪':
                article = soup.find('article', class_='article-content')
                if article:
                    text = article.get_text(strip=True)
                else:
                    content_div = soup.find('div', class_='article-content-box')
                    if content_div:
                        text = content_div.get_text(strip=True)
            
            elif source == '网易科技':
                content_div = soup.find('div', class_='post_body')
                if content_div:
                    text = content_div.get_text(strip=True)
                else:
                    article = soup.find('article')
                    if article:
                        text = article.get_text(strip=True)
            
            elif source == '机器之心':
                content_div = soup.find('div', class_='article-content')
                if content_div:
                    text = content_div.get_text(strip=True)
            
            elif source == 'IT之家':
                content_div = soup.find('div', id='articleContent')
                if content_div:
                    text = content_div.get_text(strip=True)
            
            elif source == '知乎日报':
                content_div = soup.find('div', class_='article-content')
                if content_div:
                    text = content_div.get_text(strip=True)
            
            elif source == '爱范儿':
                content_div = soup.find('div', class_='post-content')
                if content_div:
                    text = content_div.get_text(strip=True)
            
            elif source == '掘金':
                content_div = soup.find('article', class_='article-detail')
                if content_div:
                    text = content_div.get_text(strip=True)
                else:
                    content_div = soup.find('div', class_='markdown-body')
                    if content_div:
                        text = content_div.get_text(strip=True)
            
            else:
                article = soup.find('article')
                if article:
                    text = article.get_text(strip=True)
                else:
                    content_div = soup.find('div', class_='content')
                    if content_div:
                        text = content_div.get_text(strip=True)
        
        except Exception as e:
            print(f"提取 {source} 内容失败: {e}")
        
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def simplify_content(self, content, source):
        if not content:
            return None
        
        news_sources = [
            'IT之家', '新浪科技', '网易科技', '36氪', '机器之心',
            '虎嗅', '爱范儿', '掘金', '极客公园', 'CNBeta', '知乎日报'
        ]
        
        simplified = content
        
        for source_name in news_sources:
            patterns = [
                rf'{source_name}\s*\d+\s*月\s*\d+\s*日\s*消息',
                rf'{source_name}\s+消息',
                rf'{source_name}\s*讯',
                rf'来源[:：]\s*{source_name}',
                rf'{source_name}\s*报道',
                rf'{source_name}\s*注意到[，,，\s]*',
                rf'{source_name}\s*了解[到至][，,，\s]*',
                # 删除文中出现的来源引用短语（如 "据IT之家了解,"、"IT之家查询参数表获悉" 等）
                rf'据{source_name}.+?[，,]',
                rf'{source_name}从.+?[，,]',
                rf'{source_name}查询.{{0,10}}?[，,]',
                rf'{source_name}附上[^：:]+?[：:]',
                rf'{source_name}注[：:，,]\s*',
                rf'据{source_name}',
                rf'{source_name}从',
                rf'{source_name}查询',
                rf'{source_name}附上',
            ]
            for pattern in patterns:
                simplified = re.sub(pattern, '', simplified)
        
        # 删除推广语句
        simplified = re.sub(r'#欢迎关注[^#]*#?\s*', '', simplified)
        simplified = re.sub(r'【[^】]+】', '', simplified)
        simplified = re.sub(r'（[^）]+）', '', simplified)
        simplified = re.sub(r'\([^)]+\)', '', simplified)
        
        simplified = re.sub(r'\s+', ' ', simplified).strip()
        
        simplified = simplified.lstrip('，,')
        
        simplified = simplified.replace('、', ', ').replace('，', ', ').replace('。', '. ')
        simplified = simplified.replace('！', '! ').replace('？', '? ')
        
        simplified = simplified.strip()
        
        return simplified if len(simplified) > 10 else None

    def extract_summary(self, content, max_length=500):
        if not content:
            return None
        if len(content) <= max_length:
            return content
        summary = content[:max_length]
        last_period = summary.rfind('。')
        last_comma = summary.rfind('，')
        last_dot = summary.rfind('.')
        
        if last_period > last_comma and last_period > last_dot:
            summary = summary[:last_period+1]
        elif last_comma > last_dot:
            summary = summary[:last_comma+1]
        elif last_dot > 0:
            summary = summary[:last_dot+1]
        
        return summary if len(summary) > 10 else content[:max_length]

    def parse_rss(self, url, source, category, fetch_detail=False):
        content = self.fetch_url(url)
        if not content:
            return
        
        soup = BeautifulSoup(content, 'xml')
        items = soup.find_all('item')
        
        for item in items[:10]:
            title_tag = item.find('title')
            link_tag = item.find('link')
            pub_date_tag = item.find('pubDate')
            desc_tag = item.find('description') or item.find('content:encoded')
            
            if title_tag and link_tag:
                title = title_tag.get_text(strip=True)
                title = html.unescape(title)
                link = link_tag.get_text(strip=True)
                pub_date = pub_date_tag.get_text(strip=True) if pub_date_tag else datetime.now().strftime('%Y-%m-%d %H:%M')
                
                summary = None
                full_content = None
                simplified_content = None
                
                if desc_tag:
                    desc_text = desc_tag.get_text(strip=True)
                    desc_text = html.unescape(desc_text)
                    desc_text = re.sub(r'<[^>]+>', '', desc_text)
                    desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                    if desc_text:
                        summary = desc_text
                
                if fetch_detail:
                    print(f"  正在抓取详情: {title[:30]}...")
                    full_content = self.extract_article_content(link, source)
                    if full_content:
                        if not summary:
                            summary = full_content
                        simplified_content = self.simplify_content(full_content, source)
                    elif summary:
                        simplified_content = self.simplify_content(summary, source)
                elif summary:
                    simplified_content = self.simplify_content(summary, source)
                
                news_item = {
                    'title': title,
                    'source': source,
                    'url': link,
                    'category': category,
                    'time': pub_date,
                    'summary': summary,
                    'content': full_content,
                    'simplified_content': simplified_content
                }
                self.news_data.append(news_item)

    def parse_sina_tech(self, fetch_detail=False):
        url = "https://tech.sina.com.cn/rss/tech.xml"
        self.parse_rss(url, '新浪科技', '科技', fetch_detail)

    def parse_36kr(self, fetch_detail=False):
        url = "https://36kr.com/feed"
        self.parse_rss(url, '36氪', '科技', fetch_detail)

    def parse_netease_tech(self, fetch_detail=False):
        url = "https://tech.163.com/special/00097UHL/rss.xml"
        self.parse_rss(url, '网易科技', '科技', fetch_detail)

    def parse_ai_news(self, fetch_detail=False):
        url = "https://www.jiqizhixin.com/rss"
        self.parse_rss(url, '机器之心', 'AI', fetch_detail)

    def parse_ithome(self, fetch_detail=False):
        url = "https://www.ithome.com/rss/"
        self.parse_rss(url, 'IT之家', '科技', fetch_detail)

    def parse_techcrunch(self, fetch_detail=False):
        url = "https://techcrunch.com/feed/"
        self.parse_rss(url, 'TechCrunch', '国际', fetch_detail)

    def parse_theverge(self, fetch_detail=False):
        url = "https://www.theverge.com/rss/index.xml"
        self.parse_rss(url, 'The Verge', '国际', fetch_detail)

    def parse_wired(self, fetch_detail=False):
        url = "https://www.wired.com/feed/rss"
        self.parse_rss(url, 'Wired', '国际', fetch_detail)

    def parse_ars_technica(self, fetch_detail=False):
        url = "https://feeds.arstechnica.com/arstechnica/index"
        self.parse_rss(url, 'Ars Technica', '国际', fetch_detail)

    def parse_reuters_tech(self, fetch_detail=False):
        url = "https://feeds.reuters.com/reuters/technologyNews"
        self.parse_rss(url, '路透社科技', '国际', fetch_detail)

    def parse_bbc_tech(self, fetch_detail=False):
        url = "https://feeds.bbci.co.uk/news/technology/rss.xml"
        self.parse_rss(url, 'BBC科技', '国际', fetch_detail)

    def parse_huxiu(self, fetch_detail=False):
        url = "https://www.huxiu.com/rss/"
        self.parse_rss(url, '虎嗅', '国际', fetch_detail)

    def parse_ifanr(self, fetch_detail=False):
        url = "https://www.ifanr.com/feed"
        self.parse_rss(url, '爱范儿', '科技', fetch_detail)

    def parse_juejin(self, fetch_detail=False):
        url = "https://juejin.cn/rss"
        self.parse_rss(url, '掘金', '技术', fetch_detail)

    def scrape_all(self, fetch_detail=False, limit=20):
        self.news_data = []
        sources = [
            ('机器之心', self.parse_ai_news),
            ('36氪', self.parse_36kr),
            ('IT之家', self.parse_ithome),
            ('新浪科技', self.parse_sina_tech),
            ('网易科技', self.parse_netease_tech),
            ('爱范儿', self.parse_ifanr),
            ('虎嗅', self.parse_huxiu)
        ]
        
        exclude_keywords = [
            '教程', '最佳实践', '手把手', '从零开始', '入门指南', 
            '深度解析', '完全指南', '实战', '基础', '筑基',
            '完整指南', '一步步', '保姆级', '入门级', '零基础'
        ]
        
        print("开始抓取科技AI资讯..." + ("（包含详情）" if fetch_detail else ""))
        success_count = 0
        for name, parser in sources:
            print(f"正在抓取 {name}...")
            try:
                parser(fetch_detail)
                success_count += 1
            except Exception as e:
                print(f"抓取 {name} 失败: {e}")
            time.sleep(0.5)
        
        # 按字数筛选：simplified_content 须在 300~3000 字之间，无内容则直接丢弃整条新闻
        filtered_news = []
        for news in self.news_data:
            title = news.get('title', '')
            if any(keyword in title for keyword in exclude_keywords):
                continue

            simplified = (news.get('simplified_content') or '').strip()
            char_count = len(simplified)
            if char_count < 300 or char_count > 3000:
                continue

            filtered_news.append(news)

        self.news_data = filtered_news
        self.news_data.sort(key=lambda x: x['time'], reverse=True)
        self.news_data = self.news_data[:limit]
        print(f"抓取完成，成功获取 {success_count} 个来源，精选 {len(self.news_data)} 条最新资讯")
        return self.news_data

    def save_to_file(self, filename=None):
        if not self.news_data:
            print("没有数据可保存")
            return
        
        if not filename:
            date_str = datetime.now().strftime('%Y-%m-%d')
            time_str = datetime.now().strftime('%H%M%S')
            filename = f"news/{date_str}/tech_news_{date_str}_{time_str}.json"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'count': len(self.news_data),
            'news': self.news_data
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"资讯已保存到: {filename}")
        return filename

    def print_news(self, count=20, show_summary=True):
        if not self.news_data:
            print("没有资讯数据")
            return
        
        print("\n" + "="*100)
        print(f"最新科技AI资讯 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        print("="*100)
        
        for i, news in enumerate(self.news_data[:count], 1):
            print(f"\n{i}. [{news['source']}] [{news['category']}]")
            print(f"   标题: {news['title']}")
            if show_summary and news.get('summary'):
                print(f"   简介: {news['summary']}")
            print(f"   链接: {news['url']}")
            print(f"   时间: {news['time']}")
        
        print("\n" + "="*100)
