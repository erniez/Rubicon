class Animal {
    String name;
}

interface Pet {
    String name();
}

interface Trainable {
    void train();
}

interface Certifiable {
    void certify();
}

class Dog extends Animal implements Pet {
    String breed;
    public String name() { return ""; }
}

class GuideDog extends Dog implements Trainable, Certifiable {
    String handler;
    public void train() {}
    public void certify() {}
}
