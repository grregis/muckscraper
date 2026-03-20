# news_fetcher/scraper.py

import requests
from bs4 import BeautifulSoup
import bleach
import time
import os
import logging
logger = logging.getLogger(__name__)

HEADERS_DEFAULT = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

HEADERS_GOOGLEBOT = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
}

ALLOWED_TAGS = [
    "p", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "b", "i", "u",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
]

ALLOWED_ATTRIBUTES = {
    "a":   ["href", "title"],
    "img": ["src", "alt", "title"],
    "td":  ["colspan", "rowspan"],
    "th":  ["colspan", "rowspan"],
}

# Sites that need Playwright (heavy JS)
PLAYWRIGHT_DOMAINS = [
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "nytimes.com",
    "washingtonpost.com",
    "theathletic.com",
    "wired.com",
]

# Sites to try Googlebot user agent on
GOOGLEBOT_DOMAINS = [
    "axios.com",
    "politico.com",
    "theatlantic.com",
    "thedailybeast.com",
    "businessinsider.com",
    "sfgate.com",
]

# Sites to skip entirely
SKIP_DOMAINS = [
    "youtube.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
]


def should_skip(url):
    return any(domain in url.lower() for domain in SKIP_DOMAINS)


def needs_playwright(url):
    return any(domain in url.lower() for domain in PLAYWRIGHT_DOMAINS)


def use_googlebot(url):
    return any(domain in url.lower() for domain in GOOGLEBOT_DOMAINS)


def sanitize_html(raw_html):
    return bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )


def extract_with_readability(html, url):
    """
    Use Mozilla's readability algorithm to extract main article content.
    Returns sanitized HTML or None.
    """
    try:
        from readability import Document
        doc = Document(html)
        content = doc.summary()
        if content and len(content) > 200:
            sanitized = sanitize_html(content)
            if len(sanitized) > 200:
                logger.info(f"  [Readability] Extracted {len(sanitized)} chars from {url[:60]}")
                return sanitized
    except Exception as e:
        logger.info(f"  [Readability] Error: {e}")
    return None


def extract_article_html_bs4(url, headers=None):
    """
    Scrape article using BS4 and return sanitized HTML string.
    Falls back to readability if direct extraction fails.
    """
    if headers is None:
        headers = HEADERS_DEFAULT
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text

        # Try readability first — it's smarter than manual selectors
        content = extract_with_readability(html, url)
        if content:
            return content

        # Fall back to manual BS4 extraction
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "advertisement", "figure", "figcaption",
                         "iframe", "noscript", "button", "form"]):
            tag.decompose()

        content_html = None

        article = soup.find("article")
        if article:
            content_html = str(article)

        if not content_html or len(content_html) < 200:
            for selector in [
                {"class": "article-body"},
                {"class": "article-content"},
                {"class": "story-body"},
                {"class": "story-content"},
                {"class": "post-content"},
                {"class": "entry-content"},
                {"class": "content-body"},
                {"id": "article-body"},
                {"id": "story-body"},
                {"itemprop": "articleBody"},
                {"class": "body-text"},
            ]:
                found = soup.find(["div", "section"], selector)
                if found and len(found.get_text(strip=True)) > 200:
                    content_html = str(found)
                    break

        if not content_html or len(content_html) < 200:
            paragraphs = soup.find_all("p")
            if paragraphs:
                combined = "".join(str(p) for p in paragraphs)
                if len(combined) > 200:
                    content_html = f"<div>{combined}</div>"

        if content_html and len(content_html) > 200:
            sanitized = sanitize_html(content_html)
            logger.info(f"  [BS4] Scraped {len(sanitized)} chars from {url[:60]}")
            return sanitized

        logger.info(f"  [BS4] Could not extract sufficient content from {url[:60]}")
        return None

    except Exception as e:
        logger.info(f"  [BS4] Error scraping {url[:60]}: {e}")
        return None


def extract_article_html_playwright(url):
    """
    Scrape article using Playwright and return sanitized HTML string.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers(HEADERS_DEFAULT)

            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            time.sleep(2)

            page.evaluate("""
                ['script','style','nav','header','footer','aside',
                 'iframe','button','form']
                .forEach(tag => document.querySelectorAll(tag)
                .forEach(el => el.remove()))
            """)

            html = page.content()
            browser.close()

            # Try readability on the rendered HTML first
            content = extract_with_readability(html, url)
            if content:
                return content

            # Fall back to manual extraction
            content_html = page.evaluate("""
                () => {
                    const article = document.querySelector('article');
                    if (article) return article.innerHTML;

                    const selectors = [
                        '.article-body', '.article-content', '.story-body',
                        '.post-content', '.entry-content',
                        '[itemprop="articleBody"]'
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.innerText.length > 200) return el.innerHTML;
                    }

                    const paras = Array.from(document.querySelectorAll('p'));
                    return '<div>' + paras.map(p => p.outerHTML).join('') + '</div>';
                }
            """) if False else None  # page already closed, use html from above

            if content_html and len(content_html) > 200:
                sanitized = sanitize_html(content_html)
                logger.info(f"  [Playwright] Scraped {len(sanitized)} chars from {url[:60]}")
                return sanitized

            logger.info(f"  [Playwright] Could not extract content from {url[:60]}")
            return None

    except ImportError:
        logger.info("  [Playwright] Not installed, skipping.")
        return None
    except Exception as e:
        logger.info(f"  [Playwright] Error scraping {url[:60]}: {e}")
        return None


def try_archive_fallback(url):
    """
    Try to fetch article from archive.ph as a paywall fallback.
    Returns sanitized HTML or None.
    """
    archive_url = f"https://archive.ph/{url}"
    logger.info(f"  [Archive] Trying archive.ph for {url[:60]}")
    try:
        response = requests.get(archive_url, headers=HEADERS_DEFAULT, timeout=15)
        if response.status_code == 200:
            content = extract_with_readability(response.text, archive_url)
            if content:
                logger.info(f"  [Archive] Successfully extracted from archive.ph")
                return content
    except Exception as e:
        logger.info(f"  [Archive] Error: {e}")
    return None


def scrape_article(url):
    """
    Main entry point. Strategy:
    1. Skip social/video domains entirely
    2. For Playwright domains — use Playwright, fall back to archive.ph
    3. For Googlebot domains — try Googlebot UA first
    4. For everything else — try BS4 (with readability), fall back to Playwright, then archive.ph
    Returns sanitized HTML or None.
    """
    if should_skip(url):
        logger.info(f"  [Scraper] Skipping {url[:60]}")
        return None

    # Playwright-first domains
    if needs_playwright(url):
        logger.info(f"  [Scraper] Using Playwright for {url[:60]}")
        content = extract_article_html_playwright(url)
        if not content:
            content = try_archive_fallback(url)
        return content

    # Googlebot user agent domains
    if use_googlebot(url):
        logger.info(f"  [Scraper] Using Googlebot UA for {url[:60]}")
        content = extract_article_html_bs4(url, headers=HEADERS_GOOGLEBOT)
        if not content:
            content = extract_article_html_bs4(url, headers=HEADERS_DEFAULT)
        if not content:
            content = try_archive_fallback(url)
        return content

    # Default: BS4 with readability → Playwright → archive.ph
    content = extract_article_html_bs4(url)
    if not content:
        logger.info(f"  [Scraper] BS4 failed, trying Playwright for {url[:60]}")
        content = extract_article_html_playwright(url)
    if not content:
        content = try_archive_fallback(url)
    return content