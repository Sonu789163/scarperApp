#!/usr/bin/env python3
"""
Check the extracted content to see what's being captured
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from scraper import SwildeskScraper

async def check_content():
    """Check the extracted content in detail"""
    print("🔍 Checking extracted content in detail")
    print("=" * 60)
    
    # Create scraper instance
    scraper = SwildeskScraper()
    
    test_url = "https://support.swildesk.com/portal/en/kb/articles/import-data-in-swilerp-retailgraph-through-csv"
    
    try:
        print(f"Testing URL: {test_url}")
        result = await scraper.scrape_article(test_url)
        
        print(f"\n📊 Results:")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Title: {result.get('title', 'No title')}")
        print(f"Content length: {len(result.get('content', ''))}")
        print(f"Images: {len(result.get('images', []))}")
        print(f"URL: {result.get('url', 'No URL')}")
        
        if result.get('error'):
            print(f"⚠️ Error: {result.get('error')}")
        
        # Show the first 1000 characters of content
        content = result.get('content', '')
        if content:
            print(f"\n📝 Content Preview (first 1000 chars):")
            print("-" * 50)
            print(content[:1000])
            print("-" * 50)
            
            # Check for navigation elements that might still be there
            nav_indicators = [
                'skip to content', 'skip to menu', 'skip to footer',
                'home', 'my tickets', 'knowledge base', 'community', 'blog', 'updates',
                'sign in', 'sign up', 'font size', 'layout', 'full width',
                'search our knowledge base', 'ask the swil network',
                'submit a support request', 'about swil', 'stay connected',
                'corporate office', 'powered by zoho', 'terms of service', 'privacy policy',
                'welcome to swindia portal', 'swildesk | swil support'
            ]
            
            print(f"\n🔍 Checking for navigation elements:")
            for indicator in nav_indicators:
                if indicator in content.lower():
                    print(f"  ❌ Found: {indicator}")
                else:
                    print(f"  ✅ Clean: {indicator}")
        
        # Show images with their reference text
        images = result.get('images', [])
        if images:
            print(f"\n🖼️ Images found:")
            for i, img in enumerate(images[:5]):  # Show first 5
                print(f"  {i+1}. URL: {img.get('url', 'No URL')[:80]}...")
                print(f"     Reference: {img.get('reference_text', 'No reference text')}")
                print(f"     Alt: {img.get('alt_text', 'No alt text')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None
    
    finally:
        # Clean up
        scraper.close()

if __name__ == "__main__":
    asyncio.run(check_content())
