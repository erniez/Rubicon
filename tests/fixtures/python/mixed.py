import logging
from models import BaseModel

class UserService(BaseModel):
    repo: UserRepository
    cache: CacheManager

    def get_user(self, user_id: int):
        pass
