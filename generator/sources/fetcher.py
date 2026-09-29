"""공식문서 fetch + robots.txt 준수 + 본문 텍스트 추출."""

from __future__ import annotations

import ipaddress
import posixpath
import re
import socket
import time
from urllib.parse import unquote, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

_robots_cache: dict[str, RobotFileParser | None] = {}

_SKIP_PATHS = frozenset(
    "account accounts auth login logout signup register search blog blogs news events "
    "download downloads releases changelog community pricing support about contact "
    "privacy terms assets static images img css js index index.html index.htm _index.md "
    "index.md readme.md readme contributing.md license sitemap.xml".split()
)
_ALLOWED_DOCUMENT_EXTENSIONS = {"", ".html", ".htm", ".md", ".txt"}


def public_document_url(url: str) -> bool:
    """Conservative URL syntax check for links, without making DNS requests."""
    if (
        not isinstance(url, str)
        or len(url) > 2000
        or any(char.isspace() for char in url)
    ):
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.params
            or port not in {None, 80 if parsed.scheme == "http" else 443}
            or "\\" in url
            or "%" in parsed.netloc
            or "%" in parsed.path
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal", ".invalid", ".test"))
            or "." not in host
        ):
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            # Numeric pseudo-hosts (2130706433, 127.1, octal forms) are not docs.
            if re.fullmatch(r"[0-9.]+", host):
                return False
        else:
            if not address.is_global:
                return False
    except ValueError:
        return False
    return True


def _detail_url(url: str) -> bool:
    if not public_document_url(url):
        return False
    path = unquote(urlparse(url).path).lower().rstrip("/")
    parts = [part for part in path.split("/") if part]
    if not parts or any(part in _SKIP_PATHS for part in parts):
        return False
    if parts[-1] in {"docs", "documentation", "reference", "concepts", "guides"}:
        return False
    return posixpath.splitext(parts[-1])[1] in _ALLOWED_DOCUMENT_EXTENSIONS


def _without_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def _raw_relative_pair(source: dict, href: str) -> dict | None:
    """Resolve only raw .md paths whose published path mapping is provable.

    Custom slugs, fixed cite URLs, MDX, reference links and generator shortcodes
    are intentionally unsupported; never guess their published URLs.
    """
    raw, cite = urlparse(source["fetch"]), urlparse(source["cite"])
    link = urlparse(href)
    if (
        raw.hostname != "raw.githubusercontent.com"
        or link.scheme
        or link.netloc
        or link.path.startswith("/")
        or not link.path.endswith(".md")
        or link.query
        or "%" in link.path
        or "\\" in link.path
    ):
        return None
    pieces = raw.path.strip("/").split("/")
    if len(pieces) < 4 or not raw.path.endswith(".md"):
        return None
    source_path = raw.path[:-3]
    if source_path.endswith(("/_index", "/index")):
        source_path = source_path.rsplit("/", 1)[0]
    cite_path = cite.path.rstrip("/")
    if not cite_path or not source_path.endswith(cite_path):
        return None
    raw_root = source_path[: -len(cite_path)]
    # At minimum owner/repo/ref must stay fixed, even if paths happen to match.
    if len(raw_root.strip("/").split("/")) < 3:
        return None
    target = urlparse(urljoin(source["fetch"], href))
    if not target.path.startswith(raw_root + "/"):
        return None
    published = target.path[len(raw_root) : -3]
    if published.endswith(("/_index", "/index")):
        published = published.rsplit("/", 1)[0]
    if cite.path.endswith("/"):
        published += "/"
    return {
        "fetch": _without_fragment(target.geturl()),
        "cite": urlunparse(cite._replace(path=published, fragment="")),
    }


def _related_pair(source: dict, href: str) -> dict | None:
    if not isinstance(href, str) or not href.strip() or href.startswith("#"):
        return None
    if not public_document_url(source["cite"]):
        return None
    raw_source = urlparse(source["fetch"]).hostname == "raw.githubusercontent.com"
    if raw_source and not urlparse(href).scheme and not href.startswith("/"):
        pair = _raw_relative_pair(source, href)
        if pair is None:
            return None
    else:
        target = _without_fragment(urljoin(source["cite"], href))
        pair = {"fetch": target, "cite": target}
    if (
        not _detail_url(pair["cite"])
        or not public_document_url(pair["fetch"])
        or urlparse(pair["cite"]).hostname != urlparse(source["cite"]).hostname
        or pair["cite"].rstrip("/") == _without_fragment(source["cite"]).rstrip("/")
    ):
        return None
    return pair


def related_source_allowed(source: dict, candidate: dict) -> bool:
    """Recheck saved discovery metadata before permitting a supporting request."""
    try:
        target_fetch, target_cite = candidate["fetch"], candidate["cite"]
        if not public_document_url(target_fetch) or not _detail_url(target_cite):
            return False
        if urlparse(target_fetch).hostname == "raw.githubusercontent.com":
            raw_parent, raw_target = urlparse(source["fetch"]), urlparse(target_fetch)
            relative = posixpath.relpath(
                raw_target.path, posixpath.dirname(raw_parent.path)
            )
            expected = _raw_relative_pair(source, relative)
        else:
            expected = _related_pair(source, target_cite)
        return expected == {"fetch": target_fetch, "cite": target_cite}
    except (KeyError, TypeError, ValueError):
        return False


def _content_root(soup):
    for tag in soup(
        ["script", "style", "nav", "header", "footer", "noscript", "svg", "aside"]
    ):
        tag.decompose()
    for tag in soup.select(
        '[role="navigation"], [role="contentinfo"], .toc, .table-of-contents, .pagination, .breadcrumb, .breadcrumbs'
    ):
        tag.decompose()
    return soup.find("main") or soup.find("article") or soup.body or soup


def related_sources(text: str, source: dict, *, markdown: bool = False) -> list[dict]:
    """Extract at most 64 already-linked detail candidates; never crawl here."""
    links = []
    if markdown:
        # Ignore YAML front matter, fenced examples and HTML comments. Deliberately
        # accept only inline Markdown links whose target is an ordinary URL/path.
        body = re.sub(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", "", text, flags=re.S)
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        body = re.sub(
            r"<(nav|header|footer|aside)\b[^>]*>.*?</\1\s*>",
            "",
            body,
            flags=re.S | re.I,
        )
        heading, fence = "", None
        for line in body.splitlines():
            marker = re.match(r"^\s*(`{3,}|~{3,})", line)
            if marker:
                token = marker[1]
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = None
                continue
            if fence is not None:
                continue
            if title := re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line):
                heading = title[1][:180]
            content_line = re.sub(r"`+[^`]*`+", "", line)
            for match in re.finditer(
                r"(?<!!)\[([^\]\n]{1,180})\]\(([^\s()]+)\)", content_line
            ):
                links.append((match[2], match[1], heading, line[:400]))
    else:
        root = _content_root(BeautifulSoup(text, "html.parser"))
        heading = ""
        for node in root.find_all(["h1", "h2", "h3", "h4", "a"]):
            if node.name != "a":
                heading = node.get_text(" ", strip=True)[:180]
            else:
                parent = node.find_parent(["p", "li", "dd", "td"])
                links.append(
                    (
                        node.get("href"),
                        node.get_text(" ", strip=True)[:180],
                        heading,
                        parent.get_text(" ", strip=True)[:400] if parent else "",
                    )
                )
    found, seen = [], set()
    for href, label, heading, context in links:
        try:
            pair = _related_pair(source, href)
        except (ValueError, TypeError):
            continue
        if pair is None or not label.strip() or pair["cite"].rstrip("/") in seen:
            continue
        seen.add(pair["cite"].rstrip("/"))
        found.append({**pair, "label": label, "heading": heading, "context": context})
        if len(found) == 64:
            break
    return found


def _public_address(url: str):
    if not public_document_url(url):
        raise ValueError("unsafe_related_url")
    parsed = urlparse(url)
    addresses = socket.getaddrinfo(
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
        type=socket.SOCK_STREAM,
    )
    if not addresses or any(
        not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses
    ):
        raise ValueError("non_public_related_address")


def _safe_get(url: str, user_agent: str, *, check_robots: bool = True):
    origin = urlparse(url)
    for _ in range(3):
        _public_address(url)
        if check_robots and not allowed(url, user_agent, strict_public=True):
            raise ValueError("robots_disallow")
        response = requests.get(
            url, timeout=25, headers={"User-Agent": user_agent}, allow_redirects=False
        )
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        target = _without_fragment(urljoin(url, response.headers.get("Location", "")))
        parsed = urlparse(target)
        if (
            not public_document_url(target)
            or (check_robots and not _detail_url(target))
            or (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc)
        ):
            raise ValueError("unsafe_related_redirect")
        url = target
    raise ValueError("related_redirect_limit")


def _robots_for(
    base: str, user_agent: str, *, strict_public: bool = False
) -> RobotFileParser | None:
    cache_key = base + ("|public" if strict_public else "")
    if cache_key in _robots_cache:
        return _robots_cache[cache_key]
    rp = RobotFileParser()
    robots_url = f"{base}/robots.txt"
    try:
        resp = (
            _safe_get(robots_url, user_agent, check_robots=False)
            if strict_public
            else requests.get(
                robots_url, timeout=15, headers={"User-Agent": user_agent}
            )
        )
        if resp.status_code == 200 and (
            "Disallow" in resp.text or "Allow" in resp.text
        ):
            rp.parse(resp.text.splitlines())
        elif strict_public and resp.status_code not in {200, 404, 410}:
            rp.parse(["User-agent: *", "Disallow: /"])
        else:
            # robots.txt 없음/비표준 → 제한 없음으로 간주
            rp = None
    except (requests.RequestException, ValueError, OSError):
        if strict_public:
            rp.parse(["User-agent: *", "Disallow: /"])
        else:
            rp = None
    _robots_cache[cache_key] = rp
    return rp


def allowed(url: str, user_agent: str, *, strict_public: bool = False) -> bool:
    """robots.txt가 이 URL의 자동 수집을 허용하는지."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_for(base, user_agent, strict_public=strict_public)
    if rp is None:
        return True
    return rp.can_fetch(user_agent, url)


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    # 빈 줄 다중 압축
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def fetch_source(source: dict, user_agent: str, max_chars: int) -> dict:
    """단일 공식문서 source({'fetch','cite'})를 가져와 텍스트로 반환.

    반환: {"fetch", "cite", "ok", "text", "reason"}
    """
    fetch_url = source["fetch"]
    cite_url = source.get("cite", fetch_url)
    base = {"fetch": fetch_url, "cite": cite_url}

    supporting = source.get("supporting_source")
    if supporting:
        base["supporting_source"] = supporting
    if not supporting and not allowed(fetch_url, user_agent):
        return {**base, "ok": False, "text": "", "reason": "robots_disallow"}
    try:
        resp = (
            _safe_get(fetch_url, user_agent)
            if supporting
            else requests.get(fetch_url, timeout=25, headers={"User-Agent": user_agent})
        )
    except (requests.RequestException, ValueError, OSError) as e:
        return {**base, "ok": False, "text": "", "reason": f"request_error:{e}"}
    if resp.status_code != 200:
        return {**base, "ok": False, "text": "", "reason": f"http_{resp.status_code}"}

    # 마크다운 원문(공식 docs의 오픈소스 소스)은 HTML 추출 없이 그대로 사용.
    # SPA(JS 렌더링) 문서는 HTML 추출이 비어버리므로 raw .md 를 쓰는 게 안정적.
    markdown = (
        fetch_url.endswith((".md", ".txt"))
        or urlparse(fetch_url).hostname == "raw.githubusercontent.com"
    )
    if markdown:
        # 마크다운/평문(RFC 등)은 HTML 추출 없이 그대로 사용.
        text = resp.text.strip()
    else:
        text = _extract_text(resp.text)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[이하 생략]"
    # 매너: 같은 호스트 연속 요청 사이 약간의 딜레이
    time.sleep(2)
    related = [] if supporting else related_sources(resp.text, base, markdown=markdown)
    return {
        **base,
        "ok": True,
        "text": text,
        "reason": "ok",
        "related_sources": related,
    }


def fetch_topic_sources(
    sources: list[dict], user_agent: str, max_chars: int
) -> list[dict]:
    return [fetch_source(s, user_agent, max_chars) for s in sources]
