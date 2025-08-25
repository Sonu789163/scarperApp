#!/usr/bin/env python3
"""
Debug script to see what HTML content is returned from Swildesk
"""

import requests
from bs4 import BeautifulSoup
import json

def debug_scrape(url):
    """Debug scrape to see what's in the HTML"""
    
    # Set headers to mimic a real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
        "Referer": "https://support.swildesk.com/"
    }
    
    try:
        print(f"Fetching: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
        print(f"Content Length: {len(response.content)} bytes")
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for title
        title_tag = soup.find('title')
        if title_tag:
            print(f"\nTitle tag: {title_tag.get_text(strip=True)}")
        
        # Check for h1 tags
        h1_tags = soup.find_all('h1')
        print(f"\nH1 tags found: {len(h1_tags)}")
        for i, h1 in enumerate(h1_tags):
            print(f"  H1 {i+1}: {h1.get_text(strip=True)}")
            print(f"    Classes: {h1.get('class', [])}")
        
        # Check for article-related elements
        article_selectors = [
            '.kb-article', '.kb-article__content', '.article-content',
            '.kb-content', '.knowledge-article', '.help-article',
            '.support-article', '.article-body', '.content-main',
            '.main-content', 'article', '.portal-content', '#portal_content'
        ]
        
        print(f"\nChecking article selectors:")
        for selector in article_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"  {selector}: {len(elements)} elements found")
                for i, el in enumerate(elements[:3]):  # Show first 3
                    text = el.get_text(strip=True)[:100]
                    print(f"    Element {i+1}: {text}...")
            else:
                print(f"  {selector}: No elements found")
        
        # Check for any divs with substantial text
        print(f"\nChecking for divs with substantial text:")
        all_divs = soup.find_all('div')
        divs_with_text = []
        
        for div in all_divs:
            text = div.get_text(strip=True)
            if len(text) > 200:  # More than 200 characters
                divs_with_text.append((div, text))
        
        # Sort by text length
        divs_with_text.sort(key=lambda x: len(x[1]), reverse=True)
        
        print(f"Found {len(divs_with_text)} divs with substantial text:")
        for i, (div, text) in enumerate(divs_with_text[:5]):  # Show top 5
            classes = div.get('class', [])
            id_attr = div.get('id', '')
            print(f"  Div {i+1}: {len(text)} chars, classes: {classes}, id: {id_attr}")
            print(f"    Text preview: {text[:200]}...")
        
        # Check if it's a JavaScript-heavy page
        scripts = soup.find_all('script')
        print(f"\nScripts found: {len(scripts)}")
        
        # Check for common JavaScript frameworks
        html_str = str(soup)
        if 'react' in html_str.lower():
            print("  React detected")
        if 'vue' in html_str.lower():
            print("  Vue detected")
        if 'angular' in html_str.lower():
            print("  Angular detected")
        if 'spa' in html_str.lower():
            print("  Single Page Application detected")
        
        # Save HTML for inspection
        with open('debug_output.html', 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
        print(f"\nHTML saved to debug_output.html")
        
        return soup
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    test_url = "https://support.swildesk.com/portal/en/kb/articles/import-data-in-swilerp-retailgraph-through-csv"
    debug_scrape(test_url)
