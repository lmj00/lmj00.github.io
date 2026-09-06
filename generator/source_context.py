"""가져온 공식문서를 프롬프트 입력 컨텍스트로 변환한다."""

from __future__ import annotations

import html

import catalog
import fetcher
from contracts import SourceBundle


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
    return text.replace("]]>", "]]]]><![CDATA[>")


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
        prompt_context, cite_urls = build_sources_block(documents)
        hint = topic.get("title_hint")
        if not hint:
            first_text = next(
                (item["text"] for item in documents if item["ok"]),
                "",
            )
            hint = catalog.derive_title(first_text, normalized[0]["fetch"])
        return SourceBundle(
            documents=documents,
            prompt_context=prompt_context,
            cite_urls=tuple(cite_urls),
            title_hint=hint,
        )
