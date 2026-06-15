import requests
from bs4 import BeautifulSoup

from .security import is_safe_url


def crawl(url: str) -> dict:
    """Static crawl via requests. SPA crawling handled by celery_studio_playwright (D2)."""
    if not is_safe_url(url):
        raise ValueError('Небезопасный URL (SSRF)')
    r = requests.get(url, timeout=15, headers={'User-Agent': 'aineron-studio-bot'})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    return {
        'html': r.text,
        'title': (soup.title.string if soup.title else ''),
        'text': soup.get_text(separator='\n', strip=True)[:20000],
        'css_links': [link.get('href') for link in soup.find_all('link', rel='stylesheet')],
    }


def crawl_spa(url: str) -> dict:
    """Full JS-rendered crawl via Playwright (prefork worker only, never in gevent)."""
    if not is_safe_url(url):
        raise ValueError('Небезопасный URL (SSRF)')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        page = browser.new_page()
        page.goto(url, timeout=30000, wait_until='networkidle')
        html = page.content()
        title = page.title()
        text = page.evaluate('() => document.body ? document.body.innerText : ""')
        browser.close()
    soup = BeautifulSoup(html, 'html.parser')
    return {
        'html': html,
        'title': title,
        'text': str(text)[:20000],
        'css_links': [link.get('href') for link in soup.find_all('link', rel='stylesheet')],
    }
