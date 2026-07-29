---
title: "PostgreSQL 문서 빌드를 위한 도구 세트와 플랫폼별 설치"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-30 07:25:08 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-07-30
sources:
  - https://www.postgresql.org/docs/current/docguide-toolsets.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
PostgreSQL 공식 문서는 DocBook 형식의 소스로 작성되어 있으며, 이를 HTML이나 PDF와 같은 읽을 수 있는 형식으로 변환하려면 특정 도구 세트가 필요하다. 이 글은 문서 빌드에 필수적인 각 도구의 역할과, Fedora/RHEL, FreeBSD, Debian, macOS와 같은 주요 운영체제별로 해당 도구를 설치하는 방법을 개념적으로 설명한다. `configure` 스크립트가 이 도구들을 어떻게 감지하는지 이해하는 것은 빌드 환경을 올바르게 구성하는 데 핵심적이다.

### 문서 빌드 도구 세트의 구성 요소
PostgreSQL 문서 처리를 위해 필요한 핵심 도구들은 다음과 같은 역할을 담당한다.

**DocBook DTD**는 문서 구조를 정의하는 규칙 집합이다. **XML 버전의 DocBook 4.5**를 반드시 사용해야 하며, 이전이나 이후 버전은 호환되지 않는다. SGML 변형은 사용할 수 없다.

**DocBook XSL Stylesheets**는 DocBook 소스를 HTML 등의 다른 형식으로 변환하는 처리 지침(XSLT)을 포함한다. 최소 1.77.0 버전이 필요하지만, 최상의 결과를 위해 사용 가능한 최신 버전을 사용하는 것이 권장된다.

**Libxml2 (xmllint)**는 XML 처리를 위한 라이브러리와 도구다. `xmllint`는 PostgreSQL 코드 빌드 시에도 사용되므로 많은 개발자에게 이미 설치되어 있을 수 있지만, 별도의 서브패키지로 설치해야 할 경우도 있다.

**Libxslt (xsltproc)**는 XSLT 스타일시트를 사용해 XML을 다른 형식으로 변환하는 **XSLT 프로세서** 프로그램이다.

**FOP**는 XML을 PDF 형식으로 변환하는 프로그램이다. 이 도구는 **문서를 PDF 형식으로 빌드하고자 할 때만 필요**하다.

### 플랫폼별 설치 명령어의 패턴
공식 문서는 여러 주요 운영체제 계열에 대해 패키지 관리자를 통한 설치 명령을 제시한다. 각 플랫폼별 패키지 이름에는 차이가 있지만, 필요한 도구 세트(DocBook DTD, 스타일시트, 변환기)를 설치한다는 공통된 목적을 가진다.

| 플랫폼 (파생 계열) | 패키지 관리자 | 설치 명령어 (핵심 패키지) |
| :--- | :--- | :--- |
| Fedora, RHEL 및 파생 배포판 | `yum` | `docbook-dtds docbook-style-xsl libxslt fop` |
| FreeBSD | `pkg` | `docbook-xml docbook-xsl libxslt fop` |
| Debian GNU/Linux | `apt-get` | `docbook-xml docbook-xsl libxml2-utils xsltproc fop` |
| macOS (MacPorts) | `port` | `docbook-xml docbook-xsl-nons libxslt fop` |
| macOS (Homebrew) | `brew` | `docbook docbook-xsl libxslt fop` |

FreeBSD의 경우, 문서 `doc` 디렉터리에서 빌드할 때는 `gmake`를 사용해야 한다. 제공된 Makefile이 FreeBSD의 기본 `make`에 적합하지 않기 때문이다.

macOS에서 Homebrew를 사용할 때는 **`XML_CATALOG_FILES` 환경 변수 설정**이 중요하다. 이 변수가 설정되지 않으면 `xsltproc`가 네트워크에서 DTD를 불러오려 시도하다 실패하는 오류를 발생시킨다. Intel 기반 Mac에서는 `/usr/local/etc/xml/catalog`를, Apple Silicon 기반 Mac에서는 `/opt/homebrew/etc/xml/catalog`를 값으로 설정해야 한다.

### configure 스크립트를 통한 도구 감지
PostgreSQL 프로그램 자체를 빌드할 때와 마찬가지로, 문서를 빌드하기 전에 반드시 `configure` 스크립트를 실행해야 한다. 스크립트 실행 결과 끝부분에서 다음과 같은 도구 감지 메시지를 확인할 수 있다.

```
checking for xmllint... xmllint
checking for xsltproc... xsltproc
checking for fop... fop
checking for dbtoepub... dbtoepub
```

`xmllint`나 `xsltproc`가 발견되지 않으면 **어떤 형식의 문서도 빌드할 수 없다**. `fop`는 PDF 형식 빌드 시에만, `dbtoepub`는 EPUB 형식 빌드 시에만 각각 필요하다. 필요한 경우, `./configure ... XMLLINT=/opt/local/bin/xmllint ...`와 같은 형식으로 `configure`에 도구의 경로를 직접 알려줄 수 있다.

Meson 빌드 시스템을 선호하는 경우에는 `meson setup`을 실행한 후 해당 문서화 섹션을 참조해야 한다.

### 주의사항 및 선택 기준
*   **DocBook 버전 고정**: DocBook DTD는 **반드시 버전 4.5를 사용해야 한다**. 호환성을 위해 버전을 엄격히 준수하는 것이 중요하다.
*   **도구의 선택적 필요성**: 모든 도구가 항상 필요한 것은 아니다. **FOP는 PDF 출력을 원할 때만**, **dbtoepub는 EPUB 출력을 원할 때만** 설치하면 된다.
*   **macOS 환경 변수**: Homebrew 사용 시 `XML_CATALOG_FILES` 설정을 잊지 말아야 한다. 이는 로컬 카탈로그 파일을 참조하여 네트워크 의존성을 제거하는 핵심 설정이다.
*   **빌드 시스템 차이**: 전통적인 Autotools(`configure`) 방식과 Meson 방식 사이에 문서 빌드 준비 절차가 다르므로 주의해야 한다.

### 정리
PostgreSQL 문서 빌드는 DocBook 4.5 DTD와 XSL 스타일시트, `xmllint`, `xsltproc`를 필수 도구로 요구하며, PDF 출력을 위해선 FOP가 추가로 필요하다. 각 운영체제는 패키지 이름이 다르지만, 동일한 도구 세트를 설치하는 패턴을 보인다. 특히 macOS에서는 환경 변수 설정이 빌드 성공의 관건이 된다. 최종 빌드 전 `configure` 스크립트를 실행하여 모든 필수 도구가 정상적으로 감지되는지 확인하는 것이 표준적인 작업 흐름이다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/docguide-toolsets.html](https://www.postgresql.org/docs/current/docguide-toolsets.html)
