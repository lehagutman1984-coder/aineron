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
