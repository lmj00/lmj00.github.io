"""Fast contract and logic checks; no Chromium or paid APIs."""

from __future__ import annotations

import copy
import io
import re
import socket
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from unittest import mock

import generator.sources.fetcher as fetcher
from generator.contracts import GeneratedText, ModelGatewayError
from generator.design.visual_contracts import ReviewContractError, source_sections
from generator.sources import difficulty, topics
from generator.sources.source_context import (
    OfficialDocumentSourceGateway,
    as_cdata,
    supporting_candidates,
)
from generator.tests.fixtures.sources import (
    RAW_DOCUMENT,
    ROOT_DOCUMENT,
    link,
    root_document,
    source_response,
)


class DifficultyGatewayTest(unittest.TestCase):
    def test_scoring_uses_injected_gateway_and_fallback_model_order(self):
        gateway = mock.Mock()
        gateway.complete_text.side_effect = [
            ModelGatewayError("upstream failed"),
            GeneratedText('{"Overview": 1, "Internals": 9}', "second"),
        ]
        candidates = [
            {"id": "intro", "title_hint": "Overview"},
            {"id": "advanced", "title_hint": "Internals"},
        ]
        actual = difficulty._score_chunk_with_llm(
            candidates, ["first", "second"], gateway
        )
        self.assertEqual(actual, {"intro": 1, "advanced": 5})
        self.assertEqual(
            [call.args[2] for call in gateway.complete_text.call_args_list],
            ["first", "second"],
        )

    def test_cached_scores_never_call_gateway(self):
        gateway = mock.Mock()
        with (
            mock.patch.object(difficulty, "load_cache", return_value={"intro": 1}),
            mock.patch.object(difficulty, "_save_cache") as save,
        ):
            self.assertEqual(
                difficulty.score([{"id": "intro"}], {}, gateway=gateway), {"intro": 1}
            )
        gateway.complete_text.assert_not_called()
        save.assert_not_called()

    def test_missing_gateway_retains_offline_heuristic(self):
        with (
            mock.patch.object(difficulty, "load_cache", return_value={}),
            mock.patch.object(difficulty, "_save_cache") as save,
        ):
            result = difficulty.score(
                [{"id": "overview"}], {"model_fallback": ["model"]}
            )
        self.assertEqual(result, {"overview": 2})
        save.assert_called_once_with(result)

    def test_gateway_failure_is_private_and_missing_scores_are_filled(self):
        for response in (
            RuntimeError("private-credential"),
            GeneratedText('{"Overview": 1}', "model"),
        ):
            gateway = mock.Mock()
            if isinstance(response, Exception):
                gateway.complete_text.side_effect = response
            else:
                gateway.complete_text.return_value = response
            output = io.StringIO()
            with (
                mock.patch.object(difficulty, "load_cache", return_value={}),
                mock.patch.object(difficulty, "_save_cache"),
                redirect_stdout(output),
            ):
                result = difficulty.score(
                    [{"id": "overview", "title_hint": "Overview"}, {"id": "internals"}],
                    {"model_fallback": ["model"]},
                    gateway=gateway,
                )
            self.assertEqual(result["internals"], 4)
            self.assertEqual(
                result["overview"], 2 if isinstance(response, Exception) else 1
            )
            self.assertNotIn("private-credential", output.getvalue())

    def test_catalog_selection_passes_gateway_into_difficulty_scoring(self):
        gateway = mock.Mock()
        candidate = {"id": "catalog::overview"}
        with (
            mock.patch.object(topics.dedup, "pick_next_topic", return_value=None),
            mock.patch.object(topics.dedup, "load_done", return_value=[]),
            mock.patch.object(topics.catalog, "build_pool", return_value=[candidate]),
            mock.patch.object(
                difficulty, "score", return_value={candidate["id"]: 1}
            ) as score,
        ):
            result = topics.CatalogTopicRepository(gateway=gateway).select({})
        self.assertEqual(result, candidate)
        score.assert_called_once_with([candidate], {}, gateway=gateway)


class NoNetworkTests(unittest.TestCase):
    def setUp(self):
        fetcher._robots_cache.clear()
        self.network = mock.patch(
            "generator.sources.fetcher.requests.get",
            side_effect=AssertionError("Live HTTP is forbidden in unit tests"),
        ).start()
        self.dns = mock.patch(
            "generator.sources.fetcher.socket.getaddrinfo",
            side_effect=AssertionError("Live DNS is forbidden in unit tests"),
        ).start()
        self.sleep = mock.patch("generator.sources.fetcher.time.sleep").start()
        self.addCleanup(mock.patch.stopall)


class RelatedSourceTests(NoNetworkTests):
    def test_html_discovers_only_body_links_and_records_local_heading_and_caption(self):
        html = """<html><header><a href="/docs/header-security/">security</a></header>
        <main><h1>Security</h1><nav><a href="/docs/nav-security/">security</a></nav>
        <div role="navigation"><a href="/docs/menu-security/">security</a></div>
        <aside><a href="/docs/aside-security/">security</a></aside>
        <div class="toc"><a href="/docs/toc-security/">security</a></div>
        <h2>Admission policy</h2><p>Security checks use <a href="/docs/reference/admission-control/#example">admission control</a>.</p>
        <p><a href="/docs/reference/admission-control/">duplicate</a></p>
        </main><footer><a href="/docs/footer-security/">security</a></footer></html>"""
        actual = fetcher.related_sources(html, ROOT_DOCUMENT)
        self.assertEqual(len(actual), 1)
        self.assertEqual(
            actual[0]["cite"], "https://kubernetes.io/docs/reference/admission-control/"
        )
        self.assertEqual(actual[0]["heading"], "Admission policy")
        self.assertEqual(actual[0]["label"], "admission control")
        self.assertIn("Security checks", actual[0]["context"])
        self.network.assert_not_called()
        self.dns.assert_not_called()

    def test_unsafe_unrelated_navigation_asset_and_query_links_are_not_candidates(self):
        paths = (
            "#local",
            ROOT_DOCUMENT["cite"],
            "https://external.example.com/docs/security/",
            "https://kubernetes.io.evil.example/docs/security/",
            "//evil.example/docs/security/",
            "https://user:secret@kubernetes.io/docs/security-policy/",
            "http://127.0.0.1/admin",
            "http://localhost:4000/docs/security/",
            "http://192.168.1.1/docs/security/",
            "http://169.254.169.254/latest/meta-data",
            "javascript:alert(1)",
            "/docs/policy/?token=private",
            "/docs/policy/%2e%2e/account/",
            "/docs/index.html",
            "/docs/",
            "/news/security/",
            "/account/security/",
            "/assets/policy.svg",
            "/docs/policy.yaml",
            "/docs/policy.pdf",
            "http://[malformed/",
            "/docs/policy/;session=abc",
        )
        for href in paths:
            with self.subTest(href=href):
                actual = fetcher.related_sources(
                    f'<main><p><a href="{href}">Security details</a></p></main>',
                    ROOT_DOCUMENT,
                )
                self.assertEqual(actual, [])

    def test_public_url_syntax_rejects_credentials_nonpublic_hosts_and_obscured_ips(
        self,
    ):
        for url in (
            "http://localhost./docs/x",
            "http://service.internal/docs/x",
            "http://127.1/docs/x",
            "http://2130706433/docs/x",
            "http://[::1]/docs/x",
            "https://host.local/docs/x",
            "ftp://kubernetes.io/docs/x",
            "https://kubernetes.io:444/docs/x",
            "https://kubernetes.io/docs/x?x=y",
            "https://kubernetes.io\\@127.0.0.1/x",
        ):
            with self.subTest(url=url):
                self.assertFalse(fetcher.public_document_url(url))
        self.assertTrue(
            fetcher.public_document_url("https://kubernetes.io/docs/security/")
        )

    def test_markdown_resolves_only_provable_relative_raw_document_pairs(self):
        body = """---
title: Security
example: '[metadata](metadata.md)'
---
# Security
[Admission policy](admission.md#validation)
[unsupported slug](admission)
[unsupported reference][admission]
![diagram](diagram.md)
`[inline example](inline.md)`
```markdown
[fenced example](fenced.md)
```
<nav>[navigation](navigation.md)</nav>
<!-- [comment](comment.md) -->
[admission]: admission.md
"""
        actual = fetcher.related_sources(body, RAW_DOCUMENT, markdown=True)
        self.assertEqual(len(actual), 1)
        self.assertEqual(
            actual[0]["fetch"],
            "https://raw.githubusercontent.com/org/docs/main/docs/admission.md",
        )
        self.assertEqual(actual[0]["cite"], "https://docs.example.com/docs/admission")
        self.assertTrue(fetcher.related_source_allowed(RAW_DOCUMENT, actual[0]))

    def test_raw_index_mapping_and_relative_parent_paths_stay_inside_proven_doc_root(
        self,
    ):
        source = {
            "fetch": "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/concepts/security/_index.md",
            "cite": "https://kubernetes.io/docs/concepts/security/",
        }
        actual = fetcher.related_sources(
            "# Security\n[Admission](../../reference/admission.md)\n[Escape](../../../../../../other.md)",
            source,
            markdown=True,
        )
        self.assertEqual(len(actual), 1)
        self.assertEqual(
            actual[0]["cite"], "https://kubernetes.io/docs/reference/admission/"
        )
        self.assertEqual(
            actual[0]["fetch"],
            "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/reference/admission.md",
        )

    def test_ambiguous_fixed_cite_mapping_is_not_guessed(self):
        source = {
            "fetch": "https://raw.githubusercontent.com/apache/kafka/trunk/docs/design/controller.md",
            "cite": "https://kafka.apache.org/documentation/",
        }
        self.assertEqual(
            fetcher.related_sources(
                "[Replication](replication.md)", source, markdown=True
            ),
            [],
        )

    def test_saved_candidate_metadata_cannot_swap_cite_domain_or_github_repository(
        self,
    ):
        actual = fetcher.related_sources(
            "[Admission](admission.md)", RAW_DOCUMENT, markdown=True
        )[0]
        for replacement in (
            {
                "fetch": "https://raw.githubusercontent.com/evil/docs/main/docs/admission.md"
            },
            {"cite": "https://evil.example.com/docs/admission"},
            {"fetch": "http://127.0.0.1/docs/admission.md"},
        ):
            with self.subTest(replacement=replacement):
                self.assertFalse(
                    fetcher.related_source_allowed(
                        RAW_DOCUMENT, {**actual, **replacement}
                    )
                )

    def test_discovery_is_bounded_even_when_a_page_has_many_links(self):
        body = (
            "<main>"
            + "".join(
                f'<a href="/docs/policy-{index}/">policy {index}</a>'
                for index in range(100)
            )
            + "</main>"
        )
        self.assertEqual(len(fetcher.related_sources(body, ROOT_DOCUMENT)), 64)

    def test_fetch_root_preserves_body_and_discovers_related_links_without_extra_requests(
        self,
    ):
        self.network.side_effect = None
        self.network.return_value = source_response(
            '<main><h1>Security</h1><p><a href="/docs/policy/">Policy</a></p></main>'
        )
        with mock.patch("generator.sources.fetcher.allowed", return_value=True):
            actual = fetcher.fetch_source(ROOT_DOCUMENT, "test-agent", 10)
        self.assertTrue(actual["ok"])
        self.assertEqual(actual["cite"], ROOT_DOCUMENT["cite"])
        self.assertEqual(
            actual["related_sources"][0]["cite"], "https://kubernetes.io/docs/policy/"
        )
        self.assertLessEqual(len(actual["text"]), 10 + len("\n...[이하 생략]"))
        self.assertEqual(self.network.call_count, 1)
        self.dns.assert_not_called()


class SupportingGatewayTests(NoNetworkTests):
    def topic(self):
        return {
            **ROOT_DOCUMENT,
            "title_hint": "Kubernetes security policy",
            "tags": ["kubernetes"],
        }

    def test_default_does_not_fetch_related_sources(self):
        base = root_document([link("/docs/security-policy/", "Security policy")])
        with (
            mock.patch(
                "generator.sources.fetcher.fetch_topic_sources", return_value=[base]
            ),
            mock.patch("generator.sources.fetcher.fetch_source") as extra,
        ):
            bundle = OfficialDocumentSourceGateway().fetch(
                self.topic(), user_agent="test", max_chars=1000
            )
        extra.assert_not_called()
        self.assertEqual(bundle.documents, [base])
        self.assertEqual(bundle.cite_urls, (ROOT_DOCUMENT["cite"],))

    def test_relevance_ranking_prefers_topic_overlap_and_ignores_unrelated_links(self):
        documents = [
            root_document(
                [
                    link("/docs/volume-mount/", "Storage mount"),
                    link("/docs/policy/", "Admission", heading="Security policy"),
                    link("/docs/security-policy/", "Security policy enforcement"),
                    link(
                        "/docs/storage-security/",
                        "Storage",
                        context="Security boundaries apply.",
                    ),
                ]
            )
        ]
        actual = supporting_candidates(documents, self.topic(), "Security policy", 2)
        self.assertEqual(
            [item["cite"] for item in actual],
            [
                "https://kubernetes.io/docs/security-policy/",
                "https://kubernetes.io/docs/policy/",
            ],
        )
        self.assertGreater(
            actual[0]["supporting_source"]["selection_score"],
            actual[1]["supporting_source"]["selection_score"],
        )

    def test_max_two_one_hop_supports_and_failed_attempts_preserve_root_and_provenance(
        self,
    ):
        links = [
            link(f"/docs/security-policy-{index}/", f"Security policy {index}")
            for index in range(4)
        ]
        base = root_document(links)
        extra_results = [
            {
                **links[0],
                "ok": True,
                "text": "Detailed policy semantics.",
                "reason": "ok",
                "related_sources": [
                    link("/docs/security-grandchild/", "Security policy")
                ],
            },
            {**links[1], "ok": False, "text": "", "reason": "http_429"},
        ]
        before = copy.deepcopy(base)
        with (
            mock.patch(
                "generator.sources.fetcher.fetch_topic_sources", return_value=[base]
            ),
            mock.patch(
                "generator.sources.fetcher.fetch_source", side_effect=extra_results
            ) as extra,
        ):
            bundle = OfficialDocumentSourceGateway(supporting_documents=2).fetch(
                self.topic(), user_agent="test", max_chars=456
            )
        self.assertEqual(extra.call_count, 2)
        self.assertEqual(base, before)
        self.assertEqual(bundle.documents[0], base)
        self.assertEqual(len(bundle.documents), 3)
        self.assertEqual(bundle.documents[2]["reason"], "http_429")
        self.assertEqual(bundle.cite_urls, (ROOT_DOCUMENT["cite"], links[0]["cite"]))
        self.assertIn("Detailed policy semantics.", bundle.prompt_context)
        self.assertNotIn("http_429", bundle.prompt_context)
        for item in bundle.documents[1:]:
            self.assertEqual(item["supporting_source"]["depth"], 1)
            self.assertEqual(
                item["supporting_source"]["parent_cite"], ROOT_DOCUMENT["cite"]
            )
        for call in extra.call_args_list:
            self.assertEqual(call.args[1:], ("test", 456))

    def test_failed_support_exception_does_not_discard_base(self):
        base = root_document([link("/docs/security-policy/", "Security policy")])
        with (
            mock.patch(
                "generator.sources.fetcher.fetch_topic_sources", return_value=[base]
            ),
            mock.patch(
                "generator.sources.fetcher.fetch_source",
                side_effect=ValueError("unavailable"),
            ),
        ):
            bundle = OfficialDocumentSourceGateway(1).fetch(
                self.topic(), user_agent="test", max_chars=100
            )
        self.assertEqual(bundle.cite_urls, (ROOT_DOCUMENT["cite"],))
        self.assertFalse(bundle.documents[1]["ok"])
        self.assertEqual(bundle.documents[1]["reason"], "supporting_error:ValueError")
        self.assertIn("Official security overview", bundle.prompt_context)

    def test_existing_roots_and_duplicate_related_urls_are_not_refetched(self):
        target = link("/docs/security-policy/", "Security policy")
        docs = [
            root_document([target, target]),
            {**target, "ok": True, "text": "existing", "reason": "ok"},
        ]
        self.assertEqual(
            supporting_candidates(docs, self.topic(), "Security policy", 2), []
        )
        docs = [root_document([target, target])]
        self.assertEqual(
            len(supporting_candidates(docs, self.topic(), "Security policy", 2)), 1
        )

    def test_only_successful_root_documents_participate_in_discovery(self):
        base = root_document([link("/docs/security-policy/", "Security policy")])
        base["ok"] = False
        self.assertEqual(
            supporting_candidates([base], self.topic(), "Security policy", 2), []
        )

    def test_without_title_hint_uses_title_derived_from_original_root_only(self):
        base = root_document([link("/docs/security-policy/", "Security policy")])
        with (
            mock.patch(
                "generator.sources.fetcher.fetch_topic_sources", return_value=[base]
            ),
            mock.patch(
                "generator.sources.catalog.derive_title", return_value="Security policy"
            ) as derive,
            mock.patch(
                "generator.sources.fetcher.fetch_source",
                return_value={
                    "fetch": "https://kubernetes.io/docs/security-policy/",
                    "cite": "https://kubernetes.io/docs/security-policy/",
                    "ok": True,
                    "text": "detail",
                    "reason": "ok",
                },
            ),
        ):
            bundle = OfficialDocumentSourceGateway(1).fetch(
                {**ROOT_DOCUMENT}, user_agent="test", max_chars=500
            )
        self.assertEqual(bundle.title_hint, "Security policy")
        derive.assert_called_once_with(base["text"], ROOT_DOCUMENT["fetch"])

    def test_invalid_budget_is_rejected(self):
        for count in (-1, 3, True, "2", None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                OfficialDocumentSourceGateway(count)


class SupportingFetchSafetyTests(NoNetworkTests):
    def setUp(self):
        super().setUp()
        self.dns.side_effect = None
        self.dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
        ]

    def supporting(self):
        return {
            "fetch": "https://kubernetes.io/docs/security-policy/",
            "cite": "https://kubernetes.io/docs/security-policy/",
            "supporting_source": {"depth": 1, "parent_cite": ROOT_DOCUMENT["cite"]},
        }

    def test_support_fetch_checks_public_address_robots_and_never_discovers_a_second_hop(
        self,
    ):
        self.network.side_effect = None
        self.network.return_value = source_response(
            '<main>Policy semantics <a href="/docs/security-grandchild/">security</a></main>'
        )
        with mock.patch(
            "generator.sources.fetcher.allowed", return_value=True
        ) as allowed:
            actual = fetcher.fetch_source(self.supporting(), "test", 1000)
        self.assertTrue(actual["ok"])
        self.assertEqual(actual["related_sources"], [])
        self.assertEqual(actual["supporting_source"]["depth"], 1)
        allowed.assert_called_once_with(
            self.supporting()["fetch"], "test", strict_public=True
        )
        self.assertEqual(self.network.call_args.kwargs["allow_redirects"], False)

    def test_private_dns_result_is_rejected_before_any_http_request(self):
        self.dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]
        actual = fetcher.fetch_source(self.supporting(), "test", 1000)
        self.assertFalse(actual["ok"])
        self.assertIn("non_public_related_address", actual["reason"])
        self.network.assert_not_called()

    def test_redirects_cannot_leave_origin_or_enter_private_assets_or_account_paths(
        self,
    ):
        for target in (
            "http://127.0.0.1/admin",
            "https://evil.example.com/docs/policy/",
            "https://kubernetes.io/account/security/",
            "https://kubernetes.io/assets/policy.svg",
            "http://kubernetes.io/docs/policy/",
        ):
            with (
                self.subTest(target=target),
                mock.patch("generator.sources.fetcher.allowed", return_value=True),
            ):
                self.network.reset_mock()
                self.network.side_effect = None
                self.network.return_value = source_response(status=302, location=target)
                actual = fetcher.fetch_source(self.supporting(), "test", 1000)
                self.assertFalse(actual["ok"])
                self.assertIn("unsafe_related_redirect", actual["reason"])
                self.assertEqual(self.network.call_count, 1)

    def test_safe_same_origin_redirects_are_bounded_and_checked_again(self):
        with mock.patch(
            "generator.sources.fetcher.allowed", return_value=True
        ) as allowed:
            self.network.side_effect = [
                source_response(status=301, location="/docs/security-policy-v2/"),
                source_response("<main>Detailed policy.</main>"),
            ]
            actual = fetcher.fetch_source(self.supporting(), "test", 1000)
        self.assertTrue(actual["ok"])
        self.assertEqual(actual["cite"], self.supporting()["cite"])
        self.assertEqual(allowed.call_count, 2)
        self.assertEqual(self.dns.call_count, 2)
        with mock.patch("generator.sources.fetcher.allowed", return_value=True):
            self.network.reset_mock()
            self.network.side_effect = None
            self.network.return_value = source_response(
                status=302, location="/docs/security-policy-v2/"
            )
            actual = fetcher.fetch_source(self.supporting(), "test", 1000)
        self.assertFalse(actual["ok"])
        self.assertIn("related_redirect_limit", actual["reason"])
        self.assertEqual(self.network.call_count, 3)

    def test_robots_disallow_or_unavailable_policy_blocks_support_fetch(self):
        for result in (
            source_response("User-agent: *\nDisallow: /docs/"),
            source_response(status=503),
        ):
            with self.subTest(result=result):
                fetcher._robots_cache.clear()
                self.network.reset_mock()
                self.network.side_effect = None
                self.network.return_value = result
                actual = fetcher.fetch_source(self.supporting(), "test", 1000)
                self.assertFalse(actual["ok"])
                self.assertIn("robots_disallow", actual["reason"])
                self.assertEqual(self.network.call_count, 1)
                self.assertTrue(self.network.call_args.args[0].endswith("/robots.txt"))

    def test_robots_redirect_cannot_trigger_private_request(self):
        self.network.side_effect = None
        self.network.return_value = source_response(
            status=302, location="http://127.0.0.1/robots.txt"
        )
        actual = fetcher.fetch_source(self.supporting(), "test", 1000)
        self.assertFalse(actual["ok"])
        self.assertIn("robots_disallow", actual["reason"])
        self.assertEqual(self.network.call_count, 1)


class SourceXMLTest(unittest.TestCase):
    def test_new_and_legacy_rfc_page_breaks_keep_normalized_evidence(self):
        source = "A page.\fNext page.\vDetails."
        wrapped = (
            "<document><source_url>https://www.rfc-editor.org/rfc/rfc8077</source_url>"
            "<document_content><![CDATA[%s]]></document_content></document>"
        )
        for content in (source, as_cdata(source)):
            indexed = source_sections(wrapped % content)
            self.assertEqual(
                re.sub(r"\s+", " ", indexed[0]["content"]),
                re.sub(r"\s+", " ", source),
            )
        ET.fromstring(wrapped % as_cdata(source))

    def test_invalid_non_whitespace_controls_still_fail(self):
        with self.assertRaises(ReviewContractError):
            source_sections("<document>broken\x00</document>")

    def test_cdata_terminator_keeps_original_text(self):
        value = "text ]]> next"
        self.assertEqual(
            ET.fromstring("<root><![CDATA[" + as_cdata(value) + "]]></root>").text,
            value,
        )
