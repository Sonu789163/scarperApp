#!/usr/bin/env python3
"""
Test script for the Swildesk scraper
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from scraper import scrape_url, scrape_url_sync


async def test_async_scraper():
    """Test the async scraper"""
    print("Testing async scraper...")
    
    test_url = "https://support.swildesk.com/portal/en/kb/articles/import-data-in-swilerp-retailgraph-through-csv"
    
    try:
        result = await scrape_url(test_url)
        print(f"✅ Async scraper successful!")
        print(f"Title: {result.get('title', 'No title')}")
        print(f"Content length: {len(result.get('content', ''))}")
        print(f"Images: {len(result.get('images', []))}")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"URL: {result.get('url', 'No URL')}")
        
        if result.get('error'):
            print(f"⚠️ Error: {result.get('error')}")
            
        return result
        
    except Exception as e:
        print(f"❌ Async scraper failed: {e}")
        return None


def test_sync_scraper():
    """Test the sync scraper"""
    print("\nTesting sync scraper...")
    
    test_url = "https://support.swildesk.com/portal/en/kb/articles/import-data-in-swilerp-retailgraph-through-csv"
    
    try:
        result = scrape_url_sync(test_url)
        print(f"✅ Sync scraper successful!")
        print(f"Title: {result.get('title', 'No title')}")
        print(f"Content length: {len(result.get('content', ''))}")
        print(f"Images: {len(result.get('images', []))}")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"URL: {result.get('url', 'No URL')}")
        
        if result.get('error'):
            print(f"⚠️ Error: {result.get('error')}")
            
        return result
        
    except Exception as e:
        print(f"❌ Sync scraper failed: {e}")
        return None


async def main():
    """Main test function"""
    print("🚀 Starting Swildesk Scraper Tests")
    print("=" * 50)
    
    # Test async scraper
    async_result = await test_async_scraper()
    
    # Test sync scraper
    sync_result = test_sync_scraper()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    if async_result and async_result.get('status') == 'success':
        print("✅ Async scraper: PASSED")
    else:
        print("❌ Async scraper: FAILED")
    
    if sync_result and sync_result.get('status') == 'success':
        print("✅ Sync scraper: PASSED")
    else:
        print("❌ Sync scraper: FAILED")
    
    print("\n🎯 Ready for n8n integration!")


if __name__ == "__main__":
    asyncio.run(main())
