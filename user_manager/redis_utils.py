import json
import redis
import os

TTL = 24 * 3600

class RedisCache:
    """
    Wrapper for Redis used to store idempotency keys for incoming HTTP requests.

    Attributes:
        client (redis.Redis | None): The Redis client instance, or None if Redis is unavailable or the connection failed.

    Methods:
        request_already_processed(req_id: str) -> bool
            Checks whether a request ID was already processed by querying Redis.

        save_request(req_id: str, ttl: int = 86400) -> None
            Stores the request ID in Redis with a TTL to flag it as processed.
    """

    def __init__(self):
        """
        Initializes the Redis client using the REDIS_URL environment variable.
        If the connection fails, the client is set to None.
        """
        redis_url = os.getenv("REDIS_URL")
        try:
            self.client = redis.Redis.from_url(redis_url)
            self.client.ping()
        except Exception:
            self.client = None


    def is_available(self) -> bool:
        """
        Checks if the Redis client is available.
        """
        return self.client is not None


    def request_already_processed(self, req_id: str) -> bool:
        """
        Checks whether the given request ID is already present in Redis.
        """
        return self.client.exists(req_id)


    def save_request_result(self, req_id, result: dict) -> None:
        """
        Store the outcome of a processed request in Redis.
        Args:
            req_id (str): The unique request identifier.
            result (dict): The result data to store.
        """
        self.client.set(req_id, json.dumps(result), ex=TTL, nx=True)


    def get_request_result(self, req_id) -> dict | None:
        """
        Retrieve the previously stored result of a request from Redis.
        Args:
            req_id (str): The unique request identifier.
        Returns:
            dict | None: The stored result if found, otherwise None.
        """
        val = self.client.get(req_id)
        return json.loads(val) if val else None