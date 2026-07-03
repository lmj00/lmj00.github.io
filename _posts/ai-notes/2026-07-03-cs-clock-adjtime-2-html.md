---
title: "Cs: Clock_Adjtime.2.Html"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-03
tags: [cs, os, syscall]
generated_by: "openrouter:nvidia/nemotron-3-super-120b-a12b:free"
generated_at: 2026-07-03
sources:
  - https://man7.org/linux/man-pages/man2/clock_adjtime.2.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요  
adjtimex(), clock_adjtime(), ntp_adjtime() 시스템 콜은 데이비드 L. 밀스의 클럭 보정 알고리즘을 이용해 리눅스 커널 시계를 읽거나 조정한다. 이 함수들은 struct timex 구조체를 통해 오프셋, 주파수 오프셋, 상태 플래그 등을 전달한다. clock_adjtime()은 추가적인 clk_id 인자로 특정 클럭을 지정할 수 있고, ntp_adjtime()은 더 이식 가능한 라이브러리 인터페이스이다.

### 작동 원리  
시스템 콜은 사용자로부터 전달된 struct timex 포인터를 받아 커널 내 클럭 보정 파라미터를 읽고, modes 필드에 지정된 비트에 따라 선택적으로 값을 쓴다. modes 필드는 비트마스크로, ADJ_OFFSET, ADJ_FREQUENCY, ADJ_MAXERROR, ADJ_ESTERROR, ADJ_STATUS, ADJ_TIMECONST, ADJ_SETOFFSET, ADJ_MICRO, ADJ_NANO, ADJ_TAI, ADJ_TICK, ADJ_OFFSET_SINGLESHOT, ADJ_OFFSET_SS_READ 등을 조합해 사용할 수 있다. 예를 들어 ADJ_OFFSET_SINGLESHOT은 buf.offset에 주어진 마이크로초 단위 값을 이용해 adjtime(3)과 유사하게 시간을 점차 조정하고, ADJ_OFFSET_SS_READ은 이전에 수행한 ADJ_OFFSET_SINGLESHOT 작업의 남은 조정량을 buf.offset에 반환한다.  

status 필드도 비트마스크이며, STA_PLL, STA_PPSFREQ, STA_PPSTIME, STA_FLL, STA_INS, STA_DEL, STA_UNSYNC, STA_FREQHOLD 등은 읽고 쓸 수 있고, STA_PPSSIGNAL, STA_PPSJITTER, STA_PPSWANDER, STA_PPSERROR, STA_CLOCKERR, STA_NANO, STA_MODE, STA_CLK 등은 읽기 전용이다. 읽기 전용 비트를 설정하려는 시도는 무시된다. STA_NANO는 2.6.26부터 해상도를 나노초로 선택하며, ADJ_NANO로 설정하고 ADJ_MICRO로 해제한다.  

freq, ppsfreq, stabil 필드는 16비트 소수부를 가진 ppm 단위이며, 값 1은 2⁻¹⁶ ppm에 해당하고 65536은 1 ppm이다. leap‑second 플래그인 STA_INS와 STA_DEL이 설정되면 커널 타이머 컨텍스트에서 처리되며, 실제 삽입·삭제는 한 틱 이후에 이루어진다.  

반환 값은 성공 시 클럭 상태를 나타내는 상수 중 하나이다: TIME_OK(동기화, leap‑second 대기 없음), TIME_INS(오늘 끝에 leap‑second 삽입 예정), TIME_DEL(삭제 예정), TIME_OOP(삽입 진행 중), TIME_WAIT(삽입·삭제 완료 후 플래그_clear 전까지), TIME_ERROR(동기화 실패). TIME_ERROR는 STA_UNSYNC 또는 STA_CLOCKERR이 설정돼 있거나, STA_PPSSIGNAL이 cleared이며 STA_PPSFREQ 또는 STA_PPSTIME 중 하나가 설정돼 있거나, STA_PPSTIME와 STA_PPSJITTER가 동시에 설정돼 있거나, STA_PPSFREQ이 설정돼 있으며 STA_PPSWANDER 또는 STA_PPSJITTER 중 하나가 설정돼 있을 때 반환된다. TIME_BAD은 TIME_ERROR의 이전 이름이다.  

Linux 3.4부터는 호출이 비동기적으로 처리돼 반환 값이 바로 호출로 인한 상태 변화를 반영하지 않을 수 있다.  

오류 상황에서는 -1을 반환하고 errno를 설정한다: EFAULT는 buf가 쓰기 불가능한 메모리를 가리킬 때, EINVAL은 modes, offset, freq, tick, status 또는 clk_id의 값이 허용 범위를 벗어났을 때, ENODEV는 동적 clk_id가 나타내는 핫플러그 장치가 사라졌을 때, EOPNOTSUPP는 해당 clk_id가 조정을 지원하지 않을 때, EPERM은 일반 사용자가 modes에 0이나 ADJ_OFFSET_SS_READ 이외의 값을 넣으려 할 때(즉, CAP_SYS_TIME 능력이 필요) 발생한다.  

### 차이점 및 사용 주의  
- adjtimex()와 ntp_adjtime()은 기본적으로 시스템 전체 실시간 클럭을 대상으로 한다. clock_adjtime()은 clk_id 인자로 특정 클럭(예: monotonic, boot-time)을 지정할 수 있다.  
- ntp_adjtime()은 라이브러리 함수로, modes 상수에 MOD_ 접두사를 사용하고 MOD_CLKA가 ADJ_OFFSET_SINGLESHOT, MOD_CLKB가 ADJ_TICK의 동의어이다. ADJ_OFFSET_SS_READ에 해당하는 동의어는 KAPI에 없다.  
- 일반 사용자는 modes에 0이나 ADJ_OFFSET_SS_READ만 지정할 수 있으며, 그 외의 값을 설정하려면 CAP_SYS_TIME 능력(즉, root 권한)이 필요하다.  
- status 필드의 읽기 전용 비트는 설정 attempts가 무시되므로, 의도하지 않은 변경을 방지한다.  
- Linux 3.4 이후 비동기 특성 때문에 반환 값만으로 최신 클럭 상태를 신뢰하기 어렵고, 별도로 clock_gettime() 등을 이용해 확인해야 할 수 있다.  
- clk_id가 잘못되거나 지원하지 않는 클럭이면 EINVAL 또는 EOPNOTSUPP가 반환된다.  

### 정리  
adjtimex 계열 시스템 콜은 struct timex를 통해 커널 클럭의 오프셋, 주파수 오프셋, 상태 플래그 등을 읽고 조정한다. modes와 status 필드별 설정 비트마스크이며, status는 읽기/쓰기 가능 및 읽기 전용 플래그로 구성된다. clock_adjtime()은 특정 클럭을 지정할 수 있고, ntp_adjtime()은 더 이식 가능한 인터페이스이다. 일반 사용자는 제한된 modes만 사용할 수 있고, superuser 권한이 필요한 작업은 CAP_SYS_TIME을 요구한다. Linux 3.4부터는 비동기 처리 특성을 고려해야 하며, 오류 조건과 반환 값을 정확히 이해해야 한다.

---
> 🤖 작성 모델: `nvidia/nemotron-3-super-120b-a12b:free` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://man7.org/linux/man-pages/man2/clock_adjtime.2.html](https://man7.org/linux/man-pages/man2/clock_adjtime.2.html)
