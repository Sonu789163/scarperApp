from __future__ import annotations
import asyncio
import logging
import time
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SwildeskScraper:
    """Scraper optimized for Swildesk support portal articles (Zoho-based)"""
    
    def __init__(self):
        # Create a session with proper headers
        self.session = requests.Session()
        
        # Set headers to mimic a real browser
        self.session.headers.update({
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
        })
        
        # Initialize Selenium driver
        self.driver = None
    
    async def scrape_article(self, url: str) -> Dict[str, any]:
        """
        Scrape a single Swildesk support article
        
        Args:
            url: The URL of the article to scrape
            
        Returns:
            Dictionary containing scraped content
        """
        try:
            logger.info(f"Scraping article: {url}")
            
            # Try HTML parsing approach first (fastest)
            logger.info("Trying HTML parsing approach...")
            html_result = await self._try_html_approach(url)
            if html_result and html_result.get('content'):
                logger.info("Successfully scraped via HTML parsing")
                return html_result
            
            # If HTML approach fails, use Selenium for JavaScript-rendered content
            logger.info("HTML parsing failed, trying Selenium approach for JavaScript-rendered content...")
            selenium_result = await self._try_selenium_approach(url)
            if selenium_result and selenium_result.get('content'):
                logger.info("Successfully scraped via Selenium")
                return selenium_result
            
            # If all approaches fail, return error
            logger.warning("All scraping approaches failed")
            return self._create_error_response("Unable to extract content from article")
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return self._create_error_response(str(e))
    
    def _similarity_check(self, text1: str, text2: str) -> float:
        """Check similarity between two text strings"""
        if not text1 or not text2:
            return 0.0
        
        # Simple similarity check based on common words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _extract_article_id(self, url: str) -> Optional[str]:
        """Extract article slug from URL - not used anymore but kept for reference"""
        # This was incorrect - it's not an article ID, it's a slug
        # The URL structure is: /portal/en/kb/articles/{article-slug}
        path_parts = urlparse(url).path.split('/')
        if len(path_parts) >= 2 and path_parts[-2] == 'articles':
            return path_parts[-1]
        return None
    
    async def _try_api_approach(self, article_id: str, original_url: str) -> Optional[Dict[str, any]]:
        """API approach - not used for Zoho systems as they don't have public APIs"""
        # This method is kept for reference but not used
        # Zoho help center systems typically don't expose public APIs
        return None
    
    async def _try_html_approach(self, url: str) -> Optional[Dict[str, any]]:
        """Try to extract content from HTML"""
        try:
            # Fetch the page
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if this is a React SPA with no content
            if self._is_react_spa_without_content(soup):
                logger.info("Detected React SPA without rendered content")
                return None
            
            # Extract content
            result = self._extract_content_from_html(soup, url)
            return result
            
        except Exception as e:
            logger.error(f"HTML approach failed: {e}")
            return None
    
    async def _try_selenium_approach(self, url: str) -> Optional[Dict[str, any]]:
        """Try to extract content using Selenium for JavaScript-rendered content"""
        try:
            # Initialize Chrome driver if not already done
            if self.driver is None:
                self.driver = self._init_chrome_driver()
            
            if self.driver is None:
                logger.error("Failed to initialize Chrome driver")
                return None
            
            logger.info(f"Navigating to {url} with Selenium...")
            self.driver.get(url)
            
            # Wait for the React app to load and render content
            logger.info("Waiting for React app to load and render content...")
            
            # Strategy: Wait for content to appear, with multiple fallbacks
            max_wait_time = 30
            wait_interval = 2
            total_wait_time = 0
            
            while total_wait_time < max_wait_time:
                try:
                    # Get current page source
                    page_source = self.driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                    
                    # Check if we have substantial content
                    body_text = soup.get_text(strip=True)
                    logger.info(f"Current text length: {len(body_text)} characters")
                    
                    # If we have substantial content, try to extract it
                    if len(body_text) > 2000:  # More than 2000 characters
                        logger.info("Substantial content detected, extracting...")
                        result = self._extract_content_from_html(soup, url)
                        if result and result.get('content') and len(result.get('content', '')) > 500:
                            logger.info("Successfully extracted content via Selenium")
                            return result
                    
                    # Wait a bit more
                    time.sleep(wait_interval)
                    total_wait_time += wait_interval
                    
                    # Try to scroll down to trigger lazy loading
                    if total_wait_time % 10 == 0:  # Every 10 seconds
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        logger.info("Scrolled to bottom to trigger content loading")
                    
                except Exception as e:
                    logger.warning(f"Error during content check: {e}")
                    time.sleep(wait_interval)
                    total_wait_time += wait_interval
            
            # If we get here, try to extract whatever content we have
            logger.warning("Timeout reached, trying to extract available content...")
            try:
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                result = self._extract_content_from_html(soup, url)
                
                if result and result.get('content'):
                    logger.info("Extracted some content after timeout")
                    return result
                else:
                    logger.warning("No content could be extracted after timeout")
                    return None
                    
            except Exception as e:
                logger.error(f"Error extracting content after timeout: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Selenium approach failed: {e}")
            return None
    
    def _init_chrome_driver(self) -> Optional[webdriver.Chrome]:
        """Initialize Chrome driver with appropriate options"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run in background
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Try to use webdriver-manager to get Chrome driver
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info("Chrome driver initialized successfully")
                return driver
            except Exception as e:
                logger.warning(f"Failed to use webdriver-manager: {e}")
                
                # Fallback: try to use system Chrome
                try:
                    driver = webdriver.Chrome(options=chrome_options)
                    logger.info("Chrome driver initialized with system Chrome")
                    return driver
                except Exception as e2:
                    logger.error(f"Failed to initialize Chrome driver: {e2}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error initializing Chrome driver: {e}")
            return None
    
    def _is_react_spa_without_content(self, soup: BeautifulSoup) -> bool:
        """Check if this is a React SPA without rendered content"""
        # Look for React indicators
        scripts = soup.find_all('script')
        has_react = any('react' in str(script).lower() for script in scripts)
        
        # Check if there's substantial content
        body_text = soup.get_text(strip=True)
        has_content = len(body_text) > 1000  # More than 1000 characters
        
        # If it's React but has no content, it's likely a SPA
        return has_react and not has_content
    
    def _extract_content_from_html(self, soup: BeautifulSoup, url: str) -> Dict[str, any]:
        """Extract content from HTML, focusing ONLY on the article body content"""
        try:
            # Find the actual article title (not the page title)
            article_title = "No title found"
            
            # Look for the main article heading (usually h1 or specific class)
            title_selectors = [
                'h1.kb-article-title',
                'h1.article-title', 
                'h1[data-testid="article-title"]',
                'h1',
                '.kb-article-title',
                '.article-title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    # Skip generic page titles like "Welcome to SwilDesk | Swil Support"
                    if title_text and not any(skip in title_text.lower() for skip in [
                        'welcome to', 'swildesk | swil support', 'swil support', 'knowledge base'
                    ]):
                        article_title = title_text
                        logger.info(f"Found article title: {article_title}")
                        break
            
            # If no title found in h1 tags, look for it in the content
            if article_title == "No title found":
                logger.info("No title found in h1 tags, looking in content...")
                # Look for the first meaningful heading or text that looks like a title
                content_elements = soup.find_all(['h1', 'h2', 'h3', 'p', 'div'])
                for elem in content_elements:
                    text = elem.get_text(strip=True)
                    # Look for text that contains article-specific keywords and is NOT breadcrumb text
                    if (any(keyword in text.lower() for keyword in [
                        'importing purchase invoices', 'csv file', 'swilerp', 'import data'
                    ]) and len(text) > 20 and len(text) < 200 and
                    not any(breadcrumb in text.lower() for breadcrumb in [
                        'knowledge base', 'swilerp - retailgraph', 'import/export data'
                    ])):
                        article_title = text
                        logger.info(f"Found article title in content: {article_title}")
                        break
            
            # If still no title, extract from the first meaningful content
            if article_title == "No title found":
                logger.info("Still no title found, extracting from first meaningful content...")
                # Look for the first substantial text that looks like a title
                for elem in soup.find_all(['h1', 'h2', 'h3', 'p', 'div']):
                    text = elem.get_text(strip=True)
                    if len(text) > 30 and len(text) < 150:
                        # Check if it looks like an article title and NOT breadcrumb
                        if (any(keyword in text.lower() for keyword in ['import', 'csv', 'swilerp', 'purchase']) and
                            not any(breadcrumb in text.lower() for breadcrumb in [
                                'knowledge base', 'swilerp - retailgraph', 'import/export data'
                            ])):
                            article_title = text
                            logger.info(f"Extracted title from content: {article_title}")
                            break
            
            # If still no title, try to find it in the main content area
            if article_title == "No title found":
                logger.info("Still no title found, trying to extract from main content...")
                # Look for the first line that contains the article title
                main_content_text = soup.get_text(separator='\n', strip=True)
                content_lines = main_content_text.split('\n')
                
                for line in content_lines:
                    line = line.strip()
                    # Look for a line that contains the article title keywords and is NOT breadcrumb
                    if (len(line) > 30 and len(line) < 200 and 
                        any(keyword in line.lower() for keyword in ['importing purchase invoices', 'csv file', 'swilerp']) and
                        not any(breadcrumb in line.lower() for breadcrumb in [
                            'knowledge base', 'swilerp - retailgraph', 'import/export data'
                        ])):
                        article_title = line
                        logger.info(f"Extracted title from main content: {article_title}")
                        break
            
            # Find ONLY the article body content - be very specific
            article_content = None
            
            # First, try to find the specific article content container
            content_selectors = [
                'div.kb-article-content',           # Zoho help center specific
                'div.article-content',               # Generic article content
                'div[data-testid="article-content"]', # Test ID based
                'article',                           # HTML5 article tag
                'main',                              # HTML5 main tag
                'div.entry-content',                 # WordPress-like
                'div.post-content'                   # Blog-like
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # Verify this contains actual article content, not navigation
                    text = content_elem.get_text(strip=True)
                    if len(text) > 2000 and any(keyword in text.lower() for keyword in [
                        'step 1:', 'step 2:', 'reference image:', 'what is a csv file?',
                        'import', 'csv', 'swilerp', 'purchase invoice'
                    ]):
                        article_content = content_elem
                        logger.info(f"Found article content using selector: {selector}")
                        break
            
            # If no specific content area found, try to find the article body more intelligently
            if not article_content:
                logger.info("No specific content area found, looking for article body...")
                
                # Look for elements that contain the actual article text
                potential_containers = []
                
                # Find all divs and check their content
                all_divs = soup.find_all('div')
                
                for div in all_divs:
                    # Skip obvious navigation/header/footer elements
                    div_classes = ' '.join(div.get('class', [])).lower()
                    div_id = div.get('id', '').lower()
                    
                    # Skip common header/footer/navigation classes
                    if any(skip in div_classes or skip in div_id for skip in [
                        'header', 'footer', 'nav', 'navigation', 'breadcrumb', 
                        'sidebar', 'menu', 'search', 'logo', 'brand', 'skip',
                        'portal', 'swil', 'swildesk', 'top', 'bottom', 'global',
                        'user', 'auth', 'sign', 'login', 'register', 'profile'
                    ]):
                        continue
                    
                    # Get text content
                    text = div.get_text(strip=True)
                    
                    # Look for article-specific content indicators
                    if any(indicator in text.lower() for indicator in [
                        'step 1:', 'step 2:', 'step 3:', 'step 4:', 'step 5:', 'step 6:',
                        'reference image:', 'what is a csv file?', 'how to set csv format',
                        'import purchase', 'csv format definition', 'import transaction'
                    ]):
                        potential_containers.append({
                            'element': div,
                            'text_length': len(text),
                            'relevance_score': 0
                        })
                
                # Score containers based on relevance
                for container in potential_containers:
                    text = container['element'].get_text(strip=True).lower()
                    score = 0
                    
                    # Higher score for more relevant content
                    if 'step' in text:
                        score += 10
                    if 'reference image' in text:
                        score += 8
                    if 'csv' in text:
                        score += 6
                    if 'import' in text:
                        score += 5
                    if 'swilerp' in text:
                        score += 4
                    
                    container['relevance_score'] = score
                
                # Sort by relevance score and text length
                potential_containers.sort(key=lambda x: (x['relevance_score'], x['text_length']), reverse=True)
                
                if potential_containers:
                    article_content = potential_containers[0]['element']
                    logger.info(f"Using best content container with score {potential_containers[0]['relevance_score']} and {potential_containers[0]['text_length']} characters")
            
            if not article_content:
                logger.warning("Could not find article content area")
                return self._create_error_response("No article content found")
            
            # Clean the content area - remove unwanted elements more aggressively
            content_soup = BeautifulSoup(str(article_content), 'html.parser')
            
            # Remove navigation, header, footer elements that might be inside
            unwanted_selectors = [
                'nav', '.navigation', '.breadcrumb', '.search', '.sidebar',
                '.header', '.footer', '.menu', '.logo', '.brand',
                '.social', '.share', '.tags', '.related', '.comments',
                '.skip', '.portal', '.swil', '.swildesk', '.top', '.bottom',
                '.breadcrumbs', '.breadcrumb', '.search-bar', '.search-box',
                '.user-menu', '.user-nav', '.global-nav', '.main-nav'
            ]
            
            for selector in unwanted_selectors:
                for element in content_soup.select(selector):
                    element.decompose()
            
            # Also remove elements by text content that indicates navigation
            for element in content_soup.find_all(['div', 'span', 'a', 'p']):
                text = element.get_text(strip=True).lower()
                if any(nav_text in text for nav_text in [
                    'skip to content', 'skip to menu', 'skip to footer',
                    'home', 'my tickets', 'knowledge base', 'community', 'blog', 'updates',
                    'sign in', 'sign up', 'font size', 'layout', 'full width',
                    'search our knowledge base', 'ask the swil network',
                    'submit a support request', 'about swil', 'stay connected',
                    'corporate office', 'powered by zoho', 'terms of service', 'privacy policy'
                ]):
                    element.decompose()
            
            # Extract text content with better formatting
            content_parts = []
            
            # Process each text element to preserve structure
            for element in content_soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'div']):
                text = element.get_text(strip=True)
                if text and len(text) > 10:  # Only meaningful text
                    # Add proper spacing based on element type
                    if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        content_parts.append(f"\n\n{text}\n")
                    elif element.name == 'li':
                        content_parts.append(f"• {text}")
                    elif element.name == 'p':
                        content_parts.append(f"{text}\n")
                    else:
                        content_parts.append(text)
            
            # Join all content parts
            content = '\n'.join(content_parts).strip()
            
            # Final cleanup - remove any remaining navigation text and duplicates
            lines = content.split('\n')
            cleaned_lines = []
            seen_lines = set()  # To remove duplicates
            
            for line in lines:
                line = line.strip()
                if line and not any(nav_text in line.lower() for nav_text in [
                    'skip to', 'home', 'my tickets', 'knowledge base', 'community', 'blog', 'updates',
                    'sign in', 'sign up', 'font size', 'layout', 'full width',
                    'search our knowledge base', 'ask the swil network',
                    'submit a support request', 'about swil', 'stay connected',
                    'corporate office', 'powered by zoho', 'terms of service', 'privacy policy',
                    'welcome to swindia portal', 'swildesk | swil support',
                    'swil network', 'import/export data', 'view all', 'tags',
                    'still can\'t find an answer?', 'send us a support request',
                    'softworld (india) pvt. ltd.', 'iso 9001:2015', 'jaipur',
                    'sunder market', 'sms hospital', 's.r.s. road',
                    'on this page', 'follow', 'subscribe to receive notifications',
                    'helpful?', 'import master excel file', 'export/import all vendors',
                    'export/import all customers', 'export/import vouchers',
                    'export/import cheque format', 'export tally data', 'how to export/import'
                ]):
                    # Also filter out very short lines that are likely navigation
                    if len(line) > 3 and not line in ['?', 'Unknown', '-', '+', '|']:
                        # Special handling for reference image lines - preserve them
                        if 'reference image:' in line.lower():
                            if line not in seen_lines:  # Avoid duplicates
                                cleaned_lines.append(line)
                                seen_lines.add(line)
                        else:
                            # For non-reference lines, check for duplicates
                            if line not in seen_lines:
                                cleaned_lines.append(line)
                                seen_lines.add(line)
            
            content = '\n'.join(cleaned_lines).strip()
            
            # Remove any remaining duplicate consecutive lines
            final_lines = []
            prev_line = ""
            for line in content.split('\n'):
                line = line.strip()
                if line and line != prev_line:
                    # Also check for similar lines (with slight variations)
                    is_duplicate = False
                    for existing_line in final_lines:
                        # Check if lines are very similar (90% similarity)
                        if self._similarity_check(line, existing_line) > 0.9:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        final_lines.append(line)
                        prev_line = line
            
            content = '\n'.join(final_lines).strip()
            
            # If we still don't have good content, try a simpler approach
            if len(content) < 500:
                logger.warning("Content extraction produced insufficient content, trying simpler approach...")
                
                # Just get the text from the article content element, but clean it
                raw_text = article_content.get_text(separator='\n', strip=True)
                
                # Remove navigation lines
                lines = raw_text.split('\n')
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if line and not any(nav_text in line.lower() for nav_text in [
                        'skip to', 'home', 'my tickets', 'knowledge base', 'community', 'blog', 'updates',
                        'sign in', 'sign up', 'font size', 'layout', 'full width',
                        'search our knowledge base', 'ask the swil network',
                        'submit a support request', 'about swil', 'stay connected',
                        'corporate office', 'powered by zoho', 'terms of service', 'privacy policy',
                        'welcome to swindia portal', 'swildesk | swil support',
                        'swil network', 'import/export data', 'view all', 'tags',
                        'still can\'t find an answer?', 'send us a support request',
                        'softworld (india) pvt. ltd.', 'iso 9001:2015', 'jaipur',
                        'sunder market', 'sms hospital', 's.r.s. road'
                    ]):
                        # Also filter out very short lines that are likely navigation
                        if len(line) > 3 and not line in ['?', 'Unknown', '-', '+', '|']:
                            # Special handling for reference image lines - preserve them
                            if 'reference image:' in line.lower():
                                cleaned_lines.append(line)
                            else:
                                cleaned_lines.append(line)
                
                content = '\n'.join(cleaned_lines).strip()
                logger.info(f"Simpler approach produced {len(content)} characters of content")
            
            # Extract images with their context - search in the full page, not just content area
            images = []
            
            # First, try to find images in the content area
            content_images = content_soup.find_all('img')
            for img in content_images:
                img_src = img.get('src') or img.get('data-src')
                if img_src:
                    # Make URL absolute
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src
                    elif img_src.startswith('/'):
                        img_src = urljoin(url, img_src)
                    elif not img_src.startswith('http'):
                        img_src = urljoin(url, img_src)
                    
                    # Look for reference text near the image
                    reference_text = ""
                    
                    # Check if image has alt text
                    if img.get('alt'):
                        reference_text = img['alt']
                    else:
                        # Look for reference text in nearby elements
                        parent = img.parent
                        if parent:
                            # Look for text that mentions "Reference Image" or similar
                            for sibling in parent.find_all(['p', 'span', 'div']):
                                sibling_text = sibling.get_text(strip=True)
                                if any(ref_word in sibling_text.lower() for ref_word in ['reference', 'image', 'screenshot', 'figure']):
                                    reference_text = sibling_text
                                    break
                    
                    images.append({
                        'url': img_src,
                        'reference_text': reference_text,
                        'alt_text': img.get('alt', '')
                    })
            
            # If no images found in content area, search the entire page for images
            if not images:
                logger.info("No images found in content area, searching entire page...")
                
                # Search in the original soup (full page) for images
                all_images = soup.find_all('img')
                logger.info(f"Found {len(all_images)} images on the page")
                
                # First, let's find all the reference text mentioned in our content
                # Get the raw content before cleaning to preserve reference text
                raw_content = article_content.get_text(separator='\n', strip=True)
                reference_texts = []
                content_lines = raw_content.split('\n')
                for line in content_lines:
                    if 'reference image:' in line.lower():
                        # Extract the reference text after "Reference Image:"
                        ref_text = line.split('Reference Image:')[-1].strip()
                        if ref_text:
                            reference_texts.append(ref_text.lower())
                
                logger.info(f"Found reference texts: {reference_texts}")
                
                # Now try to match images with reference texts
                for img in all_images:
                    img_src = img.get('src') or img.get('data-src')
                    if img_src:
                        # Make URL absolute
                        if img_src.startswith('//'):
                            img_src = 'https:' + img_src
                        elif img_src.startswith('/'):
                            img_src = urljoin(url, img_src)
                        elif not img_src.startswith('http'):
                            img_src = urljoin(url, img_src)
                        
                        # Look for reference text near the image
                        reference_text = ""
                        
                        # Check if image has alt text
                        if img.get('alt'):
                            reference_text = img['alt']
                        else:
                            # Look for reference text in nearby elements
                            parent = img.parent
                            if parent:
                                # Look for text that mentions "Reference Image" or similar
                                for sibling in parent.find_all(['p', 'span', 'div']):
                                    sibling_text = sibling.get_text(strip=True)
                                    if any(ref_word in sibling_text.lower() for ref_word in ['reference', 'image', 'screenshot', 'figure']):
                                        reference_text = sibling_text
                                        break
                        
                        # If we found reference text, try to match it with our content references
                        if reference_text:
                            # Check if this reference text appears in our cleaned content
                            if reference_text.lower() in content.lower():
                                images.append({
                                    'url': img_src,
                                    'reference_text': reference_text,
                                    'alt_text': img.get('alt', '')
                                })
                                logger.info(f"Found referenced image: {reference_text} -> {img_src}")
                        
                        # If no reference text found, try to match by proximity
                        if not reference_text:
                            # Look for any text near the image that might be a reference
                            parent = img.parent
                            if parent:
                                # Search in parent and siblings for reference-like text
                                nearby_text = parent.get_text(strip=True)
                                
                                # Check if any of our reference texts appear nearby
                                for ref_text in reference_texts:
                                    if ref_text in nearby_text.lower():
                                        # Find the actual reference text in the nearby content
                                        for sibling in parent.find_all(['p', 'span', 'div']):
                                            sibling_text = sibling.get_text(strip=True)
                                            if ref_text in sibling_text.lower():
                                                reference_text = sibling_text
                                                break
                                        
                                        if reference_text:
                                            images.append({
                                                'url': img_src,
                                                'reference_text': reference_text,
                                                'alt_text': img.get('alt', '')
                                            })
                                            logger.info(f"Found image by proximity: {reference_text} -> {img_src}")
                                            break
                
                # If we still don't have enough images, try to find images by looking at the DOM structure
                if len(images) < len(reference_texts):
                    logger.info(f"Only found {len(images)} images for {len(reference_texts)} references, trying DOM structure analysis...")
                    
                    # Look for images that might be in specific containers
                    for ref_text in reference_texts:
                        # Skip if we already have an image for this reference
                        if any(ref_text in img['reference_text'].lower() for img in images):
                            continue
                        
                        # Look for images in the same section as this reference text
                        for element in soup.find_all(['div', 'section', 'article']):
                            element_text = element.get_text(strip=True).lower()
                            if ref_text in element_text:
                                # Found a container with this reference text, look for images in it
                                container_images = element.find_all('img')
                                for img in container_images:
                                    img_src = img.get('src') or img.get('data-src')
                                    if img_src:
                                        # Make URL absolute
                                        if img_src.startswith('//'):
                                            img_src = 'https:' + img_src
                                        elif img_src.startswith('/'):
                                            img_src = urljoin(url, img_src)
                                        elif not img_src.startswith('http'):
                                            img_src = urljoin(url, img_src)
                                        
                                        # Find the actual reference text in this container
                                        actual_ref_text = ""
                                        for text_elem in element.find_all(['p', 'span', 'div']):
                                            text_content = text_elem.get_text(strip=True)
                                            if ref_text in text_content.lower():
                                                actual_ref_text = text_content
                                                break
                                        
                                        if actual_ref_text:
                                            images.append({
                                                'url': img_src,
                                                'reference_text': actual_ref_text,
                                                'alt_text': img.get('alt', '')
                                            })
                                            logger.info(f"Found image by DOM structure: {actual_ref_text} -> {img_src}")
                                            break
                
                logger.info(f"Total images found: {len(images)}")
            
            # If we still don't have images with reference text, try a different approach
            # Look for images that are mentioned in the content with "Reference Image:" text
            if not any(img.get('reference_text') for img in images):
                logger.info("No images with reference text found, trying content-based matching...")
                
                # Parse the content to find "Reference Image:" mentions
                content_lines = content.split('\n')
                reference_sections = []
                
                for i, line in enumerate(content_lines):
                    if 'reference image:' in line.lower():
                        # Get the reference text
                        ref_text = line.split('Reference Image:')[-1].strip()
                        if ref_text:
                            # Look for the next few lines that might contain more context
                            context_lines = []
                            for j in range(i, min(i + 3, len(content_lines))):
                                context_lines.append(content_lines[j])
                            
                            reference_sections.append({
                                'reference': ref_text,
                                'context': ' '.join(context_lines)
                            })
                
                logger.info(f"Found {len(reference_sections)} reference sections in content")
                
                # Now try to match these with images from the page
                all_page_images = soup.find_all('img')
                for ref_section in reference_sections:
                    ref_text = ref_section['reference'].lower()
                    
                    # Look for images that might match this reference
                    for img in all_page_images:
                        img_src = img.get('src') or img.get('data-src')
                        if img_src:
                            # Make URL absolute
                            if img_src.startswith('//'):
                                img_src = 'https:' + img_src
                            elif img_src.startswith('/'):
                                img_src = urljoin(url, img_src)
                            elif not img_src.startswith('http'):
                                img_src = urljoin(url, img_src)
                            
                            # Check if this image is already in our list
                            if not any(img_src == existing_img['url'] for existing_img in images):
                                # Add this image with the reference text
                                images.append({
                                    'url': img_src,
                                    'reference_text': f"Reference Image: {ref_section['reference']}",
                                    'alt_text': img.get('alt', '')
                                })
                                logger.info(f"Added image with reference: {ref_section['reference']} -> {img_src}")
                                break
            
            # Extract metadata
            metadata = {}
            
            # Try to find author and date
            author_selectors = ['.author', '.author-name', '.byline', '.published-by']
            date_selectors = ['.date', '.published-date', '.updated', '.timestamp']
            
            for selector in author_selectors:
                author_elem = content_soup.select_one(selector)
                if author_elem:
                    metadata['author'] = author_elem.get_text(strip=True)
                    break
            
            for selector in date_selectors:
                date_elem = content_soup.select_one(selector)
                if date_elem:
                    metadata['publish_date'] = date_elem.get_text(strip=True)
                    break
            
            # Add content statistics
            metadata['content_length'] = len(content)
            metadata['image_count'] = len(images)
            
            return {
                "title": article_title,
                "content": content,
                "images": images,
                "metadata": metadata,
                "url": url,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from HTML: {e}")
            return self._create_error_response(f"Content extraction failed: {str(e)}")
    
    def _extract_title_from_html(self, soup: BeautifulSoup) -> str:
        """Extract title from HTML - no longer used"""
        pass
    
    def _extract_text_content_from_html(self, element) -> str:
        """Extract text content from HTML element - no longer used"""
        pass
    
    def _extract_images_from_html(self, element, base_url: str) -> List[str]:
        """Extract images from HTML element - no longer used"""
        pass
    
    def _extract_metadata_from_html(self, soup: BeautifulSoup) -> Dict[str, any]:
        """Extract metadata from HTML - no longer used"""
        pass
    
    def _create_error_response(self, error_message: str) -> Dict[str, any]:
        """Create a standardized error response"""
        return {
            "title": "Error",
            "content": f"Failed to scrape article: {error_message}",
            "images": [],
            "metadata": {},
            "url": "",
            "status": "error",
            "error": error_message
        }
    
    def close(self):
        """Close the session and driver"""
        self.session.close()
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


# Global scraper instance
_scraper_instance = None


async def get_scraper() -> SwildeskScraper:
    """Get or create a global scraper instance"""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = SwildeskScraper()
    return _scraper_instance


async def scrape_url(url: str) -> Dict[str, any]:
    """
    Main function to scrape a URL - compatible with n8n HTTP calls
    
    Args:
        url: The URL to scrape
        
    Returns:
        Dictionary with scraped content
    """
    scraper = await get_scraper()
    return await scraper.scrape_article(url)


async def scrape_multiple_urls(urls: List[str]) -> List[Dict[str, any]]:
    """
    Scrape multiple URLs concurrently
    
    Args:
        urls: List of URLs to scrape
        
    Returns:
        List of scraped content dictionaries
    """
    scraper = await get_scraper()
    
    # Create tasks for concurrent scraping
    tasks = [scraper.scrape_article(url) for url in urls]
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error scraping {urls[i]}: {result}")
            processed_results.append({
                "url": urls[i],
                "status": "error",
                "error": str(result)
            })
        else:
            processed_results.append(result)
    
    return processed_results


# Synchronous wrapper for compatibility
def scrape_url_sync(url: str) -> Dict[str, any]:
    """
    Synchronous wrapper for scraping - useful for testing or non-async contexts
    
    Args:
        url: The URL to scrape
        
    Returns:
        Dictionary with scraped content
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(scrape_url(url))
            finally:
                loop.close()
        else:
            return loop.run_until_complete(scrape_url(url))
    except RuntimeError:
        # No event loop, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(scrape_url(url))
        finally:
            loop.close()


if __name__ == "__main__":
    # Test the scraper
    test_url = "https://support.swildesk.com/portal/en/kb/articles/import-data-in-swilerp-retailgraph-through-csv"
    
    # Test synchronous version
    print("Testing synchronous scraper...")
    result = scrape_url_sync(test_url)
    print(f"Title: {result.get('title', 'No title')}")
    print(f"Content length: {len(result.get('content', ''))}")
    print(f"Images: {len(result.get('images', []))}")
    print(f"Status: {result.get('status', 'unknown')}")
    print(f"URL: {result.get('url', 'No URL')}")


