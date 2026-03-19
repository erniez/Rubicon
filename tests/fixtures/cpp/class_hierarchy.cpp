class Animal {
public:
    string name;
};

class Pet {
public:
    virtual string name() = 0;
};

class Trainable {
public:
    virtual void train() = 0;
};

class Certifiable {
public:
    virtual void certify() = 0;
};

class Dog : public Animal, public Pet {
public:
    string breed;
    string name() override { return ""; }
};

class GuideDog : public Dog, public Trainable, public Certifiable {
public:
    string handler;
    void train() override {}
    void certify() override {}
};
