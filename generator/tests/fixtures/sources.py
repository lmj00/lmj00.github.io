"""Reusable fictional inputs and test doubles; never test cases."""

from __future__ import annotations

from unittest import mock

ROOT_DOCUMENT = {
    "fetch": "https://kubernetes.io/docs/concepts/security/",
    "cite": "https://kubernetes.io/docs/concepts/security/",
}


RAW_DOCUMENT = {
    "fetch": "https://raw.githubusercontent.com/org/docs/main/docs/security.md",
    "cite": "https://docs.example.com/docs/security",
}


def source_response(text="", status=200, location=None):
    return mock.Mock(
        status_code=status,
        text=text,
        headers={"Location": location} if location else {},
    )


def root_document(links=None):
    return {
        **ROOT_DOCUMENT,
        "ok": True,
        "text": "# Kubernetes security\nOfficial security overview.",
        "reason": "ok",
        "related_sources": links or [],
    }


def link(path, label, heading="", context=""):
    url = "https://kubernetes.io" + path
    return {
        "fetch": url,
        "cite": url,
        "label": label,
        "heading": heading,
        "context": context,
    }
