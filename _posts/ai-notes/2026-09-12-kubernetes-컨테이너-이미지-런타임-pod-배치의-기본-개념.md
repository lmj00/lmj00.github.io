---
title: "Kubernetes 컨테이너: 이미지, 런타임, Pod 배치의 기본 개념"
layout: post
categories: ai-notes
type: study-note
date: 2026-09-12 08:11:02 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-09-12
sources:
  - https://kubernetes.io/docs/concepts/containers/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: 컨테이너는 애플리케이션과 런타임 의존성을 하나로 묶는 패키징 기술이며, Kubernetes에서는 불변 이미지로 컨테이너를 만들고 컨테이너 런타임이 실행과 라이프사이클을 관리한다.

### 개요
컨테이너는 애플리케이션을 런타임 의존성과 함께 패키징하는 기술이다. 의존성이 패키지에 포함되므로 실행 위치와 관계없이 같은 동작을 얻을 수 있고, 애플리케이션이 호스트 인프라로부터 분리되므로 다양한 클라우드나 OS 환경에서 배포가 쉬워진다. Kubernetes 클러스터에서 각 노드는 자신에게 할당된 Pod를 구성하는 컨테이너를 실행한다. 다만 `container`라는 단어는 여러 의미로 쓰이는 용어이므로, 사용할 때 상대방이 같은 정의를 쓰는지 확인해야 한다.

### 컨테이너 이미지와 불변성
컨테이너 이미지는 실행 준비가 끝난 소프트웨어 패키지다. 코드와 필요한 런타임, 애플리케이션 및 시스템 라이브러리, 필수 설정의 기본값이 모두 이미지에 포함된다.

컨테이너는 상태를 갖지 않고(stateless) 불변(immutable)으로 설계된다. 이미 실행 중인 컨테이너의 코드를 변경해서는 안 되며, 변경이 필요하면 변경 사항을 포함한 새 이미지를 빌드한 뒤 그 이미지로 컨테이너를 다시 생성해야 한다.

### Kubernetes에서의 컨테이너 배치
Kubernetes 클러스터의 각 노드는 해당 노드에 할당된 Pod를 구성하는 컨테이너를 실행한다. 같은 Pod 안의 컨테이너들은 같은 노드에 함께 배치되고(co-located) 함께 스케줄된다(co-scheduled).

### 컨테이너 런타임과 RuntimeClass
컨테이너 런타임은 Kubernetes가 컨테이너를 효과적으로 실행하게 하는 기본 구성 요소다. 런타임은 Kubernetes 환경에서 컨테이너의 실행과 라이프사이클을 관리한다. Kubernetes는 `containerd`, `CRI-O`, 그리고 Kubernetes CRI(Container Runtime Interface)를 구현한 다른 런타임을 지원한다.

보통은 클러스터가 Pod의 기본 컨테이너 런타임을 선택하도록 둘 수 있다. 클러스터에서 여러 컨테이너 런타임을 사용해야 한다면 Pod에 `RuntimeClass`를 지정해 Kubernetes가 특정 런타임으로 컨테이너를 실행하게 할 수 있다. `RuntimeClass`는 같은 런타임을 쓰더라도 Pod마다 다른 설정으로 실행할 때도 사용할 수 있다.

이미지에서 컨테이너가 생성되고 런타임이 이를 관리하며, 컨테이너가 Pod로 노드에 배치되는 흐름을 나타내면 다음과 같다.

![diagram](/assets/diagrams/2026-09-12-kubernetes-컨테이너-이미지-런타임-pod-배치의-기본-개념-1.svg)

### 정리
컨테이너는 코드와 런타임, 라이브러리, 기본 설정을 하나의 이미지로 묶어 어디서든 같은 동작을 보장하는 실행 단위다. Kubernetes에서 컨테이너는 Pod 단위로 같은 노드에 배치되며, 컨테이너 런타임이 실행과 라이프사이클을 관리한다. 실행 중인 컨테이너는 변경하지 않고 새 이미지를 빌드해 재생성하는 불변성 원칙을 따른다. 여러 런타임이 필요하면 `RuntimeClass`로 Pod별 런타임이나 설정을 지정할 수 있다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/containers/](https://kubernetes.io/docs/concepts/containers/)
