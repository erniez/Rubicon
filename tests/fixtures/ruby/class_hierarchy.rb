class Animal
  def speak
  end
end

module Pet
  def name
  end
end

module Trainable
  def train
  end
end

module Certifiable
  def certify
  end
end

class Dog < Animal
  include Pet
end

class GuideDog < Dog
  include Trainable
  include Certifiable
end
