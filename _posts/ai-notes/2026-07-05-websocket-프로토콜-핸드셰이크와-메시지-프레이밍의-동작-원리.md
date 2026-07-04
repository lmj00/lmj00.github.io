---
title: "WebSocket 프로토콜: 핸드셰이크와 메시지 프레이밍의 동작 원리"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-05 03:39:12 +0900
tags: [cs, network, websocket]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-07-05
sources:
  - https://www.rfc-editor.org/rfc/rfc6455
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: WebSocket 프로토콜은 HTTP 업그레이드 핸드셰이크를 통해 양방향 통신 채널을 수립한 후, 경량의 프레이밍 프로토콜을 통해 메시지를 주고받는 메커니즘을 정의한다.

### 개요
WebSocket 프로토콜은 브라우저 기반 애플리케이션이 서버와 양방향 통신을 하기 위한 메커니즘을 제공한다. 기존의 HTTP 폴링이나 롱 폴링과 같은 방식은 여러 TCP 연결을 필요로 하고 각 메시지마다 HTTP 헤더 오버헤드가 발생하는 문제가 있었다. WebSocket은 단일 TCP 연결을 통해 양방향으로 데이터를 전송함으로써 이러한 문제를 해결하며, 기존의 HTTP 인프라(포트 80/443, 프록시, 인증)와의 호환성을 유지하도록 설계되었다.

### 핸드셰이크: HTTP에서 WebSocket으로의 업그레이드
WebSocket 연결은 **Opening Handshake**로 시작한다. 이 핸드셰이크는 HTTP 업그레이드 요청의 형태를 띠어, HTTP 기반 서버 소프트웨어 및 중간자(프록시 등)와 호환될 수 있도록 설계되었다. 이를 통해 단일 포트로 HTTP 클라이언트와 WebSocket 클라이언트를 모두 처리할 수 있다.

클라이언트의 핸드셰이크 요청은 다음과 같은 핵심 헤더를 포함한 HTTP GET 요청이다.
```
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```
*   `Upgrade: websocket`과 `Connection: Upgrade`: 프로토콜을 WebSocket으로 변경하겠다는 의도를 명시한다.
*   `Sec-WebSocket-Key`: 보안을 위한 임의의 16바이트 nonce 값(Base64 인코딩)이다.
*   `Sec-WebSocket-Version`: 사용 중인 프로토콜 버전(13)을 명시한다.

서버는 이 요청을 검증하고, 성공 시 **101 Switching Protocols** 응답으로 회신한다.
```
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```
*   `Sec-WebSocket-Accept`: 클라이언트가 보낸 `Sec-WebSocket-Key` 값에 RFC 6455에 정의된 고정 GUID 문자열("258EAFA5-E914-47DA-95CA-C5AB0DC85B11")을 연결한 후, SHA-1 해시를 계산하고 그 결과를 Base64 인코딩한 값이다. 이 계산을 통해 클라이언트가 유효한 WebSocket 핸드셰이크를 지원함을 확인한다.

![diagram](/assets/diagrams/2026-07-05-websocket-프로토콜-핸드셰이크와-메시지-프레이밍의-동작-원리-1.svg)

핸드셰이크가 성공적으로 완료되면, 프로토콜은 순수한 WebSocket 모드로 전환되어 TCP 연결을 통해 양방향 데이터 전송이 시작된다.

### 데이터 프레이밍: 메시지와 프레임
핸드셰이크 이후의 데이터 전송은 **프레임(Frame)** 단위로 이루어진다. 애플리케이션 관점의 논리적 단위는 **메시지(Message)**이며, 하나의 메시지는 하나 이상의 프레임으로 구성될 수 있다(프래그먼테이션). 프레임은 매우 경량화된 이진 포맷을 사용하여 헤더 오버헤드를 최소화한다.

프레임은 그 용도에 따라 크게 세 가지 유형으로 구분된다.
*   **텍스트 데이터 프레임**: UTF-8로 인코딩된 텍스트 데이터를 운반한다.
*   **이진 데이터 프레임**: 애플리케이션이 해석할 임의의 바이너리 데이터를 운반한다.
*   **제어 프레임(Control Frames)**: 애플리케이션 데이터를 운반하지 않고 프로토콜 수준의 신호를 전달한다. 주요 제어 프레임으로는 연결 종료를 알리는 **Close**, 연결 상태 확인을 위한 **Ping** 및 이에 대한 응답 **Pong**이 있다.

프레임의 기본 구조는 고정된 헤더와 선택적인 페이로드 데이터로 구성된다. 헤더에는 **FIN** 비트(이 프레임이 메시지의 마지막 조각인지 표시), **Opcode**(프레임 유형 지정, 예: 텍스트는 0x1, 이진은 0x2, Close는 0x8), **Mask** 비트(클라이언트→서버 방향 마스킹 여부), 페이로드 길이 등을 나타내는 필드들이 포함된다.

### 보안 고려사항: 마스킹(Masking)
프로토콜은 특별한 보안 조치로 **클라이언트에서 서버로 보내는 모든 데이터 프레임에 마스킹을 적용**하도록 요구한다. 프레임 헤더의 `Mask` 비트가 1로 설정되고, 32비트 마스킹 키(Masking-key)가 함께 전송된다. 실제 페이로드 데이터는 이 키를 사용해 특정 알고리즘으로 XOR 연산되어 '마스크' 처리된다.

이 마스킹의 주된 목적은 악성 코드가 배포된 캐시 서버나 보안 검사가 약한 프록시를 속이는 공격(인프라 공격)을 완화하는 데 있다. 서버로 향하는 트래픽이 예측 불가능한 패턴을 가지게 만들어, 이러한 중간자들이 프레임 내용을 잘못 해석하는 것을 어렵게 만든다. 반대로, 서버에서 클라이언트로 보내는 프레임은 마스킹이 적용되지 않는다.

### 연결 종료 핸드셰이크
WebSocket 연결은 **Closing Handshake**를 통해 정상적으로 종료된다. 한쪽(클라이언트 또는 서버)이 **Close 제어 프레임**을 전송하면, 수신 측은 반드시 동일한 Close 프레임으로 응답해야 한다. 이 핸드셰이크가 완료된 후에야 TCP 연결이 닫힌다. Close 프레임에는 연결 종료 이유를 나타내는 숫자 형태의 **상태 코드(Status Code)**와 짧은 텍스트 **이유(Reason)**를 포함할 수 있다.

### 설계 철학과 한계
WebSocket 프로토콜의 설계 철학은 기존 HTTP 생태계 위에서 동작하는 것이다. 이는 장점이자 복잡성을 동반한다. 표준 HTTP 포트를 사용하고 프록시를 인식하도록 만들어 배포성을 높였지만, 반대로 이로 인해 핸드셰이크가 복잡해지고(HTTP 업그레이드), 보안 조치(마스킹)가 필요해졌다. RFC는 이 프로토콜이 반드시 HTTP에 제한되는 것은 아니며, 향후 구현에서는 전용 포트를 사용한 더 간단한 핸드셰이크도 가능하다고 언급하고 있다.

### 정리
WebSocket은 효율적인 실시간 양방향 통신을 위한 프로토콜이다. 핸드셰이크는 HTTP 업그레이드 메커니즘을 활용해 기존 인프라와의 호환성을 보장한다. 데이터 전송은 오버헤드가 적은 이진 프레이밍 방식을 사용하며, 메시지는 하나 이상의 프레임으로 조각낼 수 있다. 보안을 위해 클라이언트→서버 방향 트래픽에 마스킹을 적용하며, 제어 프레임을 통해 연결 상태 관리와 정상 종료 절차를 정의한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.rfc-editor.org/rfc/rfc6455](https://www.rfc-editor.org/rfc/rfc6455)
