"""공식문서 fetch + robots.txt 준수 + 본문 텍스트 추출."""
from __future__ import annotations

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

_robots_cache: dict[str, RobotFileParser | None] = {}


def _robots_for(base: str, user_agent: str) -> RobotFileParser | None:
    if base in _robots_cache:
        return _robots_cache[base]
    rp = RobotFileParser()
    robots_url = f"{base}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=15,
                            headers={"User-Agent": user_agent})
        if resp.status_code == 200 and "Disallow" in resp.text or "Allow" in resp.text:
            rp.parse(resp.text.splitlines())
        else:
            # robots.txt 없음/비표준 → 제한 없음으로 간주
            rp = None
    except requests.RequestException:
        rp = None
    _robots_cache[base] = rp
    return rp


def allowed(url: str, user_agent: str) -> bool:
    """robots.txt가 이 URL의 자동 수집을 허용하는지."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_for(base, user_agent)
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

    if not allowed(fetch_url, user_agent):
        return {**base, "ok": False, "text": "", "reason": "robots_disallow"}
    try:
        resp = requests.get(fetch_url, timeout=25, headers={"User-Agent": user_agent})
    except requests.RequestException as e:
        return {**base, "ok": False, "text": "", "reason": f"request_error:{e}"}
    if resp.status_code != 200:
        return {**base, "ok": False, "text": "", "reason": f"http_{resp.status_code}"}

    # 마크다운 원문(공식 docs의 오픈소스 소스)은 HTML 추출 없이 그대로 사용.
    # SPA(JS 렌더링) 문서는 HTML 추출이 비어버리므로 raw .md 를 쓰는 게 안정적.
    if (fetch_url.endswith((".md", ".txt"))
            or "raw.githubusercontent.com" in fetch_url):
        # 마크다운/평문(RFC 등)은 HTML 추출 없이 그대로 사용.
        text = resp.text.strip()
    else:
        text = _extract_text(resp.text)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[이하 생략]"
    # 매너: 같은 호스트 연속 요청 사이 약간의 딜레이
    time.sleep(2)
    return {**base, "ok": True, "text": text, "reason": "ok"}


def fetch_topic_sources(sources: list[dict], user_agent: str, max_chars: int) -> list[dict]:
    return [fetch_source(s, user_agent, max_chars) for s in sources]
