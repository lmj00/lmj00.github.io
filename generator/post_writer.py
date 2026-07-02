"""생성된 본문 → Jekyll 포스트 파일(.md) 작성."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "_posts" / "ai-notes"
ASSETS_DIR = HERE.parent / "assets" / "diagrams"

_D2_BLOCK = re.compile(r"```d2\s*\n(.*?)```", re.DOTALL)


def _render_one_d2(src: str, slug: str, idx: int) -> str | None:
    """d2 소스 하나를 SVG로 렌더링. 성공 시 이미지 마크다운, 실패 시 None(제거)."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    svg_name = f"{slug}-{idx}.svg"
    svg_path = ASSETS_DIR / svg_name
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".d2", delete=False,
                                         encoding="utf-8") as tf:
            tf.write(src)
            tmp = tf.name
        r = subprocess.run(["d2", "--pad", "20", tmp, str(svg_path)],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(f"  [d2] 블록 {idx} 렌더 실패 → 제거: {r.stderr.strip()[:120]}")
            return None
        return f"![diagram](/assets/diagrams/{svg_name})"
    except FileNotFoundError:
        print("  [d2] d2 미설치 → 다이어그램 블록을 코드로 유지")
        return f"```\n{src}```"
    except subprocess.TimeoutExpired:
        print(f"  [d2] 블록 {idx} 타임아웃 → 제거")
        return None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def normalize_markdown(body: str) -> str:
    """LLM 출력의 흔한 마크다운 실수 교정. (코드블록 안은 건드리지 않음)"""
    out = []
    in_fence = False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            # '###개요' → '### 개요' (헤딩 # 뒤 공백 누락 교정)
            line = re.sub(r"^(#{1,6})([^#\s])", r"\1 \2", line)
        out.append(line)
    return "\n".join(out)


def render_d2_blocks(body: str, slug: str) -> str:
    """본문의 ```d2 블록을 렌더링한 SVG 이미지로 치환. 실패한 블록은 제거."""
    matches = list(_D2_BLOCK.finditer(body))
    for i, m in enumerate(matches, 1):
        replacement = _render_one_d2(m.group(1), slug, i)
        if replacement is None:
            replacement = ""
        body = body.replace(m.group(0), replacement, 1)
    return body


def _slugify(text: str) -> str:
    text = text.strip().lower()
    # 한글/영문/숫자만 남기고 나머지는 하이픈
    text = re.sub(r"[^0-9a-z가-힣]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60] or "post"


def _frontmatter(title: str, date: dt.date, model: str, tags: list[str],
                 source_urls: list[str]) -> str:
    tag_str = ", ".join(tags)
    src_yaml = "\n".join(f"  - {u}" for u in source_urls)
    return (
        "---\n"
        f'title: "{title}"\n'
        "layout: post\n"
        "categories: ai-notes\n"
        "type: study-note\n"
        f"date: {date.isoformat()}\n"
        f"tags: [{tag_str}]\n"
        f'generated_by: "openrouter:{model}"\n'
        f"generated_at: {date.isoformat()}\n"
        "sources:\n"
        f"{src_yaml}\n"
        "---\n"
    )


def _footer(model: str, source_urls: list[str]) -> str:
    links = "\n".join(f"> - [{u}]({u})" for u in source_urls)
    return (
        "\n\n---\n"
        f"> 🤖 작성 모델: `{model}` (OpenRouter)\n"
        "> \n"
        "> 참고한 공식문서:\n"
        f"{links}\n"
    )


def write_post(title: str, body: str, model: str, tags: list[str],
               source_urls: list[str], date: dt.date | None = None) -> Path:
    date = date or dt.date.today()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(title)
    filename = f"{date.isoformat()}-{slug}.md"
    path = OUT_DIR / filename

    # 마크다운 실수 교정 후, ```d2 블록을 SVG로 렌더링해 이미지로 치환
    body = normalize_markdown(body)
    body = render_d2_blocks(body, f"{date.isoformat()}-{slug}")

    top_badge = "> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.\n\n"
    content = (
        _frontmatter(title, date, model, tags, source_urls)
        + "\n"
        + top_badge
        + body.strip()
        + _footer(model, source_urls)
    )
    path.write_text(content, encoding="utf-8")
    return path
