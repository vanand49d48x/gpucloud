import os
from dotenv import load_dotenv  # add this
import redis
from rq import Queue

load_dotenv()  # ensure REDIS_URL from .env is loaded in both processes

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = redis.from_url(REDIS_URL)
q = Queue("provision", connection=redis_conn)
