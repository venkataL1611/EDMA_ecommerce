import os
import redis

class RedisUtil:
    def __init__(self):
        self.client = redis.StrictRedis(
            host=os.getenv("REDIS_HOST"),
            port=int(os.getenv("REDIS_PORT")),
            decode_responses=True,
        )

    def set_key(self, key, value, ttl=3600):
        self.client.set(key, value, ex=ttl)

    def get_key(self, key):
        return self.client.get(key)

    def delete_key(self, key):
        self.client.delete(key)

    def get_keys_by_pattern(self, pattern):
        return self.client.keys(pattern)

redis_util = RedisUtil()