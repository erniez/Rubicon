class Car
  def initialize
    @engine = Engine.new
    @name = ""
    @count = 0
  end
end

class User
  def initialize(repo)
    @repo = UserRepository.new
    @name = "default"
  end
end
