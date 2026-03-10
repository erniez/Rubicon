class Dog : Animal(), Pet {
    fun bark() {}
}

class GuideDog : Dog(), Trainable, Certifiable {
    fun guide() {}
}
