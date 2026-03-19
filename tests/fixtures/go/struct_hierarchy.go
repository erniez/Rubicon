package main

type Animal struct {
	Name string
}

type Dog struct {
	Animal
	Pet
	Breed string
}

type GuideDog struct {
	Dog
	Trainable
	Certifiable
	Handler string
}
