---
title: "Kubernetes에 RabbitMQ를 직접 배포하기: 핵심 가이드"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-03
tags: [rabbitmq]
generated_by: "openrouter:openai/gpt-oss-20b:free"
generated_at: 2026-07-03
sources:
  - https://www.rabbitmq.com/docs/install-kubernetes-diy
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
이 가이드는 Operator나 Helm 차트 없이 Kubernetes에 RabbitMQ를 배포하는 방법을 설명한다. 공식 문서에서는 이 방식이 **강력히 권장되지 않는다**는 점을 강조하며, 대신 Operator 기반 배포를 권장한다. 그러나 특정 상황에서 직접 배포가 필요할 경우, 핵심 구성 요소와 설정 항목을 명확히 이해해야 한다.

## StatefulSet 사용
RabbitMQ는 상태를 갖는 애플리케이션이며, 호스트명이 변하면 클러스터가 불안정해진다. 따라서 **StatefulSet**을 사용해야 한다.  
StatefulSet은 각 파드에 고유한 네트워크 ID를 부여하고, CoreDNS 캐시 타임아웃을 30초에서 5~10초로 낮추는 것이 필요하다. 만약 CoreDNS 설정을 바꾸기 어려우면, init 컨테이너를 이용해 30초 지연을 주는 방법도 있다.

## Persistent Volume 활용
RabbitMQ는 데이터를 저장하므로 **Persistent Volume**이 필수다. 테스트 파이프라인 등 일시적인 사용이 아니라면 데이터 손실을 방지하기 위해 반드시 사용한다.  
예외적으로 일시적 인스턴스가 필요할 때는 PV 없이 배포할 수 있으나, 큐에 저장된 메시지가 사라질 수 있다.

## podManagementPolicy 설정
`podManagementPolicy: "Parallel"`이 권장된다.  
OrderedReady를 사용하면 다음과 같은 교착 상태가 발생할 수 있다.

| 단계 | 설명 |
|------|------|
| 1 | Kubernetes가 첫 번째 노드의 readiness probe를 기다림 |
| 2 | 노드는 완전히 부팅되기 전까지 readiness probe가 실패 |
| 3 | 완전 부팅은 동료 노드가 온라인이 된 후에만 가능 |
| 4 | Kubernetes는 첫 번째 노드가 준비될 때까지 다른 파드를 시작하지 않음 |
| 5 | 배포가 데드락에 빠짐 |

Parallel 정책을 사용하면 이 문제를 피할 수 있으며, Kubernetes의 피어 디스커버리 플러그인이 초기 형성 시 발생하는 자연스러운 경쟁 조건을 처리한다.

## ReadinessProbe 구성
가장 흔한 설정은 AMQP 포트(5672 또는 5671)에 대한 TCP 체크이다. 이 포트가 열리면 노드가 거의 완전히 부팅된 상태이며 연결을 받을 준비가 된 것으로 간주된다.  
OrderedReady를 사용해야 할 경우, 완전 부팅을 요구하지 않는 `exec` 기반 프로브를 활용할 수 있다. 그러나 이는 권장되지 않는다.

```yaml
readinessProbe:
  exec:
    command: ["rabbitmq-diagnostics", "ping"]
```

## Peer Discovery 설정
Kubernetes 내부에서 피어를 찾으려면 `cluster_formation.peer_discovery_backend`를 `k8s` 또는 `rabbit_peer_discovery_k8s`로 지정한다.

```ini
cluster_formation.peer_discovery_backend = k8s
# 또는
cluster_formation.peer_discovery_backend = rabbit_peer_discovery_k8s
```

기본 설정이 대부분의 경우에 충분하지만, 필요에 따라 추가 설정이 제공된다.

## `/etc/rabbitmq` 쓰기 가능하도록 마운트
RabbitMQ 노드는 `/etc/rabbitmq`에 파일을 업데이트할 수 있다. 이 디렉터리를 writable로 마운트하고, RabbitMQ 사용자(`rabbitmq`)가 소유하도록 설정해야 한다.  
또는 init 컨테이너에서 ConfigMap 볼륨을 `/etc`에 복사해도 된다.

## 핵심 흐름 다이어그램
![diagram](/assets/diagrams/2026-07-03-kubernetes에-rabbitmq를-직접-배포하기-핵심-가이드-1.svg)

## 정리
- Operator나 Helm 차트 사용이 가장 안전하지만, 직접 배포가 필요할 경우 **StatefulSet**, **PV**, **Parallel podManagementPolicy**, **TCP 기반 ReadinessProbe**, **k8s 피어 디스커버리**, **/etc/rabbitmq writable** 설정을 반드시 적용해야 한다.
- CoreDNS 캐시 타임아웃을 5~10초로 낮추거나 init 컨테이너로 지연을 주는 것이 중요하다.
- 이 가이드는 **권장되지 않는** 방법이므로, 가능하면 Operator 기반 배포를 선택하는 것이 좋다.

---
> 🤖 작성 모델: `openai/gpt-oss-20b:free` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.rabbitmq.com/docs/install-kubernetes-diy](https://www.rabbitmq.com/docs/install-kubernetes-diy)
