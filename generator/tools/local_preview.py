"""저장된 후보를 최신 실행기로 보는 읽기 전용, loopback 전용 작업 화면.

LLM·출처 수집·publisher를 사용하지 않는다. 새로고침마다 후보와 공통 자산을 읽는다.
"""

from __future__ import annotations

import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from generator.design.scene_document import render_document, validate_design

from generator.paths import GENERATOR_DIR as HERE
ASSETS = HERE.parent / "assets"
STYLES = """
:root{color-scheme:dark;--surface:#14171d;--border:#303743;--muted:#8b93a1;
color:#d6dae0;background:#0c0e12;font:16px/1.65 'Apple SD Gothic Neo','Malgun Gothic',sans-serif}
*{box-sizing:border-box}body{margin:0;padding:24px 16px;word-break:keep-all;overflow-wrap:anywhere}main{max-width:960px;margin:auto}
h1{font-size:clamp(22px,4vw,30px);line-height:1.35;margin:12px 0}p{margin:8px 0}
a{color:#79b8ff}a:focus-visible{outline:2px solid #79b8ff;outline-offset:4px}
header{border-bottom:1px solid var(--border);padding-bottom:18px;margin-bottom:24px}
.notice{color:#e3a17e}.meta{font:12px/1.8 Menlo,monospace;color:var(--muted);overflow-wrap:anywhere}
nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}nav a{padding:8px 12px;
border:1px solid var(--border);border-radius:6px;text-decoration:none;min-height:44px}
nav a[aria-current=page]{border-color:#79b8ff;color:#d6dae0;background:#14171d}
.stage{max-width:100%;margin-inline:auto}.post-content .ai-scene{margin:0 0 28px}
.post-content figcaption{overflow-wrap:anywhere}.hint{color:var(--muted);font-size:14px}
"""


def read_snapshot(run_dir: Path) -> dict:
    """화면 확인은 의미 검수 이력과 무관하지만 HTML/CSS/전이 안전 계약은 지킨다."""
    inputs = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    title, body = inputs["article_title"], inputs["article"]
    if not all(isinstance(value, str) and value.strip() for value in (title, body)):
        raise ValueError("저장된 제목/본문이 없습니다.")
    candidates = sorted(
        (int(match[1]), path)
        for path in run_dir.glob("*-candidate.json")
        if (match := re.fullmatch(r"([1-9][0-9]*)-candidate\.json", path.name))
    )
    if not candidates:
        raise ValueError("렌더링할 저장 후보가 없습니다. 먼저 디자인을 생성하세요.")
    path = candidates[-1][1]
    content = path.read_bytes()
    raw = content.decode("utf-8")
    design = validate_design(raw, body)
    return {
        "title": title,
        "candidate": path.name,
        "digest": hashlib.sha256(content).hexdigest(),
        "scenes": design["scenes"],
    }


def render_page(snapshot: dict, width: int) -> str:
    safe = html.escape
    digest = snapshot["digest"]
    figures = "".join(
        '<figure class="ai-scene">'
        f"<figcaption>{safe(scene['after_heading'])} · {safe(scene['title'])}</figcaption>"
        f'<iframe class="ai-scene-frame" src="scene/{index}?candidate={digest}" '
        f'title="{safe(scene["title"])}" sandbox="allow-scripts" '
        'referrerpolicy="no-referrer" height="560"></iframe>'
        f'<p class="ai-scene-summary">{safe(scene["caption"])}</p></figure>'
        for index, scene in enumerate(snapshot["scenes"])
    )
    navigation = "".join(
        f'<a href="?width={size}"'
        + (' aria-current="page"' if size == width else "")
        + f">{label}</a>"
        for size, label in ((698, "글 본문 폭"), (390, "390px"), (320, "320px"))
    )
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>시각화 작업 화면 · {safe(snapshot["title"])}</title>
<link rel="stylesheet" href="/preview.css"><link rel="stylesheet" href="/article-scenes.css">
<script defer src="/article-scenes.js"></script></head><body><main>
<header><p class="notice">로컬 화면 확인 · 검수 전 · API 호출 없음</p>
<h1>{safe(snapshot["title"])}</h1>
<p class="hint">저장된 LLM 장면만 확인합니다. 본문 전체와 자동 검수는 생략하며 발행하지 않습니다.<br>
CSS·JS를 수정한 뒤 새로고침하세요. 생성 프롬프트 변경은 별도 API 실행이 필요합니다.</p>
<p class="meta">후보 {safe(snapshot["candidate"])} · SHA-256 {digest[:16]}</p>
<nav aria-label="장면 표시 폭">{navigation}</nav></header>
<div class="post-content stage" style="width:{width}px">{figures}</div>
</main></body></html>"""


def make_handler(run_dir: Path, name: str):
    prefix = f"/{name}/"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # No directory server: .env, run logs and arbitrary repo files are never served.
            if self.headers.get("Host") not in {
                f"localhost:{self.server.server_port}",
                f"127.0.0.1:{self.server.server_port}",
            }:
                return self.respond("Local requests only", "text/plain", 403)
            parsed = urlsplit(self.path)
            try:
                if parsed.path == "/preview.css":
                    return self.respond(STYLES, "text/css")
                assets = {
                    "/article-scenes.css": ("css/article-scenes.css", "text/css"),
                    "/article-scenes.js": ("js/article-scenes.js", "text/javascript"),
                }
                if parsed.path in assets:
                    path, mime = assets[parsed.path]
                    return self.respond((ASSETS / path).read_text(), mime)
                if parsed.path in {"/", prefix.rstrip("/")}:
                    self.send_response(302)
                    self.send_header("Location", prefix)
                    self.end_headers()
                    return
                match = re.fullmatch(re.escape(prefix) + r"scene/([01])", parsed.path)
                if parsed.path != prefix and match is None:
                    return self.respond("Not found", "text/plain", 404)
                snapshot = read_snapshot(run_dir)
                query = parse_qs(parsed.query)
                if match:
                    if query.get("candidate") != [snapshot["digest"]]:
                        return self.respond(
                            "후보가 바뀌었습니다. 페이지를 새로고침하세요.",
                            "text/plain",
                            409,
                        )
                    index = int(match[1])
                    if index >= len(snapshot["scenes"]):
                        return self.respond("Not found", "text/plain", 404)
                    return self.respond(render_document(snapshot["scenes"][index]))
                width = query.get("width", ["698"])[0]
                width = int(width) if width in {"320", "390", "698"} else 698
                return self.respond(render_page(snapshot, width))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                # No saved arbitrary scripts are served even in this unreviewed mode.
                print(
                    f"미리보기 실패: {type(exc).__name__}: {str(exc)[:300]}", flush=True
                )
                return self.respond(
                    f"미리보기 불가: {type(exc).__name__}. 터미널에서 후보를 확인하세요.",
                    "text/plain",
                    422,
                )

        def respond(self, content: str, mime="text/html", status=200):
            data = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            pass

    return Handler


def serve_saved_design(run_dir: Path, name: str, port: int = 4011) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", name):
        raise ValueError("미리보기 이름은 영문 소문자·숫자·하이픈으로 지정하세요.")
    snapshot = read_snapshot(run_dir)  # Fail before starting a broken preview server.
    with ThreadingHTTPServer(
        ("127.0.0.1", port), make_handler(run_dir, name)
    ) as server:
        print(
            f"API 호출 없는 장면 미리보기: http://localhost:{server.server_port}/{name}/",
            flush=True,
        )
        print(
            f"{snapshot['candidate']} 재사용 · 새로고침으로 코드 반영 · 종료 Ctrl+C",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
