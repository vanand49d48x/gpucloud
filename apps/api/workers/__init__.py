#!/usr/bin/env python3
"""
GPUCloud Worker System - Production Grade
"""

import os
import sys
import signal
import logging
import time
from typing import Optional
from rq import Worker, Queue
from rq.worker import WorkerStatus
from redis import Redis
import threading

# Import job functions so they can be found by RQ
from .provisioner import provision_pod, teardown_pod

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GPUCloudWorker:
    """Production-grade worker with health monitoring and auto-recovery"""
    
    def __init__(self, queue_name: str = 'provision', redis_url: str = 'redis://localhost:6379'):
        self.queue_name = queue_name
        self.redis_url = redis_url
        self.worker: Optional[Worker] = None
        self.health_check_thread: Optional[threading.Thread] = None
        self.running = False
        self.last_heartbeat = time.time()
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """Start the worker with health monitoring"""
        logger.info(f"Starting GPUCloud worker for queue: {self.queue_name}")
        self.running = True
        
        try:
            # Start health monitoring in background
            self.health_check_thread = threading.Thread(target=self._health_monitor, daemon=True)
            self.health_check_thread.start()
            
            # Start the worker
            queue = Queue(self.queue_name, connection=Redis.from_url(self.redis_url))
            self.worker = Worker([queue], name=f"gpucloud-{self.queue_name}")
            
            # Configure worker with production settings
            self.worker.work(
                job_timeout=300,  # 5 minute job timeout
                result_ttl=3600,  # Keep results for 1 hour
                job_monitoring_interval=30,  # Check job health every 30s
                max_jobs=10,  # Process max 10 jobs before restart
                with_scheduler=True  # Enable job scheduling
            )
                
        except Exception as e:
            logger.error(f"Worker failed to start: {e}")
            self.running = False
            raise
    
    def stop(self):
        """Stop the worker gracefully"""
        logger.info("Stopping GPUCloud worker...")
        self.running = False
        
        if self.worker:
            self.worker.shutdown()
        
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=5)
    
    def _health_monitor(self):
        """Background health monitoring thread"""
        while self.running:
            try:
                # Check worker health every 30 seconds
                time.sleep(30)
                
                if self.worker and self.worker.state != WorkerStatus.BUSY:
                    # Worker is idle, update heartbeat
                    self.last_heartbeat = time.time()
                
                # Check if worker is stuck (no heartbeat for 2 minutes)
                if time.time() - self.last_heartbeat > 120:
                    logger.warning("Worker appears stuck, restarting...")
                    self._restart_worker()
                    
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
    
    def _restart_worker(self):
        """Restart the worker if it's stuck"""
        try:
            logger.info("Restarting worker...")
            if self.worker:
                self.worker.shutdown()
            
            # Wait a moment before restarting
            time.sleep(5)
            
            # Restart worker
            queue = Queue(self.queue_name, connection=Redis.from_url(self.redis_url))
            self.worker = Worker([queue], name=f"gpucloud-{self.queue_name}-restarted")
            self.worker.work(
                job_timeout=300,
                result_ttl=3600,
                job_monitoring_interval=30,
                max_jobs=10,
                with_scheduler=True
            )
                
        except Exception as e:
            logger.error(f"Failed to restart worker: {e}")

def main():
    """Main entry point for the worker"""
    try:
        # Get queue name from environment or default to 'provision'
        queue_name = os.getenv('WORKER_QUEUE', 'provision')
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        worker = GPUCloudWorker(queue_name, redis_url)
        worker.start()
        
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
