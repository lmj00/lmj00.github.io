---
title: "Java Interface, Abstract"
layout: post
categories: java
--- 
 

### [Interface](https://docs.oracle.com/javase/tutorial/java/concepts/interface.html)
> 객체가 어떤 동작을 수행하는지만 정의하고, 실제 동작 구현은 인터페이스를 구현하는 클래스에서 이뤄지는 것을 의미한다. -> 해당 클래스가 이러한 기능을 하는 메서드들 가지고 있다는 것을 표현

> 상속은 하나의 클래스만 가능하지만, 인터페이스는 다중 구현이 가능하다.

```java
interface Bicycle {
    void speedUp(int increment);

    void applyBrakes(int decrement);
}


class RoadBike implements Bicycle {
    int speed = 0;

    @Override
    public void speedUp(int increment) {
         speed = speed + increment;   
    }

    @Override
    public void applyBrakes(int decrement) {
         speed = speed - decrement;
    }
}
```
> 구현 받은 클래스는 인터페이스에 있는 모든 메서드를 구현해야 컴파일 오류가 나지 않는다.

> 외부 클래스가 인터페이스를 구현 받기 때문에 메서드들의 `public abstract`으로 선언되어야 한다.

> 기본 선언이 `public abstract` 이기 때문에 생략할 수 있다.

> 상수만 가질 수 있다. 변수의 기본 선언은 `public static final`이기 때문에 생략할 수 있다.


### [Abstract](https://docs.oracle.com/javase/tutorial/java/IandI/abstract.html)
> 일반 메서드와 추상 메서드를 모두 선언할 수 있다.

> 상속받은 클래스는 추상 클래스의 추상 메서드를 모두 선언해 줘야 오류가 나지 않는다.

> `public` 이외의 접근 제어자가 선언할 수 있다.

> 다중 상속 불가능

<br>

```java
public abstract class Bicycle {
    int speed;

    public abstract void speedUp(int increment);

    void applyBrakes(int decrement) {
        speed -= decrement;
    }
}


class RoadBike extends Bicycle {
    @Override
    public void speedUp(int increment) {
        speed += increment;
    }
}


public class ElectricBike extends Bicycle {
    @Override
    public void speedUp(int increment) {
        speed += increment * 2;
    }
}


public class Main {
    public static void main(String[] args) {

        RoadBike roadBike = new RoadBike();
        roadBike.speed = 10;
        roadBike.speedUp(10);
        roadBike.applyBrakes(20);

        ElectricBike electricBike = new ElectricBike();
        electricBike.speed = 10; // 10
        electricBike.speedUp(10); // 30
        electricBike.applyBrakes(10); // 20
    }
}
```

> 추상 메서드에 `abstract` 제어자를 꼭 붙여줘야 한다.


### [익명 클래스](https://docs.oracle.com/javase/tutorial/java/javaOO/anonymousclasses.html)
> 클래스를 선언하고 동시에 인스턴스를 생성할 수 있다.

> 주로 클래스를 한 번만 사용할 때 사용한다.


```java
public abstract class Bicycle {
    int speed;

    public abstract void speedUp(int increment);
    
    void applyBrakes(int decrement) {
        speed -= decrement;
    }
}


public class Main {
    public static void main(String[] args) {

        Bicycle electricBike = new Bicycle() {
            @Override
            public void speedUp(int increment) {
                speed += increment * 2;
            }
        };

        electricBike.speedUp(10); // 20
        electricBike.applyBrakes(10); // 10
    }
}
```