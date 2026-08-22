---
title: "RabbitMQ URI 쿼리 파라미터를 통한 연결 세부 설정"
layout: post
categories: ai-notes
type: study-note
date: 2026-08-23 06:23:44 +0900
tags: [rabbitmq]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-08-23
sources:
  - https://www.rabbitmq.com/docs/uri-query-parameters
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: RabbitMQ 클라이언트 연결 URI에 쿼리 파라미터를 추가하여 TLS, 인증, 하트비트, 타임아웃 등의 연결 속성을 세밀하게 제어할 수 있다. 이 기능은 Erlang 클라이언트와 이를 사용하는 Federation, Shovel 플러그인에서 지원된다.

### 개요
RabbitMQ 클라이언트는 연결을 설정할 때 사용하는 URI에 쿼리 파라미터를 추가할 수 있다. 이 파라미터들을 통해 TLS 설정, 인증 메커니즘, 네트워크 타임아웃, 하트비트 간격 등 연결의 세부 동작을 명시적으로 제어할 수 있다. 이는 공식 URI 스펙과 TLS 가이드에 대한 보다 실용적인 설명으로, 현재 Erlang 클라이언트에서만 지원되며, 내부적으로 Erlang 클라이언트를 사용하는 Federation 및 Shovel 플러그인에서도 동일한 파라미터를 사용할 수 있다.

### 쿼리 파라미터의 기본 사용법
쿼리 파라미터는 일반적인 웹 URL과 동일한 방식(`?key=value&key2=value2`)으로 URI에 추가한다. 모든 파라미터는 생략 가능하며, 생략 시 클라이언트가 적절한 기본값을 선택한다.

예를 들어, `amqp://myhost?heartbeat=5&connection_timeout=10000`라는 URI는 다음과 같은 의미를 가진다.
*   `amqp://myhost`: 암호화되지 않은 네트워크 연결을 `myhost` 호스트로 설정한다.
*   `heartbeat=5`: 협상할 하트비트 간격을 5초로 설정한다.
*   `connection_timeout=10000`: TCP 연결 수립 대기 시간을 10,000밀리초(10초)로 설정한다.

### 주요 쿼리 파라미터 설명
다음은 지원되는 주요 쿼리 파라미터와 그 역할을 정리한 표다.

| 파라미터 이름 | 설명 |
| :--- | :--- |
| `cacertfile`, `certfile`, `keyfile` | 클라이언트 측 SSL 인증서를 서버에 제시하기 위한 파일 경로. `amqps` 스킴(암호화 연결)에서만 사용된다. |
| `password` | `keyfile`으로 지정된 개인 키 파일의 암호. 키 파일이 암호로 보호된 경우에만 사용된다. |
| `verify`, `server_name_indication` | 서버의 x509(TLS) 인증서 검증을 구성한다. `amqps` 스킴에서만 사용되며, **두 값을 모두 사용하는 것이 강력히 권장된다.** |
| `auth_mechanism` | 서버와 협상할 SASL 인증 메커니즘을 지정한다. `?auth_mechanism=plain&auth_mechanism=amqplain`과 같이 여러 번 지정하여 복수의 메커니즘을 나열할 수 있다. |
| `heartbeat` | 서버와 협상할 하트비트 타임아웃 값(초 단위 정수)을 지정한다. |
| `connection_timeout` | 서버에 대한 TCP 연결을 수립하기 위해 대기할 시간(밀리초 단위 정수)을 지정한다. |
| `channel_max` | 해당 연결에서 허용할 최대 채널 수를 지정한다. |

### TLS 연결 구성 예시
TLS를 사용하는 암호화 연결(`amqps`)에서는 인증서 파일 경로와 검증 방식을 파라미터로 지정한다.

**TLS 피어 검증 활성화 예시 (`verify=verify_peer`)**
```ini
amqps://myhost?cacertfile=/path/to/ca_certificate.pem
  &certfile=/path/to/client_certificate.pem
  &keyfile=/path/to/client_key.pem
  &verify=verify_peer
  &server_name_indication=myhost
```
이 구성은 서버 인증서의 신뢰 체인을 검증(`verify_peer`)하고, 서버 인증서의 `CN` 값을 호스트명 `myhost`와 대조하여 검증(`server_name_indication`)한다.

**TLS 피어 검증 비활성화 예시 (`verify=verify_none`)**
```ini
amqps://myhost?cacertfile=/path/to/ca_certificate.pem
  &certfile=/path/to/client_certificate.pem
  &keyfile=/path/to/client_key.pem
  &verify=verify_none
  &server_name_indication=myhost
```
이 구성은 암호화는 사용하지만 서버 인증서에 대한 클라이언트 측 검증을 수행하지 않는다.

### 전역 구성과의 관계
TLS 옵션은 URI 쿼리 파라미터 외에도, Erlang 구성 파일(`advanced.config`)에서 `amqp_client.ssl_options` 키를 사용하여 **전역적으로** 지정할 수도 있다.
```erlang
{amqp_client, [
    {ssl_options, [
        {cacertfile, "path-to-ca-certificate"},
        {certfile, "path-to-certificate"},
        {keyfile, "path-to-keyfile"},
        {verify, verify_peer}
    ]}
]}.
```
전역 구성과 URI 파라미터 구성이 병합될 때는 **URI 파라미터의 값이 우선순위를 가진다.** 전역 구성은 해당 노드의 모든 발신 RabbitMQ Erlang 클라이언트 연결(Federation, Shovel 등 내부적으로 클라이언트를 사용하는 플러그인 포함)에 영향을 미친다.

### 정리
*   RabbitMQ 연결 URI의 쿼리 파라미터는 연결 동작을 세부 조정하는 선언적 인터페이스다.
*   TLS 설정, 인증, 하트비트, 타임아웃, 채널 제한 등 핵심 연결 속성을 제어할 수 있다.
*   이 기능은 Erlang 클라이언트 및 이를 기반으로 하는 플러그인(Federation, Shovel)에서 사용 가능하다.
*   TLS 관련 파라미터는 전역 구성과 병합 가능하며, URI에 명시된 값이 더 높은 우선순위를 가진다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.rabbitmq.com/docs/uri-query-parameters](https://www.rabbitmq.com/docs/uri-query-parameters)
