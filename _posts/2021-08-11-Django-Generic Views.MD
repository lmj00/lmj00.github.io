---
title: "[Django] Generic Views"
layout: post
---

## 제네릭 뷰
- 웹 개발을 할 때 자주 사용하는 구조를 하나의 내용으로 모아놓은 뷰
- 간단하고 빠르게 뷰를 구현할 수 있다.

## 종류
#### Base views
- View (기본 뷰)
- TemplateView (URL에 포함된 context를 사용하여 템플릿을 렌더링)
- RedirectView (지정된 URL로 Redirect)


#### Generic display views
- DetailView (객체의 세부 정보를 나타냄)
- ListView (객체 목록)


#### Generic editing views
- FormView (폼을 표시하는 뷰)
- CreateView (객체를 생성하는 폼)
- UpdateView (객체를 수정하는 폼)
- DeleteView (기존 객체를 삭제하는 폼)


#### Generic date views
- ArchiveIndexView 
- YearArchiveView  
- MonthArchiveView
- WeekArchiveView
- DayArchiveView
- TodayArchiveView
- DateDetailView


