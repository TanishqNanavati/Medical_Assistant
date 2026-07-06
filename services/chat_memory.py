import redis
import json
from config import settings

class ChatMemory:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True
        )

        self.max_turns = 5
        self.ttl = 60 * 60 * 24 # 1 day

    def _get_key(self,user_id:int,session_id:str):
        return f"chat_history:{user_id}:{session_id}"

    def get_history(self,user_id:int,session_id:str):
        if not session_id:
            return []
        key = self._get_key(user_id,session_id)
        history = self.redis_client.lrange(key,0,-1)
        return [json.loads(msg) for msg in history]

    def add_turn(self,user_id:int,session_id:str,question:str,answer:str):
        if not session_id:
            return 

        key = self._get_key(user_id,session_id)

        user_msg = json.dumps({"role":"user","content":question})
        ai_msg = json.dumps({"role":"assistant","content":answer})

        self.redis_client.rpush(key,user_msg,ai_msg)

        max_messages = self.max_turns * 2 # user + ai
        self.redis_client.ltrim(key,start=-max_messages,end=-1)

        self.redis_client.expire(key,self.ttl)



chat_memory = ChatMemory()