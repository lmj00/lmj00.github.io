---
title: "Kubernetes Field Selector: 리소스 필드 값으로 객체를 필터링하기"
layout: post
categories: ai-notes
type: study-note
date: 2026-10-01 09:27:29 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:qwen/qwen3.8-flash"
generated_at: 2026-10-01
sources:
  - https://kubernetes.io/docs/concepts/overview/working-with-objects/field-selectors/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: Field Selector는 `metadata.name`, `metadata.namespace`, 리소스별로 허용된 필드의 값을 기준으로 Kubernetes 객체를 좁히는 필터이며, 집합 연산자나 미지원 필드는 사용할 수 없다.

### 개요
Field Selector는 Kubernetes 객체를 하나 이상의 리소스 필드 값으로 선택하는 방법이다. `metadata.name=my-service`, `metadata.namespace!=default`, `status.phase=Pending` 같은 쿼리가 예시다. 선택자가 없으면 지정된 타입의 모든 리소스가 선택되므로, Field Selector는 기본적으로 결과를 좁히는 필터로 동작한다. 모든 리소스 타입이 `metadata.name`과 `metadata.namespace`을 지원하지만, 나머지 필드는 타입에 따라 지원 범위가 다르다.

### 기본 동작과 예시
`kubectl`은 `--field-selector`로 필드 선택자를 지정한다. 예를 들어 `status.phase`가 `Running`인 Pod만 고르려면 다음을 사용한다.

```bash
kubectl get pods --field-selector status.phase=Running
```

이 명령은 `status.phase` 필드 값이 `Running`인 모든 Pod를 선택한다. 선택자를 비워 두는 것도 필터를 적용하지 않는 것과 같으므로 `kubectl get pods`와 `kubectl get pods --field-selector ""`는 동일한 결과를 만든다.

### 지원 필드와 리소스별 차이
Field Selector에 사용할 수 있는 필드는 리소스 종류에 따라 달라진다. 모든 리소스 타입은 `metadata.name`과 `metadata.namespace`을 지원한다. 지원되지 않는 필드를 넣으면 오류가 발생한다. 예를 들어 `kubectl get ingress --field-selector foo.bar=baz`는 `foo.bar`가 알려진 필드 선택자가 아니라고 거부한다.

리소스 종류별로 문서에 명시된 지원 필드는 다음과 같다.

| 리소스 종류 | Field Selector로 사용할 수 있는 필드 |
|---|---|
| Pod | `spec.nodeName`, `spec.restartPolicy`, `spec.schedulerName`, `spec.serviceAccountName`, `spec.hostNetwork`, `status.phase`, `status.podIP`, `status.podIPs`, `status.nominatedNodeName` |
| Event | `involvedObject.kind`, `involvedObject.namespace`, `involvedObject.name`, `involvedObject.uid`, `involvedObject.apiVersion`, `involvedObject.resourceVersion`, `involvedObject.fieldPath`, `reason`, `reportingComponent`, `source`, `type` |
| Secret | `type` |
| Service | `spec.clusterIP`, `spec.type` |
| Namespace | `status.phase` |
| ReplicaSet | `status.replicas` |
| ReplicationController | `status.replicas` |
| Job | `status.successful` |
| Node | `spec.unschedulable` |
| CertificateSigningRequest | `spec.signerName` |

CustomResourceDefinition으로 만드는 사용자 정의 리소스도 `metadata.name`과 `metadata.namespace`을 지원한다. 그 외 필드를 Field Selector에 사용할 수 있는지 여부는 CRD의 `spec.versions[*].selectableFields`가 선언한다.

### 연산자와 체이닝
Field Selector에는 `=`, `==`, `!=` 연산자만 사용할 수 있다. `=`와 `==`는 같은 의미다. `in`, `notin`, `exists` 같은 집합 기반 연산자는 Field Selector에서 지원되지 않는다.

```bash
kubectl get services --all-namespaces --field-selector metadata.namespace!=default
```

이 명령은 `default` 네임스페이스에 있지 않은 모든 Kubernetes Service를 선택한다.

여러 조건은 쉼표로 연결할 수 있다.

```bash
kubectl get pods --field-selector status.phase!=Running,spec.restartPolicy=Always
```

이 예시는 `status.phase`가 `Running`이 아니고 `spec.restartPolicy`가 `Always`인 Pod를 선택한다. Field Selector는 여러 리소스 타입에서도 사용할 수 있다.

```bash
kubectl get statefulsets,services --all-namespaces --field-selector metadata.namespace!=default
```

이 명령은 `default` 네임스페이스에 있지 않은 StatefulSet과 Service를 모두 고른다.

### 정리
Field Selector는 리소스 필드 값으로 Kubernetes 객체를 좁히는 필터다. 기본 선택자가 없으면 해당 타입의 모든 리소스가 선택되고, `metadata.name`과 `metadata.namespace`은 모든 타입에서 공통으로 지원된다. 지원되지 않는 필드나 집합 연산자는 오류의 원인이 되므로 리소스별 허용 필드를 먼저 확인해야 한다. 조건은 쉼표로 연결할 수 있고, 여러 리소스 타입을 한 명령에서 함께 필터링하는 것도 가능하다.

---
> 🤖 작성 모델: `qwen/qwen3.8-flash` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/overview/working-with-objects/field-selectors/](https://kubernetes.io/docs/concepts/overview/working-with-objects/field-selectors/)
