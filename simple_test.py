#!/usr/bin/env python3
"""
Simple test script for the Swildesk scraper
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from scraper import SwildeskScraper


async def test_scraper():
    """Test the scraper with a simple approach"""
    print("🚀 Testing Swildesk Scraper")
    print("=" * 50)
    
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
            print(f"\n📝 Content Preview (first 200 chars):")
            print(f"{result.get('content', '')[:200]}...")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None
    
    finally:
        # Clean up
        scraper.close()


if __name__ == "__main__":
    asyncio.run(test_scraper())
