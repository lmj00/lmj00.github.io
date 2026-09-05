#!/usr/bin/env bash
# 로컬 미리보기 실행기.
# 한글 파일명(_posts/…) 때문에 UTF-8 로케일이 없으면 bundler가
# "invalid byte sequence in US-ASCII" 에러를 냄 → 여기서 로케일을 강제 지정.
#
# 사용법:  ./serve.sh            (미리보기 → http://localhost:4000)
#          ./serve.sh --drafts  (초안 포함 등 jekyll 옵션 그대로 전달)
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
exec bundle exec jekyll serve "$@"
