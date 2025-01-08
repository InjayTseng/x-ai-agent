from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwitterScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.reply_interval = int(os.getenv('REPLY_INTERVAL', 30))  # minutes
        self.post_interval = int(os.getenv('POST_INTERVAL', 120))   # minutes
        
    def start(self, reply_func, post_func, learn_func):
        """
        Start the scheduler with the specified functions
        
        Args:
            reply_func: Function to handle replying to tweets
            post_func: Function to handle creating new posts
            learn_func: Function to handle learning from tweets
        """
        try:
            # Schedule reply job
            self.scheduler.add_job(
                reply_func,
                trigger=IntervalTrigger(minutes=self.reply_interval),
                id='reply_job',
                name='Reply to tweets'
            )
            
            # Schedule post job
            self.scheduler.add_job(
                post_func,
                trigger=IntervalTrigger(minutes=self.post_interval),
                id='post_job',
                name='Create new posts'
            )
            
            # Schedule learning job (every 15 minutes)
            self.scheduler.add_job(
                learn_func,
                trigger=IntervalTrigger(minutes=15),
                id='learn_job',
                name='Learn from tweets'
            )
            
            # Start the scheduler
            self.scheduler.start()
            logger.info("Scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
            raise
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def modify_intervals(self, reply_interval: int = None, post_interval: int = None):
        """
        Modify the intervals for reply and post jobs
        
        Args:
            reply_interval: New interval for reply job in minutes
            post_interval: New interval for post job in minutes
        """
        if reply_interval:
            self.reply_interval = reply_interval
            self.scheduler.reschedule_job(
                'reply_job',
                trigger=IntervalTrigger(minutes=reply_interval)
            )
            
        if post_interval:
            self.post_interval = post_interval
            self.scheduler.reschedule_job(
                'post_job',
                trigger=IntervalTrigger(minutes=post_interval)
            )
            
        logger.info(f"Updated intervals - Reply: {self.reply_interval}m, Post: {self.post_interval}m")
