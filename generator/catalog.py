"""공식문서 레포의 마크다운 페이지를 자동 열거해 '주제 풀'을 만든다.

주제를 손으로 적지 않아도, 각 공식문서(GitHub) 트리에서 후보 페이지를 긁어
fetch URL(raw .md)과 cite URL(사람이 보는 공식 페이지)을 자동 생성한다.
"""
from __future__ import annotations

import os
import re
import fnmatch
import requests

_tree_cache: dict[str, list[str]] = {}


def _github_tree(repo: str, ref: str) -> list[str]:
    key = f"{repo}@{ref}"
    if key in _tree_cache:
        return _tree_cache[key]
    url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    paths = [item["path"] for item in resp.json().get("tree", [])
             if item.get("type") == "blob"]
    _tree_cache[key] = paths
    return paths


def _path_to_cite(path: str, cat: dict) -> str:
    if cat.get("cite_fixed"):
        return cat["cite_fixed"]
    rel = path
    strip = cat.get("strip_prefix", "")
    if strip and rel.startswith(strip):
        rel = rel[len(strip):]
    if rel.endswith(".md"):
        rel = rel[:-3]
    if cat.get("drop_index") and rel.endswith("/_index"):
        rel = rel[: -len("/_index")]
    url = cat["web_base"].rstrip("/") + "/" + rel.lstrip("/")
    if cat.get("trailing_slash"):
        url += "/"
    return url


def _raw_url(repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def candidates_from_catalog(cat: dict) -> list[dict]:
    """하나의 카탈로그에서 주제 후보 리스트 생성."""
    paths = _github_tree(cat["repo"], cat["ref"])
    includes = cat.get("include_prefixes", [""])
    excludes = cat.get("exclude_globs", [])
    out = []
    for p in paths:
        if not p.endswith(".md"):
            continue
        if not any(p.startswith(pre) for pre in includes):
            continue
        if any(fnmatch.fnmatch(p, g) for g in excludes):
            continue
        out.append({
            "id": f"{cat['id']}::{p}",
            "fetch": _raw_url(cat["repo"], cat["ref"], p),
            "cite": _path_to_cite(p, cat),
            "tags": cat.get("tags", []),
            "title_hint": None,  # fetch 후 본문에서 추출
        })
    return out


def candidates_from_man_index(cat: dict) -> list[dict]:
    """man7.org 섹션 인덱스에서 man 페이지를 자동 열거."""
    ua = cat.get("user_agent", "Mozilla/5.0")
    resp = requests.get(cat["index_url"], headers={"User-Agent": ua}, timeout=30)
    resp.raise_for_status()
    sec = cat["section"]
    rel_paths = sorted(set(re.findall(rf'man{sec}/[A-Za-z0-9_.+-]+\.{sec}[a-z]?\.html', resp.text)))
    base = cat.get("base", "https://man7.org/linux/man-pages/")
    excludes = cat.get("exclude_globs", [])
    out = []
    for rel in rel_paths:
        if any(fnmatch.fnmatch(rel, g) for g in excludes):
            continue
        url = base.rstrip("/") + "/" + rel
        out.append({
            "id": f"{cat['id']}::{rel}",
            "fetch": url, "cite": url,
            "tags": cat.get("tags", []), "title_hint": None,
        })
    return out


def candidates_from_rfc_index(cat: dict) -> list[dict]:
    """rfc-index.txt에서 특정 상태(예: INTERNET STANDARD)의 RFC만 자동 열거."""
    ua = cat.get("user_agent", "Mozilla/5.0")
    resp = requests.get(cat["index_url"], headers={"User-Agent": ua}, timeout=40)
    resp.raise_for_status()
    statuses = set(s.upper() for s in cat.get("statuses", ["INTERNET STANDARD"]))
    out = []
    # 엔트리는 빈 줄로 구분, 줄바꿈으로 래핑됨 → 블록 단위로 합쳐 파싱
    for block in re.split(r"\n\s*\n", resp.text):
        block = " ".join(line.strip() for line in block.splitlines()).strip()
        m = re.match(r"^(\d{1,5})\s+(.*)", block)
        if not m:
            continue
        num, rest = m.group(1), m.group(2)
        st = re.search(r"Status:\s*([A-Z][A-Z ]+?)\)", rest)
        if not st or st.group(1).strip() not in statuses:
            continue
        if "(Obsoleted by" in rest:   # 폐기된 표준 제외
            continue
        title = rest.split(". ")[0].strip().rstrip(".")
        out.append({
            "id": f"{cat['id']}::rfc{num}",
            "fetch": f"https://www.rfc-editor.org/rfc/rfc{num}.txt",
            "cite": f"https://www.rfc-editor.org/rfc/rfc{num}",
            "tags": cat.get("tags", []),
            "title_hint": f"{title} (RFC {num})",
        })
    return out


def _sitemap_locs(url: str, ua: str, depth: int = 0) -> list[str]:
    """sitemap.xml의 <loc> URL들을 수집. 사이트맵 인덱스면 한 단계 따라 들어감."""
    resp = requests.get(url, headers={"User-Agent": ua}, timeout=60)
    resp.raise_for_status()
    text = resp.text
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
    is_index = "<sitemapindex" in text
    if is_index and depth < 1:
        out = []
        for sub in locs:
            try:
                out.extend(_sitemap_locs(sub, ua, depth + 1))
            except requests.RequestException:
                continue
        return out
    return locs


def candidates_from_sitemap(cat: dict) -> list[dict]:
    """사이트의 sitemap.xml에서 페이지를 자동 열거. (사이트 주소 + 경로필터만 필요)"""
    ua = cat.get("user_agent", "Mozilla/5.0 (compatible; lmj00-blog-generator)")
    locs = _sitemap_locs(cat["sitemap"], ua)
    includes = cat.get("include_prefixes") or ([cat["include"]] if cat.get("include") else [""])
    excludes = cat.get("exclude_globs", [])
    out, seen = [], set()
    for u in locs:
        u = u.strip()
        if u in seen:
            continue
        if not any(inc in u for inc in includes):
            continue
        if any(fnmatch.fnmatch(u, g) for g in excludes):
            continue
        seen.add(u)
        out.append({
            "id": f"{cat['id']}::{u}",
            "fetch": u, "cite": u,
            "tags": cat.get("tags", []), "title_hint": None,
        })
    return out


_DISPATCH = {
    "github_tree": candidates_from_catalog,
    "man_index": candidates_from_man_index,
    "rfc_index": candidates_from_rfc_index,
    "sitemap": candidates_from_sitemap,
}


def build_pool(catalogs: list[dict]) -> list[dict]:
    pool = []
    for cat in catalogs:
        fn = _DISPATCH.get(cat.get("type", "github_tree"))
        if fn is None:
            print(f"  - 알 수 없는 카탈로그 타입: {cat.get('type')}")
            continue
        try:
            pool.extend(fn(cat))
        except requests.RequestException as e:
            print(f"  - 카탈로그 {cat.get('id')} 열거 실패: {e}")
    return pool


_TITLE_FM = re.compile(r'^title:\s*"?([^"\n]+)"?', re.MULTILINE)
_TITLE_H1 = re.compile(r'^#{1,2}\s+(.+)$', re.MULTILINE)


def derive_title(md_text: str, fallback_path: str) -> str:
    """마크다운 frontmatter title 또는 첫 헤딩에서 제목 추출."""
    m = _TITLE_FM.search(md_text[:600])
    if m:
        return m.group(1).strip()
    m = _TITLE_H1.search(md_text)
    if m:
        return m.group(1).strip()
    name = fallback_path.rsplit("/", 1)[-1].replace(".md", "").replace("-", " ")
    return name.title()
