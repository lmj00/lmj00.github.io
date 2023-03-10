---
title: "serializer relations"
layout: post
categories: drf
---


## 관계 직렬화
```python
class Album(models.Model):
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    ...
```
```python
class AlbumSerializer(serializers.ModelSerializer):
    class Meta:
        model = Album
        fields = '__all__'
        extra_kwargs = {
            'Track': {'read_only': True}, # id를 url로 받아오기 때문에 read_only
        } 
```
```python
@api_view(['GET', 'POST'])
def album_list(request, pk):
    track = get_object_or_404(Track, pk=pk) # (조회할 모델, 조회할 pk)
    if request.method == 'GET':
        # album을 가져오기 위해 Track으로 filter
        albums = Alubm.objects.filter(track=track)
        serializer = AlbumSerializer(albums, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    elif request.method == 'POST':
        serializer = AlbumSerializer(data=request.data)
        if serializer.is_valid():
            # 시리얼라이저가 create() 함수의 validated_data에 track을 넘겨줌
            serializer.save(track=track) 
            return Response(serialeizr.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    ...
```


## 역관계 직렬화
```python
class Track(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='albums')
    # related_name = 역관계 이름 설정
    ...
```
```python
class TrackSerializer(serializers.ModelSerializer):
     class Meta:
        model = Track
        fields = ['id', 'name', 'albums', ...]
        read_only_fields = ['albums'] # 역관계를 쉽게 사용할 수 있게 설정
```


## PrimaryKeyRelatedField
- 역관계의 이름과 다른 이름으로 사용
- ModelSerializer로 관계를 표현할 경우, 기본 값으로 사용된다.

```python
class TrackSerializer(serializers.ModelSerializer):
    track_albums = serializers.PrimaryKeyRelatedField(source='albums', many=True, read_only=True) 
    # source - 참조할 값을 정의하는 옵션
    
    class Meta:
        model = Track
        fields = ['id', 'name', 'track_albums', ...]
```


## StringRelatedField
- DRF에서 관계 직렬화 할 때 객체의 `__str__()` 메소드가 사용되도록 설정

```python
class Track(models.Model):
    ...

    def __str__(self):
        return self.name
```
```python
class AlbumSerializer(serializers.ModelSerializer):
    tracks = serializers.StringRelatedField(many=True)
    # 조회만 가능한 필드이기 때문에 read_only를 추가하지 않아도 됨

    class Meta:
        model = Album
        fields = ['id', 'name', 'tracks', ...]
```


## Nested Serializer
- 관련된 객체의 모든 필드를 직렬화 할 때 사용
- 참조하는 Serializer가 위에 있어야 함

```python
class AlbumSerializer(serializers.ModelSerializer):
    ...

class TrackSerializer(serializers.ModelSerializer):
    album = AlbumSerializer(read_only=True)

    class Meta:
        model = Track
        fields = ['id', 'name', 'album', ...]
```