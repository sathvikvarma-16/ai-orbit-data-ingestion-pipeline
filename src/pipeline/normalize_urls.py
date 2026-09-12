"""URL normalization: consistent scheme, tracking-param stripping, domain canonicalization, and a deterministic official-URL form."""
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid",
    "mkt_tok", "hsa_cam", "hsa_grp", "hsa_ad", "hsa_src",
}

SPECIAL_HOSTS = {
    "github.com": "github.com",
    "www.github.com": "github.com",
    "huggingface.co": "huggingface.co",
    "www.huggingface.co": "huggingface.co",
    "youtube.com": "youtube.com",
    "www.youtube.com": "youtube.com",
}


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    scheme = "https"
    netloc = parsed.netloc.lower().strip()
    # Normalize common public host variants to their canonical public host.
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # Remove default ports and common anonymous caller noise.
    if ":443" in netloc:
        netloc = netloc.replace(":443", "")
    if ":80" in netloc:
        netloc = netloc.replace(":80", "")
    # Remove any empty host path artifacts.
    netloc = netloc.rstrip("/")

    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS]
    path = parsed.path.rstrip("/") if parsed.path != "/" else ""
    new = parsed._replace(
        scheme=scheme,
        netloc=netloc,
        path=path,
        query=urlencode(query, doseq=True),
        fragment="",
    )
    return urlunparse(new)
