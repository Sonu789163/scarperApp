#!/usr/bin/env python3
"""
Explore the actual page structure to find the best scraping approach
"""

import requests
from bs4 import BeautifulSoup
import json
import time

def explore_page(url):
    """Explore the page structure to understand how to scrape it"""
    
    print(f"🔍 Exploring: {url}")
    print("=" * 60)
    
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
        print("📡 Fetching page...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"✅ Status: {response.status_code}")
        print(f"📏 Content Length: {len(response.content)} bytes")
        print(f"🔗 Final URL: {response.url}")
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for title
        title_tag = soup.find('title')
        if title_tag:
            print(f"\n📋 Title: {title_tag.get_text(strip=True)}")
        
        # Check for meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            print(f"📝 Meta Description: {meta_desc.get('content', '')[:100]}...")
        
        # Look for any text content
        body_text = soup.get_text(strip=True)
        print(f"\n📄 Total Text Length: {len(body_text)} characters")
        
        if len(body_text) > 0:
            print(f"📖 Text Preview (first 300 chars):")
            print(f"{body_text[:300]}...")
        
        # Check for React/JavaScript indicators
        scripts = soup.find_all('script')
        print(f"\n🔧 Scripts found: {len(scripts)}")
        
        # Look for React indicators
        html_str = str(soup).lower()
        if 'react' in html_str:
            print("⚛️ React detected")
        if 'zoho' in html_str:
            print("🏢 Zoho detected")
        if 'spa' in html_str or 'single page' in html_str:
            print("📱 Single Page Application detected")
        
        # Check for any article-related content
        print(f"\n🔍 Looking for article content...")
        
        # Try to find any content containers
        content_containers = []
        
        # Look for divs with substantial text
        all_divs = soup.find_all('div')
        for div in all_divs:
            text = div.get_text(strip=True)
            if len(text) > 200:  # More than 200 characters
                classes = div.get('class', [])
                id_attr = div.get('id', '')
                content_containers.append({
                    'text_length': len(text),
                    'classes': classes,
                    'id': id_attr,
                    'text_preview': text[:100]
                })
        
        # Sort by text length
        content_containers.sort(key=lambda x: x['text_length'], reverse=True)
        
        print(f"📦 Found {len(content_containers)} divs with substantial content:")
        for i, container in enumerate(content_containers[:5]):  # Show top 5
            print(f"  {i+1}. {container['text_length']} chars | Classes: {container['classes']} | ID: {container['id']}")
            print(f"     Preview: {container['text_preview']}...")
        
        # Check if this is a loading page
        if len(body_text) < 1000:
            print(f"\n⚠️ This appears to be a loading page or SPA shell")
            print(f"   The actual content is likely loaded via JavaScript")
            print(f"   We'll need to use browser automation (Selenium)")
        else:
            print(f"\n✅ This page has substantial content that can be scraped directly")
        
        # Save HTML for inspection
        with open('explored_page.html', 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
        print(f"\n💾 HTML saved to 'explored_page.html' for inspection")
        
        return soup
        
    except Exception as e:
        print(f"❌ Error exploring page: {e}")
        return None

def check_network_requests(url):
    """Check what network requests the page might make"""
    print(f"\n🌐 Checking potential network requests...")
    
    # Common API patterns for Zoho/Zendesk systems
    api_patterns = [
        url.replace('/portal/en/kb/articles/', '/portal/api/kb/articles/'),
        url.replace('/portal/en/kb/articles/', '/portal/api/articles/'),
        url.replace('/portal/en/kb/articles/', '/api/kb/articles/'),
        url.replace('/portal/en/kb/articles/', '/api/articles/'),
        url.replace('/portal/en/kb/articles/', '/api/v1/articles/'),
        url.replace('/portal/en/kb/articles/', '/api/v2/articles/'),
        url.replace('/portal/en/kb/articles/', '/api/kb/'),
        url.replace('/portal/en/kb/articles/', '/api/'),
    ]
    
    print("🔗 Potential API endpoints to check:")
    for pattern in api_patterns:
        print(f"  {pattern}")
    
    return api_patterns

if __name__ == "__main__":
    test_url = "https://support.swildesk.com/portal/en/kb/articles/import-data-in-swilerp-retailgraph-through-csv"
    
    # Explore the page
    soup = explore_page(test_url)
    
    # Check network requests
    api_patterns = check_network_requests(test_url)
    
    print(f"\n🎯 Next Steps:")
    print(f"1. Check the saved HTML file for content structure")
    print(f"2. Try the suggested API endpoints")
    print(f"3. If no content found, use Selenium for JavaScript rendering")
