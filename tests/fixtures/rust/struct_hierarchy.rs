struct Animal {
    name: String,
}

trait Pet {
    fn name(&self) -> &str;
}

trait Trainable {
    fn train(&self);
}

trait Certifiable {
    fn certify(&self);
}

impl Pet for Dog {
    fn name(&self) -> &str { &self.name }
}

struct Dog {
    name: String,
    breed: String,
}

impl Trainable for GuideDog {
    fn train(&self) {}
}

impl Certifiable for GuideDog {
    fn certify(&self) {}
}
