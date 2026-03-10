class Dog extends Animal implements Pet {
    bark(): void {}
}

class GuideDog extends Dog implements Trainable, Certifiable {
    guide(): void {}
}
