"""Official logo discovery for an entity's official page. We verify image type,
response reachability, content length, and a matching same-domain origin. If the
official image cannot be proven, the logo field remains empty rather than being
filled by a third-party aggregator or a Google favicon service fallback."""
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

_TIMEOUT = 8
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIOrbitPipeline/1.0)"}


def _image_content_type_ok(headers):
    ctype = headers.get("Content-Type", "") or ""
    return ctype.lower().startswith("image/")


def _is_real_image(url: str, official_url: str = "") -> bool:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return False
        ctype = resp.headers.get("Content-Type", "") or ""
        if not ctype.lower().startswith("image/"):
            return False
        clen = int(resp.headers.get("Content-Length", "0") or 0)
        if clen and clen <= 300:
            return False
        # Domain safety: only accept URLs where the image host is the same domain
        # or an explicitly trusted same-domain asset path.
        if official_url:
            img_host = urlparse(url).netloc.lower()
            official_host = urlparse(official_url).netloc.lower()
            if img_host and img_host != official_host:
                # Allow a same-site path on a subdomain of the official site.
                if img_host.endswith("." + official_host) or official_host.endswith("." + img_host):
                    pass
                else:
                    return False
        return True
    except requests.RequestException:
        return False


def find_logo(official_url: str) -> str:
    if not official_url:
        return ""
    try:
        resp = requests.get(official_url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        # Priority: canonical rel values found in HTML.
        candidates = []
        for tag in soup.find_all("link"):
            rel = tag.get("rel") or []
            if isinstance(rel, str):
                rel_values = [rel]
            else:
                rel_values = rel
            rel_values = [str(x).lower() for x in rel_values]
            # explicit icon family; exclude data URIs and obvious external aggregator URLs.
            if any(x in {"icon", "shortcut icon", "apple-touch-icon", "apple-touch-icon-precomposed"} for x in rel_values):
                href = tag.get("href") or tag.get("content") or ""
                if href:
                    candidates.append(href)
        # Add Open Graph image and Twitter image if present.
        meta_og = soup.find("meta", attrs={"property": "og:image"})
        if meta_og:
            candidates.append(meta_og.get("content") or "")
        meta_tw = soup.find("meta", attrs={"name": "twitter:image"})
        if meta_tw:
            candidates.append(meta_tw.get("content") or "")

        for href in candidates:
            if not href:
                continue
            # ignore data and external aggregator URLs
            if href.startswith("data:"):
                continue
            cand = urljoin(official_url, href)
            # normalize markers from the known official host only.
            if _is_real_image(cand, official_url):
                return cand
    except requests.RequestException:
        return ""
    except Exception:
        return ""

    return ""
