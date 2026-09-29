"""가져온 공식문서를 프롬프트 입력 컨텍스트로 변환한다."""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import generator.sources.catalog as catalog
import generator.sources.fetcher as fetcher
from generator.contracts import SourceBundle


_GENERIC_TERMS = frozenset(
    "the and for with from this that are documentation docs document guide guides "
    "overview introduction concepts concept infra official learn more read using use "
    "about core key current latest 참고 문서 소개 개요 가이드".split()
)


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9가-힣]+", text.lower())
    return {
        word[:-3] + "y"
        if word.endswith("ies") and len(word) > 4
        else word.rstrip("s")
        if word.endswith("s") and len(word) > 4
        else word
        for word in words
        if len(word) > 1 and word not in _GENERIC_TERMS
    }


def supporting_candidates(
    documents: list[dict], topic: dict, title_hint: str, limit: int
) -> list[dict]:
    """Rank one-hop body links; unrelated and ambiguous URLs are not fetched."""
    query = _terms(
        " ".join(
            [
                title_hint,
                *[tag for tag in topic.get("tags", []) if isinstance(tag, str)],
            ]
        )
    )
    if not query or not limit:
        return []
    occupied = {
        item[key].rstrip("/") for item in documents for key in ("fetch", "cite")
    }
    ranked = []
    for parent_index, document in enumerate(documents):
        if not document.get("ok"):
            continue
        for candidate in document.get("related_sources", []):
            if not isinstance(candidate, dict) or not fetcher.related_source_allowed(
                document, candidate
            ):
                continue
            if (
                candidate["cite"].rstrip("/") in occupied
                or candidate["fetch"].rstrip("/") in occupied
            ):
                continue
            label = str(candidate.get("label", ""))[:180]
            heading = str(candidate.get("heading", ""))[:180]
            context = str(candidate.get("context", ""))[:400]
            score = (
                4 * len(query & _terms(label))
                + 2 * len(query & _terms(urlparse(candidate["cite"]).path))
                + len(query & _terms(heading + " " + context))
            )
            if not score:
                continue
            ranked.append(
                (
                    -score,
                    parent_index,
                    candidate["cite"],
                    {
                        "fetch": candidate["fetch"],
                        "cite": candidate["cite"],
                        "supporting_source": {
                            "depth": 1,
                            "parent_fetch": document["fetch"],
                            "parent_cite": document["cite"],
                            "link_text": label,
                            "section_heading": heading,
                            "selection_score": score,
                        },
                    },
                )
            )
    selected = []
    for _, _, _, candidate in sorted(ranked, key=lambda item: item[:3]):
        if (
            candidate["cite"].rstrip("/") in occupied
            or candidate["fetch"].rstrip("/") in occupied
        ):
            continue
        occupied.update((candidate["fetch"].rstrip("/"), candidate["cite"].rstrip("/")))
        selected.append(candidate)
        if len(selected) == limit:
            break
    return selected


def normalize_sources(sources: list) -> list[dict]:
    """source 항목을 fetch/cite 쌍으로 정규화한다."""
    normalized = []
    for source in sources:
        if isinstance(source, str):
            normalized.append({"fetch": source, "cite": source})
        else:
            normalized.append(
                {
                    "fetch": source["fetch"],
                    "cite": source.get("cite", source["fetch"]),
                }
            )
    return normalized


def as_cdata(text: str) -> str:
    """CDATA 종료 문자열이 있는 텍스트도 XML 안에 안전하게 넣는다."""
    return xml_source_whitespace(text).replace("]]>", "]]]]><![CDATA[>")


def xml_source_whitespace(text: str) -> str:
    """RFC 평문 페이지 구분자를 XML 1.0에서 허용되는 줄바꿈으로 보존한다.

    글자나 문서 구조는 고치지 않는다. 다른 잘못된 XML은 파서가 거부한다.
    """
    return text.replace("\f", "\n").replace("\v", "\n")


def build_sources_block(fetched: list[dict]) -> tuple[str, list[str]]:
    """성공한 출처를 XML 문서 묶음과 인용 URL 목록으로 변환한다."""
    blocks = []
    cite_urls = []
    for index, item in enumerate(fetched, 1):
        if not item["ok"]:
            print(f"  - 스킵 {item['fetch']} ({item['reason']})")
            continue
        cite_urls.append(item["cite"])
        content = as_cdata(item["text"])
        blocks.append(
            f'<document index="{index}">\n'
            f"  <source_url>{html.escape(item['cite'], quote=True)}</source_url>\n"
            f"  <document_content><![CDATA[\n{content}\n]]></document_content>\n"
            f"</document>"
        )
    return "\n\n".join(blocks), cite_urls


class OfficialDocumentSourceGateway:
    """robots 정책을 지켜 공식 웹 문서를 가져오는 현재 출처 구현."""

    def __init__(self, supporting_documents: int = 0):
        if type(supporting_documents) is not int or not 0 <= supporting_documents <= 2:
            raise ValueError("supporting_documents must be an integer from 0 to 2")
        self.supporting_documents = supporting_documents

    def fetch(
        self,
        topic: dict,
        *,
        user_agent: str,
        max_chars: int,
    ) -> SourceBundle:
        if "sources" in topic:
            normalized = normalize_sources(topic["sources"])
        else:
            normalized = [{"fetch": topic["fetch"], "cite": topic["cite"]}]

        documents = fetcher.fetch_topic_sources(
            normalized,
            user_agent,
            max_chars,
        )
        hint = topic.get("title_hint")
        if not hint:
            first_text = next(
                (item["text"] for item in documents if item["ok"]),
                "",
            )
            hint = catalog.derive_title(first_text, normalized[0]["fetch"])
        extras = supporting_candidates(
            documents, topic, hint, self.supporting_documents
        )
        # Only the original root documents are inspected. Extra documents are
        # retained with provenance even on failure, and never recursively crawled.
        for source in extras:
            try:
                item = fetcher.fetch_source(source, user_agent, max_chars)
            except (ValueError, OSError) as exc:
                item = {
                    **source,
                    "ok": False,
                    "text": "",
                    "reason": f"supporting_error:{type(exc).__name__}",
                }
            documents.append({**item, "supporting_source": source["supporting_source"]})
        prompt_context, cite_urls = build_sources_block(documents)
        return SourceBundle(
            documents=documents,
            prompt_context=prompt_context,
            cite_urls=tuple(cite_urls),
            title_hint=hint,
        )
