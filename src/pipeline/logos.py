"""Official logo discovery: scrape the entity's own official page for an icon
first (best match), verify it's really an image, and fall back to Google's
public favicon service (unofficial but free, no key, confirmed working as of
2026 -- see README) if scraping fails or finds nothing."""
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

_TIMEOUT = 8
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIOrbitPipeline/1.0)"}


def _is_real_image(url: str) -> bool:
    try:
        r = requests.head(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        ctype = r.headers.get("Content-Type", "")
        clen = int(r.headers.get("Content-Length", "0") or 0)
        return ctype.startswith("image/") and (clen == 0 or clen > 300)
    except requests.RequestException:
        return False


def find_logo(official_url: str) -> str:
    if not official_url:
        return ""
    domain = urlparse(official_url).netloc

    try:
        resp = requests.get(official_url, headers=_HEADERS, timeout=_TIMEOUT)
        soup = BeautifulSoup(resp.text, "html.parser")
        candidates = [
            soup.find("link", attrs={"rel": lambda v: v and "apple-touch-icon" in v}),
            soup.find("link", attrs={"rel": lambda v: v and "icon" in v}),
            soup.find("meta", attrs={"property": "og:image"}),
        ]
        for tag in candidates:
            if not tag:
                continue
            href = tag.get("href") or tag.get("content")
            if not href:
                continue
            candidate_url = urljoin(official_url, href)
            if _is_real_image(candidate_url):
                return candidate_url
    except requests.RequestException:
        pass

    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
