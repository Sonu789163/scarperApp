from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup
from newspaper import Article
try:
    from markdownify import markdownify as md
except Exception:  # optional
    md = None
from playwright.async_api import async_playwright
import httpx


async def fetch_html_with_js(url: str, wait_until: str = "networkidle", timeout_ms: int = 30000, headless: bool = True) -> tuple[str, str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ])
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="UTC",
            java_script_enabled=True,
            bypass_csp=True,
        )
        # Stealth-ish tweaks
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        """)

        page = await context.new_page()
        await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        # Nudge dynamic loading
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500)

        # Wait for common content selectors if available
        selectors = [
            "#article_TOC", "#articelDetail", ".ArticleDetail_description", ".KbDetailLtContainer__description",
            "main article", "article", "#content", ".entry-content", ".post-content", ".kb-article", ".kb-article__content",
        ]
        found = False
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=5000)
                found = True
                break
            except Exception:
                continue

        if not found:
            # Small grace period for late JS
            await page.wait_for_timeout(2000)

        html = await page.content()
        final_url = page.url
        await browser.close()
        return html, final_url


async def fetch_html_raw(url: str, timeout_s: int = 20) -> tuple[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(timeout=timeout_s, headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text, str(resp.url)


def clean_and_extract_main_content(html: str, base_url: str) -> tuple[str, str, list[str], str, str | None]:
    article = Article(base_url)
    article.set_html(html)
    article.parse()

    soup = BeautifulSoup(html, "lxml")

    # Remove non-content areas
    cleanup_selectors = [
        "header", "footer", "nav", "aside",
        '[role="banner"]', '[role="navigation"]', '[role="contentinfo"]',
        ".breadcrumbs", ".breadcrumb", '[class*="breadcrumb"]',
        ".toc", ".table-of-contents", '[class*="toc"]', '#toc',
        ".menu", ".nav", '[class*="menu"]', '[class*="nav"]',
        ".sidebar", ".right-sidebar",
        '[class*="sidebar"]', '[id*="sidebar"]', '[class*="aside"]', '[id*="aside"]',
        '[class*="rail"]', '[id*="rail"]',
        ".ads", ".advertisement", '[class*="ad-"]', '[class*="ads"]', '[id*="ads"]',
        '[class*="cookie"]', '[id*="cookie"]', '[class*="share"]', '[id*="share"]',
    ]
    for selector in cleanup_selectors:
        for el in soup.select(selector):
            el.decompose()

    for el in soup.select("script, style, noscript"):
        el.decompose()

    # Absolutize links
    for tag in soup.select("img[src]"):
        src = tag.get("src", "")
        if src:
            tag["src"] = urljoin(base_url, src)
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if href:
            a["href"] = urljoin(base_url, href)

    # Candidate selection
    candidate_selectors = [
        "#article_TOC", "#articelDetail",
        "main article", "main .article", "main .entry-content", "main .post-content", "main",
        "#main", "#primary", "#content article", "#content",
        ".content article", "article", ".article", ".entry-content", ".post-content",
        "#article", ".kb-article", ".kb-article__content", ".post",
    ]
    candidates = [soup.select_one(sel) for sel in candidate_selectors]
    candidates = [el for el in candidates if el is not None]
    if not candidates:
        candidates = [soup.body or soup]

    def text_len(node) -> int:
        return len(node.get_text(" ", strip=True))

    main_el = max(candidates, key=text_len)
    content_html = str(main_el)
    content_text = main_el.get_text("\n", strip=True)

    # Fallback: pick densest text container if extraction is too small
    if len(content_text) < 80:
        alt_candidates = soup.select(
            "main, article, section, div#article_TOC, div#articelDetail, div.description, .ArticleDetail_description, .KbDetailLtContainer__description"
        )
        alt_candidates = [el for el in alt_candidates if el is not None]
        if alt_candidates:
            main_el = max(alt_candidates, key=text_len)
            content_html = str(main_el)
            content_text = main_el.get_text("\n", strip=True)
    
    images = sorted({img.get("src", "") for img in main_el.select("img[src]") if img.get("src")})

    content_md = md(content_html) if md else None

    return article.title or "", content_text, images if images else [], content_html, content_md


def enhance_text_with_inline_images(text: str, images: list[str]) -> str:
    """
    Enhance text by including image links inline where "Reference Image:" appears.
    This function will replace "Reference Image:" with "Reference Image: [IMAGE_LINK]"
    """
    if not images:
        return text
    
    enhanced_text = text
    image_index = 0
    
    # Find all occurrences of "Reference Image:" and replace with image links
    while "Reference Image:" in enhanced_text and image_index < len(images):
        # Find the position of "Reference Image:"
        ref_pos = enhanced_text.find("Reference Image:")
        
        # Find the end of the current sentence or line
        end_pos = enhanced_text.find("\n", ref_pos)
        if end_pos == -1:
            end_pos = len(enhanced_text)
        
        # Insert the image link after "Reference Image:"
        insert_pos = ref_pos + len("Reference Image:")
        image_link = f" [{images[image_index]}]"
        
        enhanced_text = (
            enhanced_text[:insert_pos] + 
            image_link + 
            enhanced_text[insert_pos:]
        )
        
        # Move to next image for next occurrence
        image_index += 1
    
    return enhanced_text


async def scrape_url(url: str, headless: bool = True) -> dict:
    base_url = url.split("#", 1)[0]
    html, final_url = await fetch_html_with_js(base_url, headless=headless)
    title, text, images, content_html, content_md = clean_and_extract_main_content(html, final_url)
    if not text and not images:
        raw_html, raw_final_url = await fetch_html_raw(base_url)
        title, text, images, content_html, content_md = clean_and_extract_main_content(raw_html, raw_final_url)
    
    # Enhance text with inline image links
    enhanced_text = enhance_text_with_inline_images(text, images)
    
    return {
        "title": title, 
        "text": enhanced_text, 
        "images": images, 
        "html": content_html, 
        "markdown": content_md
    }


