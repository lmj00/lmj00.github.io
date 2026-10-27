---
title: "PostgreSQL 공식 튜토리얼(Part I)의 구성과 학습 흐름"
layout: post
interactive_design: true
categories: ai-notes
type: study-note
date: 2026-10-27 09:30:34 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-10-27
sources:
  - https://www.postgresql.org/docs/current/tutorial.html
  - https://www.postgresql.org/docs/10/tutorial.html
  - https://www.postgresql.org/docs/11/tutorial.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: PostgreSQL 공식 문서의 Part I 튜토리얼은 관계형 데이터베이스 개념과 SQL을 처음 접하는 독자를 위한 실습 중심 입문서로, 환경 준비 → SQL 기초 → 고급 기능 순으로 진행된다.

### 개요
PostgreSQL 공식 문서의 Part I "Tutorial"은 PostgreSQL, 관계형 데이터베이스 개념, SQL 언어 중 하나라도 처음 접하는 독자를 대상으로 한 입문 파트다. 문서는 일반적인 컴퓨터 사용 지식만 가정하며 Unix나 프로그래밍 경험이 없어도 따라갈 수 있다고 설명한다. 이 파트는 PostgreSQL 시스템의 중요한 측면을 직접 경험하게 하는 데 목적을 두며, 해당 주제를 완전하게 다루려는 시도는 아니라고 명시한다.

### 세 단계로 이루어진 구성
튜토리얼의 목차는 `Getting Started`, `The SQL Language`, `Advanced Features` 세 장으로 구성된다.

| 장 | 초점 | 포함 내용 |
|---|---|---|
| 1. Getting Started | 설치와 기본 환경 | Installation, Architectural Fundamentals, Creating a Database, Accessing a Database |
| 2. The SQL Language | SQL의 기초 학습 | Introduction, Concepts, Creating a New Table, Populating a Table With Rows, Querying a Table, Joins Between Tables, Aggregate Functions, Updates, Deletions |
| 3. Advanced Features | 기본 SQL을 넘어선 기능 | Introduction, Views, Foreign Keys, Transactions, Window Functions, Inheritance, Conclusion |

흐름을 보면 먼저 설치와 아키텍처 기초를 익히고 데이터베이스를 만들고 접근하는 방법을 배운다. 다음 장에서는 테이블 생성과 데이터 입력, 조회, 조인, 집계, 수정, 삭제로 이어지는 SQL 언어를 다루며, 마지막 장에서는 뷰, 외래 키, 트랜잭션, 윈도우 함수, 상속 같은 고급 기능을 소개한다.

### 튜토리얼 이후의 학습 경로
튜토리얼은 입문용 실습에 머무르기 때문에, 이후에는 목적에 따라 다른 파트를 읽도록 안내한다. Part II는 SQL 언어에 대한 더 공식적인 이해를 제공하고, Part IV는 PostgreSQL로 애플리케이션을 개발하는 방법을 다룬다. 자신의 PostgreSQL 설치를 직접 구축하고 관리하는 사람은 Part III도 함께 읽어야 한다.

### 버전별 참고
이 튜토리얼의 목차 구성은 PostgreSQL 10, 11, 18 공식 문서에서 동일하게 유지된다. 다만 PostgreSQL 10과 11 문서는 지원이 종료된 버전으로 표시되며, 현재 문서 버전은 PostgreSQL 18이다. 2026년 10월 15일에 PostgreSQL 19 RC 1이 발표되어 개발 버전(19/devel) 문서도 제공되고 있다.



{% raw %}
<figure class="ai-scene"><figcaption>버전별 문서 상태는 달라도 목차는 같다 · 설명용 시각화</figcaption><iframe class="ai-scene-frame" src="/assets/generated/designs/2026-10-27-postgresql-공식-튜토리얼-part-i-의-구성과-학습-흐름-dc9355c7b70c5bde-1.html" title="버전별 문서 상태는 달라도 목차는 같다" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy" height="560"></iframe><p class="ai-scene-summary">문서 뷰어로 세 버전의 튜토리얼 페이지를 비교한다. PostgreSQL 18은 현재 지원 버전으로, 10과 11은 지원 종료(unsupported) 버전으로 표시된다. 버전 상태 배너와 안내 문구만 바뀌고 Part I 튜토리얼 목차 구성은 그대로다.</p></figure>
{% endraw %}

### 정리
PostgreSQL 공식 튜토리얼은 설치와 기본 환경, SQL 언어, 고급 기능의 세 단계로 구성된 실습 중심 입문서다. 별도의 프로그래밍 경험을 요구하지 않으며, PostgreSQL과 관계형 데이터베이스, SQL을 처음 접하는 독자에게 핵심 개념을 직접 경험하게 한다. 튜토리얼 자체는 완전한 참고서가 아니므로, 더 깊이 있는 학습은 SQL 언어, 애플리케이션 개발, 서버 관리에 해당하는 후속 파트를 읽는 것으로 이어진다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/tutorial.html](https://www.postgresql.org/docs/current/tutorial.html)
> - [https://www.postgresql.org/docs/10/tutorial.html](https://www.postgresql.org/docs/10/tutorial.html)
> - [https://www.postgresql.org/docs/11/tutorial.html](https://www.postgresql.org/docs/11/tutorial.html)
