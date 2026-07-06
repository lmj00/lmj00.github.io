---
title: "RabbitMQ Stream Plugin: 전용 바이너리 프로토콜과 구성"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-07 07:16:36 +0900
tags: [rabbitmq]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-07-07
sources:
  - https://www.rabbitmq.com/docs/stream
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: RabbitMQ Stream Plugin은 영속적이고 복제된 append-only 로그인 스트림을 전용 바이너리 프로토콜로 사용할 수 있게 해주며, TCP 리스너, 하트비트, 흐름 제어, TLS 등을 구성할 수 있다.

### 개요
RabbitMQ의 **Stream Plugin**은 **스트림(Stream)**이라는 데이터 구조와 상호작용하기 위한 전용 모듈이다. 스트림은 영속적이고 복제된 **append-only 로그**로, 메시지를 소비해도 삭제되지 않는(non-destructive) 소비자 의미론을 가진다. 이 플러그인을 사용하면 기존 AMQP 0.9.1 큐처럼 사용할 수도 있지만, 더 효율적으로 **전용 바이너리 프로토콜**과 해당 클라이언트 라이브러리를 통해 스트림에 접근할 수 있다. 이를 통해 높은 처리량과 낮은 지연 시간을 목표로 하는 데이터 흐름을 구현할 수 있다.

### 스트림 플러그인의 역할과 클라이언트
스트림 플러그인의 주요 역할은 RabbitMQ 서버에 새로운 바이너리 프로토콜 리스너를 활성화하는 것이다. 이 프로토콜은 스트림의 리더와 복제본 위치(토폴로지)를 클라이언트가 발견하고, 데이터 지역성과 효율성을 고려해 적절한 노드에 연결할 수 있도록 설계되었다.

RabbitMQ 코어 팀에서 공식 지원하는 클라이언트 라이브러리는 Java, Go(Golang), .NET, Rust, Python(rstream)용이 있다. 그 외에도 NodeJS, C++, C, Elixir, Erlang용 커뮤니티 클라이언트가 존재한다. 성능 테스트에는 **Stream PerfTest** 도구를 사용할 수 있다.

플러그인은 RabbitMQ 배포판에 포함되어 있으며, 다음 명령어로 활성화해야 클라이언트 연결이 가능해진다.
```bash
rabbitmq-plugins enable rabbitmq_stream
```

### 네트워크 및 연결 구성
**TCP 리스너**는 기본적으로 모든 인터페이스의 **5552번 포트**에서 수신하며, 기본 인증 정보는 `guest`/`guest`이다. `rabbitmq.conf` 파일에서 리스너의 IP와 포트를 지정할 수 있다.

```ini
stream.listeners.tcp.1 = 127.0.0.1:5552
stream.listeners.tcp.2 = ::1:5552
```

`stream.tcp_listen_options` 접두사를 사용해 TCP 백로그, 송수신 버퍼 크기, TCP Keepalive, Nagle 알고리즘(`nodelay`) 등의 저수준 네트워크 옵션을 튜닝할 수 있다. 이는 일시적인 네트워크 정체나 서버 흐름 제어로 인한 오류를 줄이는 데 도움이 된다.

**하트비트 타임아웃**은 피어 연결이 끊어진 것으로 간주하기까지의 시간이다. 기본값은 60초이며, `stream.heartbeat`로 설정할 수 있다. 너무 낮은 값(5초 미만)은 일시적인 네트워크 혼잡으로 인한 **오탐(false positive)**을 유발할 수 있으므로, 5~20초 사이의 값을 선택하는 것이 대부분의 환경에 적합하다.

### 발행자 및 소비자 흐름 제어
빠른 발행자가 브로커의 처리 능력을 압도하는 것을 방지하기 위해 **흐름 제어(Flow Control)** 메커니즘이 존재한다. 각 연결은 브로커가 확인(confirm)하기 전까지 허용되는 미확인 메시지의 최대 개수(`initial_credits`, 기본값 50,000)를 가진다. 이 한도에 도달하면 연결이 차단(block)되며, 지정된 수의 메시지가 확인되면(`credits_required_for_unblocking`, 기본값 12,500) 차단이 해제된다. 이 설정은 **발행자에만 적용**되며, 높은 값은 처리량을 높이지만 메모리 사용량도 증가시킨다.

소비자의 경우 **소비자 크레딧 흐름(Consumer Credit Flow)** 메커니즘이 메시지 전달 속도를 제어한다. 소비자는 구독(subscription)을 생성할 때 초기 크레딧을 제공한다. 하나의 크레딧은 브로커가 소비자에게 보낼 수 있는 **청크(chunk)** 단위의 메시지 배치를 의미한다. 브로커는 청크를 전달할 때마다 크레딧을 하나 차감하며, 크레딧이 0이 되면 메시지 전송을 중지한다. 따라서 소비자는 자신의 처리 속도에 맞춰 지속적으로 새로운 크레딧을 제공해야 연속적인 메시지 흐름을 유지할 수 있다. 이 메커니즘은 소비자가 과부하되거나 유휴 상태에 빠지는 것을 방지한다.

### 고급 구성: Advertised Host/Port와 TLS
클라이언트가 스트림 토폴로지를 발견할 때 브로커가 반환하는 호스트와 포트 정보는 `stream.advertised_host`와 `stream.advertised_port`로 오버라이드할 수 있다. 이는 클라이언트와 브로커 클러스터 사이에 프록시가 있거나 컨테이너 환경에서 실행될 때 필요하다.

**TLS**를 활성화하려면 먼저 브로커에 TLS를 구성해야 한다. 그 후 `stream.listeners.ssl.*` 설정 키를 사용해 TLS 리스너를 추가한다. TLS 리스너는 기본 RabbitMQ 서버 인증서와 키를 사용한다. 평문 TCP 리스너를 비활성화하고 TLS만 사용하도록 구성할 수도 있다.

```ini
stream.listeners.tcp = none
stream.listeners.ssl.1 = 5551
```

TLS 연결을 위한 advertised 정보는 `advertised_tls_host`와 `advertised_tls_port`로 별도 설정할 수 있어, 내부와 외부 엔드포인트를 다르게 노출하는 것이 가능하다.

프로토콜의 최대 프레임 크기는 기본값이 1MiB이며, `stream.frame_max` 설정(바이트 단위)으로 증가시킬 수 있다.

### 정리
RabbitMQ Stream Plugin은 전용 바이너리 프로토콜을 통해 고성능, 영속적 로그 기반 메시징을 제공한다. TCP/하트비트 설정으로 연결 안정성을, 발행자 흐름 제어와 소비자 크레딧 메커니즘으로 리소스 관리를 구성할 수 있다. Advertised 호스트/포트와 TLS 지원은 복잡한 네트워크 환경(프록시, 컨테이너)에서의 배포 유연성을 높인다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.rabbitmq.com/docs/stream](https://www.rabbitmq.com/docs/stream)
