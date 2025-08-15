import os
import multiprocessing

# Fix for macOS multiprocessing issues
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
# Use spawn method instead of fork on macOS
if os.name == 'posix' and os.uname().sysname == 'Darwin':
    multiprocessing.set_start_method('spawn', force=True)

from rq import Worker
from apps.api.app.queue import redis_conn

if __name__ == "__main__":
    worker = Worker(["provision"], connection=redis_conn)
    worker.work()
