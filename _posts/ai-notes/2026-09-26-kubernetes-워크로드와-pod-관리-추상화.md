---
title: "Kubernetes 워크로드와 Pod 관리 추상화"
layout: post
categories: ai-notes
type: study-note
date: 2026-09-26 09:05:09 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-09-26
sources:
  - https://kubernetes.io/docs/concepts/workloads/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: Kubernetes에서 워크로드는 하나 이상의 컨테이너를 실행하는 `Pod` 집합으로 구성되며, 워크로드 리소스가 컨트롤러를 통해 `Pod`의 수와 종류를 지정 상태에 맞게 유지한다.

### 개요

Kubernetes에서 워크로드는 클러스터에서 실행되는 애플리케이션이다. 단일 구성 요소든 여러 구성 요소가 함께 동작하든, 실행 단위는 `Pod` 집합이다. `Pod`는 하나 이상의 컨테이너를 나타내며 정의된 lifecycle을 가진다. `Pod`가 실행 중인 노드에 치명적 장애가 발생하면 해당 노드의 모든 `Pod`가 실패하고, Kubernetes는 이 실패를 최종 상태로 취급하므로 노드가 나중에 정상화되어도 새 `Pod`를 만들어야 복구된다. 그래서 각 `Pod`를 직접 관리하는 대신, `Pod` 집합을 관리해 주는 워크로드 리소스를 사용한다.

### 워크로드 리소스와 컨트롤러

워크로드 리소스는 컨트롤러를 설정하고, 컨트롤러는 사용자가 지정한 상태에 맞춰 적절한 수와 종류의 `Pod`가 실행되도록 유지한다. 노드 장애로 `Pod`가 실패하면 컨트롤러는 지정 상태에 맞춰 새 `Pod`를 생성해 복구한다. 아래 그림은 워크로드 리소스가 컨트롤러에 지정 상태를 제공하고, 장애 후 컨트롤러가 상태를 복구하는 순서를 나타낸다.

![diagram](/assets/diagrams/2026-09-26-kubernetes-워크로드와-pod-관리-추상화-1.svg)

Kubernetes가 기본으로 제공하는 워크로드 리소스는 다음과 같다.

| 리소스 | 적합한 워크로드 | 핵심 동작 |
| --- | --- | --- |
| `Deployment` / `ReplicaSet` | 상태를 추적하지 않는 애플리케이션 | `Deployment`의 `Pod`는 서로 교체할 수 있고 필요하면 대체할 수 있다. `ReplicaSet`은 레거시 리소스인 `ReplicationController`를 대체한다. |
| `StatefulSet` | 상태를 추적하는 관련 `Pod` | 워크로드가 데이터를 영속적으로 기록하면 각 `Pod`에 `PersistentVolume`을 매칭할 수 있다. 같은 `StatefulSet`의 `Pod`들은 데이터를 서로 복제해 전체 회복탄력성을 개선할 수 있다. |
| `DaemonSet` | 노드 로컬 기능을 제공하는 `Pod` | 사양과 일치하는 노드가 클러스터에 추가되면 컨트롤 플레인이 새 노드에 `DaemonSet`의 `Pod`를 스케줄링한다. 각 `Pod`는 Unix/POSIX 서버의 시스템 데몬과 유사한 작업을 수행한다. |
| `Job` / `CronJob` | 완료까지 실행된 후 멈추는 작업 | `Job`은 한 번만 완료까지 실행하는 작업을 정의한다. `CronJob`은 일정에 따라 같은 `Job`을 여러 번 실행한다. |

`DaemonSet`은 클러스터 네트워크 플러그인처럼 클러스터 운영에 기본적인 기능, 노드 관리 지원, 컨테이너 플랫폼을 개선하는 선택적 동작을 맡을 수 있다.

### 그룹 단위 배치와 확장

표준 워크로드 리소스가 `Pod`의 lifecycle을 관리하는 것과 달리, `Pod` 그룹을 하나의 단위로 취급해야 하는 스케줄링 요구도 있다. `Workload API`는 `PodGroupTemplates`를 정의해 `Pod`를 그룹화하고 `gang scheduling` 같은 고급 스케줄링 정책을 적용할 수 있게 한다. 컨트롤러는 런타임에 템플릿에서 `PodGroup` 객체를 생성하고, `Pod`는 `spec.schedulingGroup` 필드로 자신의 `PodGroup`을 참조한다. 이 기능은 배치 처리나 머신러닝 워크로드처럼 전부 또는 전무(all-or-nothing) 배치가 필요한 경우에 특히 유용하다.

`Workload placement` 기능은 Kubernetes v1.37부터 `Beta` 상태이며 기본적으로 비활성화되어 있다. 사용하려면 클러스터 관리자가 관련 컴포넌트 전체에서 `GenericWorkload` feature gate를 활성화해야 한다.

Kubernetes core에 없는 동작은 커스텀 리소스 정의를 통해 서드파티 워크로드 리소스로 추가할 수 있다. 예를 들어 애플리케이션의 `Pod` 그룹이 모두 사용 가능할 때까지 작업을 멈추는 확장이 필요하다면, 그 기능을 제공하는 확장을 구현하거나 설치할 수 있다.

### 보조 개념

워크로드 관리와 함께 알아둘 보조 개념이 있다. `Garbage collection`은 소유 리소스(owning resource)가 제거된 후 관련 객체를 클러스터에서 정리한다. `time-to-live after finished` 컨트롤러는 `Job`이 완료된 후 정의된 시간이 지나면 해당 `Job`을 제거한다. 실행 중인 애플리케이션은 `Service`로 인터넷에 노출하거나, 웹 애플리케이션의 경우 `Ingress`를 사용할 수 있다.

### 정리

결국 Kubernetes 워크로드 관리의 핵심은 `Pod`의 lifecycle을 개별적으로 다루지 않고, 워크로드 리소스가 컨트롤러를 통해 원하는 상태를 계속 맞춰 나간다는 데 있다. 노드 장애가 `Pod` 실패를 최종적으로 만든다는 점 때문에 복구는 항상 새 `Pod` 생성으로 이어지며, 이 작업을 사용자 대신 워크로드 리소스가 수행한다. 기본 제공 리소스는 워크로드의 성격(stateless, stateful, node-local, 완료형 작업)에 따라 선택할 수 있고, 그룹 단위 스케줄링이나 core 밖의 동작은 `PodGroup`과 서드파티 확장으로 보완한다. 다만 `Workload placement`는 아직 `Beta`이고 기본 비활성화이므로, 사용하려면 `GenericWorkload` feature gate를 활성화해야 한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/workloads/](https://kubernetes.io/docs/concepts/workloads/)
