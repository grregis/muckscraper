# news_fetcher/scraper.py

import requests
from bs4 import BeautifulSoup
import bleach
import time
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Tags and attributes we allow through sanitization
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

PLAYWRIGHT_DOMAINS = [
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "nytimes.com",
    "washingtonpost.com",
    "theathletic.com",
    "wired.com",
]

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


def sanitize_html(raw_html):
    """Strip dangerous tags/attributes but keep formatting."""
    return bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )


def extract_article_html_bs4(url):
    """
    Scrape article using BS4 and return sanitized HTML string.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove junk elements
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "advertisement", "figure", "figcaption",
                         "iframe", "noscript", "button", "form"]):
            tag.decompose()

        content_html = None

        # 1. Try <article> tag
        article = soup.find("article")
        if article:
            content_html = str(article)

        # 2. Try common content containers
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

        # 3. Fall back to wrapping all <p> tags
        if not content_html or len(content_html) < 200:
            paragraphs = soup.find_all("p")
            if paragraphs:
                combined = "".join(str(p) for p in paragraphs)
                if len(combined) > 200:
                    content_html = f"<div>{combined}</div>"

        if content_html and len(content_html) > 200:
            sanitized = sanitize_html(content_html)
            print(f"  [BS4] Scraped {len(sanitized)} chars from {url[:60]}")
            return sanitized

        print(f"  [BS4] Could not extract sufficient content from {url[:60]}")
        return None

    except Exception as e:
        print(f"  [BS4] Error scraping {url[:60]}: {e}")
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
            page.set_extra_http_headers(HEADERS)

            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            time.sleep(2)

            # Remove junk elements
            page.evaluate("""
                ['script','style','nav','header','footer','aside',
                 'iframe','button','form']
                .forEach(tag => document.querySelectorAll(tag)
                .forEach(el => el.remove()))
            """)

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

                    // Fall back to all paragraphs
                    const paras = Array.from(document.querySelectorAll('p'));
                    return '<div>' + paras.map(p => p.outerHTML).join('') + '</div>';
                }
            """)

            browser.close()

            if content_html and len(content_html) > 200:
                sanitized = sanitize_html(content_html)
                print(f"  [Playwright] Scraped {len(sanitized)} chars from {url[:60]}")
                return sanitized

            print(f"  [Playwright] Could not extract content from {url[:60]}")
            return None

    except ImportError:
        print("  [Playwright] Not installed, skipping.")
        return None
    except Exception as e:
        print(f"  [Playwright] Error scraping {url[:60]}: {e}")
        return None


def scrape_article(url):
    """
    Main entry point. Try BS4 first, fall back to Playwright.
    Returns sanitized HTML string or None.
    """
    if should_skip(url):
        print(f"  [Scraper] Skipping {url[:60]}")
        return None

    if needs_playwright(url):
        print(f"  [Scraper] Using Playwright for {url[:60]}")
        return extract_article_html_playwright(url)

    content = extract_article_html_bs4(url)

    if not content:
        print(f"  [Scraper] BS4 failed, trying Playwright for {url[:60]}")
        content = extract_article_html_playwright(url)

    return content