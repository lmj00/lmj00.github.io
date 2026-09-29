---
title: "Kubernetes CRI(Container Runtime Interface): kubelet과 컨테이너 런타임을 잇는 gRPC 규약"
layout: post
categories: ai-notes
type: study-note
date: 2026-09-25 08:53:13 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-09-25
sources:
  - https://kubernetes.io/docs/concepts/containers/cri/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: CRI는 kubelet이 다양한 컨테이너 런타임을 재컴파일 없이 사용하게 해주는 gRPC 기반 플러그인 인터페이스다. v1.26부터 v1 CRI API를 필수로 요구하며, v1.36부터는 대량 컨테이너 환경을 위한 리스트 스트리밍을 선택적으로 제공한다.

### 개요
**CRI**(Container Runtime Interface)는 kubelet이 다양한 컨테이너 런타임을 사용할 수 있게 해주는 플러그인 인터페이스다. 이 인터페이스 덕분에 클러스터 컴포넌트를 재컴파일하지 않고도 런타임을 확장하거나 교체할 수 있다. kubelet이 Pod와 그 컨테이너를 실행하려면 각 노드에 동작하는 컨테이너 런타임이 필요하며, CRI는 kubelet과 컨테이너 런타임 사이의 주요 통신 프로토콜이다. 구체적으로 CRI는 노드 컴포넌트인 kubelet과 컨테이너 런타임 사이의 gRPC 프로토콜을 정의한다.

### CRI의 구조: kubelet은 gRPC 클라이언트로 동작한다
CRI API는 Kubernetes v1.23부터 안정(stable) 상태다. 통신 구조에서 kubelet은 gRPC로 컨테이너 런타임에 연결할 때 클라이언트 역할을 한다. 컨테이너 런타임 쪽에는 런타임 서비스와 이미지 서비스 엔드포인트가 모두 제공되어야 하며, kubelet에서는 `--container-runtime-endpoint` 커맨드 라인 플래그로 각 엔드포인트를 별도로 설정할 수 있다.

### CRI API 버전과 업그레이드 동작
Kubernetes v1.26부터 kubelet은 컨테이너 런타임이 v1 CRI API를 지원할 것을 요구한다. 런타임이 v1 API를 지원하지 않으면 kubelet은 노드를 등록하지 않는다.

노드의 Kubernetes 버전을 업그레이드하면 kubelet이 재시작된다. 이때 컨테이너 런타임이 v1 CRI API를 지원하지 않으면 kubelet은 등록에 실패하고 오류를 보고한다. 컨테이너 런타임이 업그레이드되어 gRPC 재연결(re-dial)이 필요한 경우에도 연결이 성공하려면 런타임이 v1 CRI API를 지원해야 한다. 따라서 런타임을 올바르게 설정한 뒤 kubelet을 재시작해야 하는 상황이 발생할 수 있다.

### 리스트 스트리밍(CRIListStreaming)
기본 CRI 리스트 RPC(`ListContainers`, `ListPodSandbox`, `ListImages`)는 모든 결과를 하나의 단일 응답(유너리 응답)으로 돌려준다. 그런데 실행 중이거나 중지된 컨테이너를 합쳐 대략 10,000개 이상의 컨테이너가 있는 노드에서는 이 응답이 gRPC의 기본 메시지 크기 제한인 16MiB를 초과할 수 있다. 이 경우 kubelet이 컨테이너 런타임과 상태를 조정(reconcile)할 때 실패하게 된다.

이 문제를 해결하기 위해 Kubernetes v1.36부터 `CRIListStreaming` 피처 게이트가 알파(alpha) 상태로 도입됐으며, 기본적으로 비활성화되어 있다. 사용하려면 클러스터 관리자가 클러스터의 모든 관련 컴포넌트에서 이 피처 게이트를 활성화해야 한다.

피처 게이트를 켜면 kubelet은 서버 사이드 스트리밍 RPC(`StreamContainers`, `StreamPodSandboxes`, `StreamImages`)를 사용한다. 스트리밍 RPC를 사용하면 컨테이너 런타임이 결과를 여러 응답 메시지로 나눠 보낼 수 있으므로 메시지당 크기 제한을 우회한다. 이 기능은 컨테이너 생성·삭제가 빈번한 CI/CD 시스템이나 대규모 배치 처리 워크로드처럼 컨테이너 교체(churn)가 많은 환경에서 특히 유용하다.

컨테이너 런타임이 스트리밍 RPC를 지원하지 않으면 kubelet은 자동으로 기존의 단일 응답 RPC로 폴백한다. 따라서 스트리밍을 지원하지 않는 런타임과의 하위 호환성은 유지된다.

kubelet의 리스트 RPC 선택 흐름을 정리하면 다음과 같다.

![diagram](/assets/diagrams/2026-09-25-kubernetes-cri-container-runtime-interface-kubelet과-컨테이너-런타임-1.svg)

### 정리
CRI는 kubelet과 컨테이너 런타임 사이의 gRPC 기반 플러그인 인터페이스로, 런타임을 바꿔도 클러스터 컴포넌트를 재컴파일할 필요가 없다는 유연성을 제공한다. v1.26부터는 v1 CRI API 지원이 필수가 되어, 이를 지원하지 않는 런타임은 노드 등록 자체가 실패한다. v1.36부터는 리스트 스트리밍이 알파 기능으로 도입되어, 16MiB 메시지 크기 제한을 우회함으로써 대량 컨테이너 노드에서 상태 조정 실패를 막는다. 스트리밍을 지원하지 않는 런타임을 위해서는 기존 유너리 RPC로 자동 폴백하므로 하위 호환성도 유지된다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/containers/cri/](https://kubernetes.io/docs/concepts/containers/cri/)
