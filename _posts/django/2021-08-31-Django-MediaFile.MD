---
title: "[Django] Media Field"
layout: post
--- 

### 미디어 파일 URL
- settings에 가서 `MEDIA_URL = "/{폴더 명}/"`
- Django가 인식할 수 있게 `MEDIA_ROOT = os.path.join(BASE_DIR, "media")`


### 미디어 파일 요청이 들어왔을 때 돌려주기 위해(urls.py)
```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```
