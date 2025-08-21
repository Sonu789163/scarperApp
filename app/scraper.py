from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup
from newspaper import Article
try:
    from markdownify import markdownify as md
except Exception:  # optional
    md = None
from playwright.async_api import async_playwright


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

        # Wait for common content selectors if available
        selectors = [
            "#article_TOC", "#articelDetail",
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
    images = sorted({img.get("src", "") for img in main_el.select("img[src]") if img.get("src")})

    content_md = md(content_html) if md else None

    return article.title or "", content_text, images if images else [], content_html, content_md


async def scrape_url(url: str, headless: bool = True) -> dict:
    base_url = url.split("#", 1)[0]
    html, final_url = await fetch_html_with_js(base_url, headless=headless)
    title, text, images, content_html, content_md = clean_and_extract_main_content(html, final_url)
    return {"title": title, "text": text, "images": images, "html": content_html, "markdown": content_md}


