---
title: "PostgreSQL 소스 코드 획득 방법"
layout: post
categories: ai-notes
type: study-note
date: 2026-09-01 09:28:07 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-09-01
sources:
  - https://www.postgresql.org/docs/current/install-getsource.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
PostgreSQL을 소스 코드로 설치하려면 먼저 공식 웹사이트에서 해당 버전의 소스 아카이브를 다운로드해야 한다. 이는 패키지 관리자를 통한 설치와 달리 최신 개발 버전 사용, 특정 컴파일 옵션 지정, 내부 구조 학습 등에 유용하다. 본 글에서는 공식 문서에 명시된 소스 코드 획득 경로와 기본적인 압축 해제 절차를 개념적으로 살펴본다.

### 소스 코드 다운로드
PostgreSQL 프로젝트는 공식 웹사이트의 다운로드 섹션(`https://www.postgresql.org/ftp/source/`)에서 각 릴리스 버전의 소스 코드를 배포한다. 사용자는 원하는 버전의 `postgresql-{version}.tar.gz` 또는 `postgresql-{version}.tar.bz2` 아카이브 파일을 선택하여 다운로드할 수 있다. 이는 표준화된 소스 배포 방식으로, 특정 버전의 정확한 코드 스냅샷을 제공한다.

### 압축 해제 및 디렉토리 구조
다운로드한 아카이브 파일은 `tar` 명령어를 사용해 현재 작업 디렉토리에 압축을 해제한다. 예를 들어 `.tar.bz2` 형식의 경우 `tar xf postgresql-{version}.tar.bz2` 명령을 실행한다. 이 작업은 `postgresql-{version}`이라는 이름의 새 디렉토리를 생성하며, 여기에 PostgreSQL의 전체 소스 코드가 포함된다. 이후의 모든 빌드 및 설치 절차는 이 디렉토리 내부에서 진행된다.

### Git을 통한 대체 방법
소스 아카이브 다운로드 외에도, **Git** 버전 관리 시스템을 통해 소스 코드를 획득할 수 있다. 이 방법은 최신 개발 브랜치(`devel`)를 추적하거나, 특정 커밋 시점의 코드를 체크아웃하는 등 보다 유연한 접근이 가능하다. 공식 문서는 이에 대한 상세한 안내를 별도 섹션(Section I.1)에서 제공한다.

### 정리
PostgreSQL 소스 설치의 첫 단계는 공식 FTP 사이트에서 원하는 버전의 압축 파일을 다운로드하고 압축을 해제하는 것이다. 이렇게 생성된 `postgresql-{version}` 디렉토리가 이후 빌드 작업의 루트가 된다. Git을 이용하면 개발 버전을 포함한 다양한 코드 베이스에 접근할 수 있는 대체 경로도 존재한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/install-getsource.html](https://www.postgresql.org/docs/current/install-getsource.html)
