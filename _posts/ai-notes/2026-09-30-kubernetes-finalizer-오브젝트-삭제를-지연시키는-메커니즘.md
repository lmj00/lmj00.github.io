---
title: "Kubernetes Finalizer: 오브젝트 삭제를 지연시키는 메커니즘"
layout: post
categories: ai-notes
type: study-note
date: 2026-09-30 09:09:43 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-09-30
sources:
  - https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: Finalizer는 삭제가 요청된 오브젝트를 즉시 지우지 않고, 컨트롤러가 소유 리소스의 정리를 마칠 때까지 삭제를 보류하도록 만드는 Kubernetes의 메커니즘이다.

### 개요

**Finalizer**는 삭제가 표시된 리소스를 Kubernetes가 완전히 삭제하기 전에 특정 조건이 충족될 때까지 기다리도록 지시하는 네임스페이스 키다. Finalizer는 컨트롤러가 삭제 대상 오브젝트가 소유했던 리소스를 정리하도록 알리는 역할을 한다. 이를 통해 오브젝트가 아직 사용 중이거나 하위 리소스를 가진 상태에서 실수로 삭제되는 것을 방지하고, 관련 API 리소스나 인프라를 먼저 정리하도록 가비지 컬렉션을 제어할 수 있다. 관리되지 않는(unmanaged) 리소스의 삭제를 막는 용도로도 사용할 수 있다.

### Finalizer의 동작 원리

매니페스트 파일로 리소스를 만들 때 `metadata.finalizers` 필드에 finalizer를 지정할 수 있다. finalizer가 지정된 오브젝트에 삭제 요청이 들어오면 API 서버는 다음을 수행한다.

- 오브젝트에 `metadata.deletionTimestamp` 필드를 추가해 삭제가 시작된 시각을 기록한다.
- `metadata.finalizers` 필드의 모든 항목이 제거될 때까지 오브젝트가 삭제되지 않도록 막는다.
- HTTP 202(ACCEPTED) 상태 코드를 반환한다.

이후 해당 finalizer를 관리하는 컨트롤러는 오브젝트에 `deletionTimestamp`가 설정된 변경을 감지하고 삭제가 요청되었음을 인지한다. 컨트롤러는 finalizer가 지정한 조건을 충족시키기 위한 작업을 수행하고, 조건이 충족될 때마다 리소스의 `finalizers` 필드에서 해당 키를 제거한다. `finalizers` 필드가 비워지면 `deletionTimestamp`가 설정된 오브젝트는 자동으로 삭제된다. 오브젝트는 이 과정 동안 terminating 상태로 남으며, 정리 작업은 컨트롤 플레인이나 다른 컴포넌트가 수행한다.

![diagram](/assets/diagrams/2026-09-30-kubernetes-finalizer-오브젝트-삭제를-지연시키는-메커니즘-1.svg)

Finalizer는 일반적으로 실행할 코드를 지정하지 않는다. 대신 어노테이션과 유사하게 특정 리소스에 붙는 키의 목록일 뿐이며, Kubernetes가 자동으로 지정하는 finalizer도 있고 사용자가 직접 지정할 수도 있다.

### 실제 예: kubernetes.io/pv-protection

대표적인 예로 `kubernetes.io/pv-protection` finalizer가 있다. 이 finalizer는 PersistentVolume 오브젝트의 실수 삭제를 방지한다. PersistentVolume이 Pod에 사용 중이면 Kubernetes는 `pv-protection` finalizer를 추가한다. 이 상태에서 PersistentVolume을 삭제하려 하면 오브젝트는 `Terminating` 상태로 들어가지만, finalizer가 존재하므로 컨트롤러는 볼륨을 삭제할 수 없다. Pod가 PersistentVolume 사용을 중단하면 Kubernetes는 `pv-protection` finalizer를 제거하고, 그제서야 컨트롤러가 볼륨을 삭제한다.

### 삭제 요청 후의 제약 사항

DELETE 요청이 처리되면 Kubernetes는 오브젝트에 삭제 타임스탬프를 추가하고, 삭제가 보류 중인 오브젝트의 `.metadata.finalizers` 필드 변경을 즉시 제한하기 시작한다. 기존 finalizer를 목록에서 제거하는 것은 가능하지만, 새 finalizer를 추가할 수는 없다. 한번 설정된 `deletionTimestamp`도 수정할 수 없다. 삭제가 요청된 오브젝트는 되살릴 수 없으며, 삭제 후 동일한 새 오브젝트를 만들어야 한다.

커스텀 finalizer 이름은 `example.com/finalizer-name`처럼 공개적으로 한정된(qualified) 이름이어야 한다. Kubernetes는 이 형식을 강제하며, 커스텀 finalizer에 qualified 이름을 사용하지 않는 변경은 API 서버가 거부한다.

### Owner references, labels, finalizers의 관계

labels와 owner references는 모두 Kubernetes 오브젝트 간의 관계를 설명하지만 용도가 다르다. 컨트롤러가 Pod 같은 오브젝트를 관리할 때는 labels를 사용해 관련 오브젝트 그룹의 변경을 추적한다. 예를 들어 Job이 Pod를 생성하면 Job 컨트롤러는 해당 Pod에 label을 적용하고, 클러스터에서 같은 label을 가진 모든 Pod의 변경을 추적한다.

Job 컨트롤러는 또한 생성한 Pod에 owner references를 추가해 Pod를 만든 Job을 가리키게 한다. Pod가 실행 중일 때 Job을 삭제하면, Kubernetes는 labels가 아니라 owner references를 사용해 클러스터에서 정리해야 할 Pod를 결정한다. Kubernetes는 삭제 대상 리소스에서 owner references를 식별할 때도 finalizer를 처리한다.

상황에 따라 finalizer가 dependent 오브젝트의 삭제를 막아, 대상 owner 오브젝트가 완전히 삭제되지 않고 예상보다 오래 남을 수 있다. 이런 경우 대상 owner와 dependent 오브젝트의 finalizer와 owner references를 확인해 원인을 찾아야 한다.

### 주의 사항

오브젝트가 삭제 상태에 멈춰 있더라도 finalizer를 수동으로 제거해 삭제를 강행하는 것은 피해야 한다. finalizer는 보통 이유가 있어서 리소스에 추가되므로, 강제로 제거하면 클러스터에 문제가 생길 수 있다. finalizer의 목적을 이해하고 다른 방식으로 목적을 달성했을 때만(예: dependent 오브젝트를 수동으로 정리) 제거를 고려해야 한다.

### 정리

Finalizer는 Kubernetes 오브젝트 삭제 과정에서 안전장치 역할을 한다. 삭제 요청이 들어와도 `metadata.finalizers` 필드가 비워질 때까지 오브젝트는 terminating 상태로 남으며, 컨트롤러가 정리 작업을 마친 뒤 finalizer를 제거해야 비로소 삭제가 완료된다. 삭제가 요청된 오브젝트에는 새 finalizer를 추가하거나 `deletionTimestamp`를 수정할 수 없고, 커스텀 finalizer 이름은 `example.com/finalizer-name` 형식의 qualified 이름이어야 한다. 삭제가 멈춘 오브젝트를 발견하면 finalizer와 owner references를 확인해 원인을 찾는 것이 우선이며, finalizer를 강제로 제거하는 것은 신중해야 한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/](https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/)
