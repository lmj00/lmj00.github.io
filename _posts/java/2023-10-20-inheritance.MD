---
title: "Java 상속"
layout: post
categories: java
--- 


### 상속 (Inheritance)
> 자식 클래스에서 부모 클래스의 변수와 메서드를 사용할 수 있다.

```java
public class Parent {
    String name = "이름";
    void method() {
        System.out.println("부모 메서드");
    }
}


public class Child extends Parent {

}


public class Main {
    public static void main(String[] args) {
        Child c1 = new Child();

        System.out.println(c1.name);
        c1.method();
    }
}


// 출력
이름
부모 메서드
```

<br>

> 자식 클래스가 부모 클래스의 메서드를 덮어서 사용하려면 `메서드 오버라이딩`을 해줘야 한다.

```java
public class Parent {
    void method() {
        System.out.println("메서드");
    }
}


public class Child extends Parent {
    @Override
    void method() {
        System.out.println("자식 메서드");
    }
}


public class Main {
    public static void main(String[] args) {
        Child c1 = new Child();
        c1.method();
    }
}

// 출력
자식 메서드
```

### super
> 자식 클래스가 부모 클래스의 변수, 메서드 또는 생성자를 사용할 때 사용한다.

> `super`를 사용하지 않고 부모 클래스에 접근은 가능하지만, `super`를 사용하는 것이 가독성에 좋다.

<br>

변수나 메서드를 사용할 때

```java
public class Parent {
    String name = "부모 변수";

    void parentMethod() {
        System.out.println("부모 메서드");
    }
}


public class Child extends Parent {
    String name = "자식 변수";

    void childMethod() {
        String parentName = super.name;
        super.parentMethod();

        System.out.println(parentName);
        System.out.println("자식 메서드");
    }
}

public class Main {
    public static void main(String[] args) {
        Child c1 = new Child();
        c1.childMethod();
    }
}
 
// 출력
부모 메서드
부모 변수
자식 메서드
```

> 부모와 자식의 변수명이 같을 경우, 구분하기 위해 `super`를 사용할 때도 있다.


<br>


생성자를 사용할 때

```java
public class Parent {
    String name;

    public Parent(String name) {
        this.name = name;
    }
}


public class Child extends Parent {
    public Child(String name) {
        super(name);
    }
}


public class Main {
    public static void main(String[] args) {
        Child c1 = new Child("테스트");
        System.out.println(c1.name);
    }
}

// 출력
테스트
```

<br>


생성자에서의 사용 규칙

> 자식 클래스의 인스턴스 생성 시 부모 클래스의 생성자는 반드시 불린다.

> 부모 클래스의 생성자를 호출할 때, 자식 클래스의 생성자 안에서 맨 윗줄에 적어야 한다.

> 자식 클래스에서 부모 클래스의 생성자를 호출하지 않으면, 부모 클래스의 기본 생성자를 호출한다.

> 부모 클래스의 생성자가 없으면, 자식 클래스는 부모 클래스의 기본 생성자를 부른다.

> 부모 클래스에 파라미터를 받는 생성자가 있으면 반드시 해당 파라미터를 전달해줘야 한다.



### Object Class
> 모든 클래스는 `Object` 클래스를 상속받는다. 

> 자바의 모든 객체는 `Object`클래스의 메서드들을 사용할 수 있다. toString(), equals(), clone() ...

```java
public class Parent {
    String name;

    public Parent(String name) {
        this.name = name;
    }

    @Override
    public String toString() {
        return name;
    }
}


public class Main {
    public static void main(String[] args) {
        Child c1 = new Child("테스트");
        System.out.println(c1);
    }
}

// 출력
테스트  
```

> `System.out.print()` 메서드는 객체를 출력하게 되면 `toString()` 메서드를 호출한다. 

> `toString()`은 객체의 클래스 이름과 해시 코드가 출력된다.

>  오버라이딩을 해서 원하는 출력으로 변경하면, 오버라이딩이 된 `toString()` 메서드를 호출하여 위와 같은 출력이 나오게 된다.