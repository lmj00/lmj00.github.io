---
title: "Daytime Protocol (RFC 867) — 입력을 무시하고 현재 시각만 돌려주는 진단용 프로토콜"
layout: post
interactive_design: true
categories: ai-notes
type: study-note
date: 2026-11-15 09:51:55 +0900
tags: [cs, network, rfc]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-11-15
sources:
  - https://www.rfc-editor.org/rfc/rfc867
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: RFC 867이 정의하는 Daytime Protocol은 TCP 또는 UDP 포트 13으로 현재 날짜와 시간을 ASCII 문자열로 반환하는 디버깅·측정용 표준 서비스다. 입력은 무시하고 출력만 존재하는 가장 단순한 형태의 프로토콜이다.

### 개요
Daytime Protocol은 RFC 867로 표준화된 ARPA 인터넷 표준으로, 이를 구현하기로 선택한 호스트는 해당 표준을 채택·구현할 것이 기대된다. 이 서비스는 디버깅과 측정에 유용한 도구로 설계되었다. 핵심 동작은 매우 단순하다. 입력 내용과 무관하게 현재 날짜와 시간을 문자 문자열로 보내는 것이 전부다.

### 동작 방식
프로토콜은 전송 계층에 따라 두 가지 변형으로 정의된다. 두 경우 모두 포트 13을 사용하며, 클라이언트가 보낸 데이터는 전혀 해석하지 않는다는 공통점이 있다.

#### TCP 기반 서비스
TCP 기반 daytime 서비스는 연결 기반 애플리케이션으로 정의된다. 서버는 TCP 포트 13에서 연결을 기다리며, 연결이 수립되면 현재 날짜와 시간을 ASCII 문자열로 연결에 실어 보낸다. 이때 수신된 데이터는 버려진다. 문자열을 보낸 뒤에는 연결을 닫는다.

#### UDP 기반 서비스
UDP 기반 서비스는 데이터그램 기반 애플리케이션으로 정의된다. 서버는 UDP 포트 13에서 데이터그램을 기다리며, 데이터그램이 도착하면 현재 날짜와 시간을 ASCII 문자열로 담은 응답 데이터그램을 보낸다. 수신 데이터그램의 내용은 무시된다.



{% raw %}
<figure class="ai-scene"><figcaption>같은 포트 13인데 응답 경로는 왜 다를까? · 설명용 시각화</figcaption><iframe class="ai-scene-frame" src="/assets/generated/designs/2026-11-15-daytime-protocol-rfc-867-입력을-무시하고-현재-시각만-돌려주는-진단용-프로토콜-591ac576991e5e9d-1.html" title="같은 포트 13인데 응답 경로는 왜 다를까?" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy" height="560"></iframe><p class="ai-scene-summary">RFC 867은 TCP와 UDP 두 가지 daytime 서비스를 정의한다. 공통 규칙은 포트 13에서 클라이언트 입력을 무시하고 현재 시각을 ASCII 문자열로 보내는 것이다. 차이는 응답 경로다. TCP는 연결을 수립하고 문자열을 보낸 뒤 연결을 닫고, UDP는 데이터그램이 도착하면 응답 데이터그램 하나로 답한다.</p></figure>
{% endraw %}

### 응답 형식
RFC는 daytime 응답의 특정 문법을 강제하지 않는다. 다만 ASCII 인쇄 문자, 공백, 캐리지 리턴, 라인 피드로 제한할 것을 권장하며, 응답은 한 줄이어야 한다. RFC에는 널리 쓰이는 두 가지 형식이 예시와 함께 소개되어 있다.

| 형식 | 예시 |
| --- | --- |
| `Weekday, Month Day, Year Time-Zone` | `Tuesday, February 22, 1982 17:37:43-PST` |
| SMTP에서 쓰는 `dd mmm yy hh:mm:ss zzz` | `02 FEB 82 07:59:01 PST` |

### 정리
Daytime Protocol은 현재 시각을 사람이 읽을 수 있는 ASCII 문자열로 반환하는 최소한의 서비스다. TCP와 UDP 양쪽 모두 포트 13을 사용하며, 입력은 무시되고 출력만 존재한다. 사람이 읽기 좋은 형식이라는 특성 때문에 기계가 직접 해석할 시간 값이 필요할 때는 RFC 868의 Time Protocol을 사용하라는 안내가 RFC 867에 명시되어 있다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.rfc-editor.org/rfc/rfc867](https://www.rfc-editor.org/rfc/rfc867)
