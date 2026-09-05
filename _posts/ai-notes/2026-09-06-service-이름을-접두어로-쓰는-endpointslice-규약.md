---
title: "Service 이름을 접두어로 쓰는 EndpointSlice 규약"
layout: post
categories: ai-notes
type: study-note
date: 2026-09-06 07:48:27 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-09-06
sources:
  - https://kubernetes.io/docs/concepts/services-networking/service/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: 셀렉터가 없는 Kubernetes Service는 EndpointSlice를 자동 생성하지 않으므로 수동으로 만들어 연결해야 하며, EndpointSlice 이름은 관례상 Service 이름을 접두어로 쓰고 실제 연결은 `kubernetes.io/service-name` 레이블이 결정한다.

### 개요
Kubernetes에서 Service는 하나 이상의 Pod로 실행 중인 네트워크 애플리케이션을 단일 엔드포인트 뒤로 노출하는 방법이다. Pod는 클러스터의 원하는 상태에 맞춰 생성되고 파괴되는 임시 리소스이므로 개별 Pod의 IP는 언제든 바뀐다. Service는 셀렉터로 논리적 엔드포인트 집합을 정의하고, 실제 백엔드 목록은 EndpointSlice 객체가 담당한다. 셀렉터가 없는 Service는 Pod가 아닌 백엔드까지 추상화할 수 있는데, 이때 EndpointSlice를 수동으로 만들어 연결하는 규약이 필요하다.

### Service와 EndpointSlice의 연결 원리
Service 객체는 논리적 엔드포인트 집합과 그 접근 정책을 정의한다. 셀렉터를 지정하면 Service의 컨트롤러가 셀렉터와 일치하는 Pod를 계속 스캔하고, 그 결과로 Service의 EndpointSlice 집합을 갱신한다. 반대로 셀렉터가 없는 Service는 대응하는 EndpointSlice 객체가 자동으로 생성되지 않는다. 이 경우 Service가 가리킬 네트워크 주소와 포트를 EndpointSlice 객체로 직접 매핑해야 한다.

셀렉터 없는 Service는 주로 다음 상황에서 사용한다. 운영 환경에서는 외부 데이터베이스 클러스터를 쓰고 테스트 환경에서는 자체 데이터베이스를 쓸 때, Service를 다른 네임스페이스나 다른 클러스터의 Service를 가리키게 할 때, 워크로드를 Kubernetes로 마이그레이션하면서 백엔드 일부만 클러스터에서 실행할 때다. 셀렉터가 없고 DNS 이름을 사용하는 ExternalName Service도 이 범주에 속하는 특수한 경우다.

![diagram](/assets/diagrams/2026-09-06-service-이름을-접두어로-쓰는-endpointslice-규약-1.svg)

### 이름 규약: Service 이름을 접두어로
수동으로 EndpointSlice를 만들 때는 **관례상 Service 이름을 EndpointSlice 이름의 접두어로 사용한다.** 예를 들어 `my-service`라는 Service에 연결하는 EndpointSlice는 `my-service-1`처럼 이름 짓는다. EndpointSlice 이름 자체는 네임스페이스 안에서 고유하기만 하면 어떤 값이든 쓸 수 있다. Service와의 연결은 이름이 아니라 `kubernetes.io/service-name` 레이블이 결정하며, 이 레이블 값은 Service 이름과 일치해야 한다.

셀렉터 없는 Service와 그에 연결되는 EndpointSlice의 예시는 다음과 같다.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 9376
```

```yaml
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: my-service-1
  labels:
    kubernetes.io/service-name: my-service
addressType: IPv4
ports:
  - name: http
    appProtocol: http
    protocol: TCP
    port: 9376
endpoints:
  - addresses:
      - "10.4.5.6"
  - addresses:
      - "10.1.2.3"
```

위 Service는 셀렉터가 없고 `http` 포트를 9376의 `targetPort`로 매핑한다. EndpointSlice는 `kubernetes.io/service-name: my-service` 레이블로 이 Service에 연결되며, 10.1.2.3과 10.4.5.6 두 주소를 백엔드로 정의한다. 셀렉터 없는 Service에 대한 접근은 셀렉터가 있는 Service와 동일하게 동작하므로, TCP 연결은 두 엔드포인트 중 하나의 9376 포트로 라우팅된다.

### 수동 EndpointSlice 작성 시 지켜야 할 제약
수동으로 만들거나 자체 코드로 관리하는 EndpointSlice에는 `endpointslice.kubernetes.io/managed-by` 레이블 값도 정해야 한다. 자체 컨트롤러 코드를 작성한다면 `my-domain.example/name-of-controller` 같은 값을, 서드파티 도구를 쓴다면 도구 이름을 소문자로 바꾸고 공백과 구두점을 대시로 치환한 값을 사용한다. kubectl로 직접 관리한다면 `staff`나 `cluster-admins`처럼 수동 관리를 설명하는 이름을 쓰고, Kubernetes 컨트롤 플레인이 관리하는 EndpointSlice를 식별하는 예약 값 `controller`는 피해야 한다.

엔드포인트 IP는 loopback(IPv4 127.0.0.0/8, IPv6 ::1/128)이나 link-local(IPv4 169.254.0.0/16, 224.0.0.0/24, IPv6 fe80::/64)이면 안 된다. 다른 Service의 클러스터 IP도 목적지로 쓸 수 없는데, kube-proxy가 가상 IP를 목적지로 지원하지 않기 때문이다.

또한 Kubernetes API 서버는 Pod에 매핑되지 않은 엔드포인트로의 프록시를 허용하지 않는다. `kubectl port-forward service/<service-name> forwardedPort:servicePort`처럼 셀렉터가 없는 Service를 대상으로 한 동작은 실패한다. 이는 API 서버가 호출자가 접근 권한이 없는 엔드포인트의 프록시로 악용되는 것을 막기 위한 제약이다.

### EndpointSlice의 확장과 이전 Endpoints API의 한계
EndpointSlice는 Service의 백킹 네트워크 엔드포인트 일부(slice)를 나타내는 객체로, Kubernetes v1.21부터 Stable 기능이다. 클러스터는 각 EndpointSlice가 나타내는 엔드포인트 수를 추적한다. 기본적으로 기존 EndpointSlice가 모두 최소 100개의 엔드포인트를 담게 되면, 새 엔드포인트를 추가해야 할 때 새 EndpointSlice를 만든다. Service는 여러 EndpointSlice와 연결될 수 있으므로 엔드포인트가 많아져도 하나의 객체에 몰리지 않는다.

EndpointSlice는 이전 Endpoints API의 진화형이다. Endpoints API는 v1.33부터 Deprecated 상태이며, dual-stack 클러스터를 지원하지 않고 `trafficDistribution` 같은 최신 기능에 필요한 정보를 담지 못하며 엔드포인트 목록이 길면 잘라낸다. Service의 백킹 엔드포인트가 1000개를 넘으면 Endpoints 객체는 최대 1000개까지만 저장하고 `endpoints.kubernetes.io/over-capacity: truncated` 어노테이션을 설정한다. 백엔드 Pod 수가 1000개 미만으로 줄면 컨트롤 플레인이 이 어노테이션을 제거한다. 이전 Endpoints API에 의존하는 로드 밸런싱 메커니즘은 사용 가능한 백엔드 중 최대 1000개에만 트래픽을 보내며, 같은 API 제한 때문에 Endpoints를 수동으로 1000개 이상 업데이트할 수도 없다.

### 정리
Service 이름을 EndpointSlice 이름의 접두어로 쓰는 것은 관례일 뿐, 실제 연결은 `kubernetes.io/service-name` 레이블이 결정한다. 셀렉터가 없는 Service는 외부 데이터베이스나 다른 네임스페이스·클러스터의 Service, 마이그레이션 중인 워크로드처럼 Pod가 아닌 백엔드를 추상화할 때 유용하다. 이때 EndpointSlice를 수동으로 만들되, IP 제약과 `managed-by` 레이블 규칙을 지켜야 한다. EndpointSlice는 기존 슬라이스가 모두 100개 이상의 엔드포인트를 담으면 새 슬라이스를 추가하는 방식으로 확장되며, 1000개 제한과 잘림 문제가 있는 이전 Endpoints API를 대체한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/services-networking/service/](https://kubernetes.io/docs/concepts/services-networking/service/)
