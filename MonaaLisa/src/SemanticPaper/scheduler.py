import threading
import queue
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from Database.db import db_base, engine
from util.logger import Logger
from SemanticPaper.api.arxiv import fetch_papers, fetch_historical_batch
from SemanticPaper.api.arxiv import rate_limiter 
from SemanticPaper.config.category_loader import get_semanticpaper_categories
from Database.db import (
    create_program_run,
    is_category_historically_completed,
    mark_category_historically_completed,
    start_category_historical_fetch
)

logger = Logger("Scheduler")

# Queue to buffer fetched Paper objects for embedding workers
paper_queue = queue.Queue(maxsize=50)

current_program_run_id = None
scheduler_lock = threading.Lock()
historical_fetch_state = {"running": False}


"""
13-August-2025 - Basti
Abstract: Fetches the newest paper (1 per category) daily and enqueues into paper_queue.
Args:
- None
Returns: None
"""
def daily_fetch():
    categories = get_semanticpaper_categories()
    logger.info(f"Fetching newest paper for categories: {categories}")
    for cat in categories:
        rate_limiter.wait()
        papers = fetch_papers(category=cat, amount=1)
        for paper in papers:
            if paper:
                try:
                    paper_queue.put_nowait(paper)  
                    logger.info(f"Enqueued paper: {paper.title} (queue size: {paper_queue.qsize()})")
                except queue.Full:
                    logger.warning(f"Queue full, skipping paper: {paper.title}")
                    break
                except Exception as e:
                    logger.error(f"Error queuing daily paper: {e}")
                    break

"""
13-August-2025 - Basti
Abstract: Fetches historical papers in batches per category and enqueues into paper_queue.
Args:
- None
Returns: None
"""
def historical_fetch():
    global current_program_run_id
    with scheduler_lock:
        if historical_fetch_state["running"]:
            logger.info("Historical fetch already in progress")
            return
        historical_fetch_state["running"] = True
    try:
        if not current_program_run_id:
            logger.error("No active program run ID")
            return
        categories = get_semanticpaper_categories()
        for cat in categories:
            if is_category_historically_completed(current_program_run_id, cat):
                continue
            
            start_category_historical_fetch(current_program_run_id, cat)
            
            offset = historical_fetch_state.get(cat, 0)
            total_papers_queued = 0
            
            while True:
                if paper_queue.qsize() >= 45:  
                    logger.info(f"Queue nearly full ({paper_queue.qsize()}/50), waiting for space to continue {cat} at offset {offset}")
                    threading.Event().wait(2)  
                    continue
                    
                rate_limiter.wait()
                papers, has_more = fetch_historical_batch(cat, batch_size=50, start_offset=offset)
                
                if papers:
                    papers_queued = 0
                    queue_full_hit = False
                    for paper in papers:
                        if paper:
                            try:
                                paper_queue.put_nowait(paper)  
                                papers_queued += 1
                                total_papers_queued += 1
                            except queue.Full:
                                logger.warning(f"Queue full (size: {paper_queue.qsize()}), pausing {cat} fetch at offset {offset}")
                                historical_fetch_state[cat] = offset
                                queue_full_hit = True
                                break  
                            except Exception as e:
                                logger.error(f"Error queuing paper for {cat}: {e}")
                                break
                    
                    if queue_full_hit:
                        logger.info(f"Waiting for queue space, will retry {cat} at offset {offset}")
                        threading.Event().wait(5)  
                        continue
                        
                    logger.info(f"Enqueued {papers_queued}/{len(papers)} papers for {cat} at offset {offset} (total: {total_papers_queued}, queue size: {paper_queue.qsize()})")
                else:
                    logger.warning(f"No papers fetched for category {cat} at offset {offset}")
                
                offset += 50
                historical_fetch_state[cat] = offset
                
                if not has_more:
                    mark_category_historically_completed(current_program_run_id, cat)
                    logger.info(f"Category {cat} historical fetch completed - processed {total_papers_queued} total papers")
                    break
    except Exception as e:
        logger.error(f"Error in historical_fetch: {e}")
    finally:
        with scheduler_lock:
            historical_fetch_state["running"] = False

"""
13-August-2025 - Basti
Abstract: Starts the background scheduler for daily and historical fetch tasks.
Args:
- None
Returns: BackgroundScheduler
"""
def start_scheduler():
    global current_program_run_id
    if BackgroundScheduler is None:
        logger.error("Cannot start scheduler: APScheduler missing")
        return None
    db_base.metadata.create_all(bind=engine)
    current_program_run_id = create_program_run()
    if not current_program_run_id:
        logger.error("Failed to create program run")
        return None
    scheduler = BackgroundScheduler()
    # Schedule daily_fetch at 0,6,12,18
    for hr in [0, 6, 12, 18]:
        scheduler.add_job(daily_fetch, 'cron', hour=hr, minute=0, id=f"daily_fetch_{hr}")
    # Schedule historical_fetch 
    scheduler.add_job(historical_fetch, 'interval', minutes=2, next_run_time=datetime.now(), id='historical_fetch')
    scheduler.start()
    logger.info(f"Scheduler started (run ID {current_program_run_id})")
    return scheduler
