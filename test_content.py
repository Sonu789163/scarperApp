#!/usr/bin/env python3
"""
Test script to show the full extracted content
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from scraper import SwildeskScraper

async def test_content():
    """Test the scraper and show full content"""
    print("🚀 Testing Swildesk Scraper - Full Content")
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
        
        if result.get('content'):
            print(f"\n📝 FULL CONTENT:")
            print("=" * 60)
            print(result.get('content'))
            print("=" * 60)
        
        if result.get('images'):
            print(f"\n🖼️ Images found:")
            for i, img in enumerate(result.get('images', []), 1):
                if isinstance(img, dict):
                    print(f"  {i}. URL: {img.get('url', 'No URL')}")
                    if img.get('reference_text'):
                        print(f"     Reference: {img.get('reference_text')}")
                else:
                    print(f"  {i}. {img}")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None
    
    finally:
        # Clean up
        scraper.close()

if __name__ == "__main__":
    asyncio.run(test_content())
