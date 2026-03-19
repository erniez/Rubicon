class Animal {
    string Name;
}

interface IPet {
    string Name { get; }
}

interface ITrainable {
    void Train();
}

interface ICertifiable {
    void Certify();
}

class Dog : Animal, IPet {
    string Breed;
    public string Name { get { return ""; } }
}

class GuideDog : Dog, ITrainable, ICertifiable {
    string Handler;
    public void Train() {}
    public void Certify() {}
}
