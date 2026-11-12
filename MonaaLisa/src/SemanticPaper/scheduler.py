import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from Database.db import db_base, engine

from SemanticPaper.api.arxiv import ArxivAPI
from config import cfg
from util.logger import Logger
from SemanticPaper.config.category_loader import get_semanticpaper_categories
from Database.db import (
    create_program_run,
    is_category_historically_completed,
    mark_category_historically_completed,
    ensure_historical_start,
    update_historical_progress,
    set_active_program_run,
    program_run_exists,
)
import threading
import queue
import json
from pathlib import Path


"""
30-September-2025 - Lenio
Refactored from scheduler.py coded by Basti on 13-August-2025
"""
class Scheduler:

    def __init__(self, arxiv_client: ArxivAPI):
        self._arxiv_client = arxiv_client
        self.logger = Logger("Scheduler")
        self._current_program_run_id = None
        self.scheduler_lock = threading.Lock()
        self.historical_fetch_state = {"running": False}
        self.goal_dates_cache = {}
        # Tuning knobs via env vars
        self.HISTORICAL_FETCH_INTERVAL_SECONDS = cfg.get_int(
            "semanticpaper",
            "historical_fetch_interval_seconds",
            int(os.getenv("HISTORICAL_FETCH_INTERVAL_SECONDS", "60"))
        )
        self.QUEUE_MAX_SIZE = cfg.get_int(
            "semanticpaper",
            "queue_max_size",
            int(os.getenv("QUEUE_MAX_SIZE", "200"))
        )
        # Initialize bounded queue now that QUEUE_MAX_SIZE is defined
        self.paper_queue = queue.Queue(maxsize=self.QUEUE_MAX_SIZE)
        # for now save the historical state to disk, easier and quicker than to save to the db
        # might change later but this is fine for now
        default_state_path = os.getenv("HISTORICAL_STATE_PATH", "/app/.cache/historical_state.json")
        state_path_value = cfg.get("semanticpaper", "historical_state_path", default_state_path) or default_state_path
        self.state_path = Path(state_path_value)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_dirty = False
        self._load_historical_state()


    """
    12-November-2025 - Basti
    Abstract: Attempts to enqueue a paper without blocking; returns False if the queue is full.
    """
    def _enqueue_paper(self, paper) -> bool:
        if paper is None:
            return False
        try:
            self.paper_queue.put_nowait(paper)
            return True
        except queue.Full:
            title = getattr(paper, "title", "Unknown Title")
            self.logger.warning(
                f"Paper queue capacity ({self.QUEUE_MAX_SIZE}) reached; dropping '{title}'"
            )
            return False


    """
    30-September-2025 - Lenio
    Abstract: Checks whether the scheduler is running
    Returns: bool indicating if the scheduler is running
    """
    def is_running(self) -> bool:
        return self._current_program_run_id is not None

    """
    13-August-2025 - Basti
    Abstract: Fetches the newest paper (1 per category) daily and enqueues into paper_queue.
    Args:
    - None
    Returns: None
    """
    def daily_fetch(self):
        categories = get_semanticpaper_categories()
        self.logger.info(f"Fetching newest paper for categories: {categories}")
        for cat in categories:
            self._arxiv_client.get_rate_limiter().wait()
            papers = self._arxiv_client.fetch_papers(category=cat, amount=1)
            for paper in papers:
                if paper:
                    if not self._enqueue_paper(paper):
                        self.logger.info(
                            "Skipped enqueuing newest paper for %s because the queue is full",
                            cat
                        )
                        break
                    self.logger.info(f"Enqueued paper: {paper.title}")

    """
    13-August-2025 - Basti
    Abstract: Fetches historical papers in batches per category and enqueues into paper_queue.
    Args:
    - None
    Returns: None
    """
    def historical_fetch(self):
        with self.scheduler_lock:
            if self.historical_fetch_state["running"]:
                self.logger.info("Historical fetch already in progress")
                return
            self.historical_fetch_state["running"] = True
        try:
            try:
                qsize = self.paper_queue.qsize()
            except NotImplementedError:
                qsize = 0
            if qsize >= self.QUEUE_MAX_SIZE:
                self.logger.info(f"Queue size {qsize} >= max {self.QUEUE_MAX_SIZE}; skipping fetch this cycle")
                return
            if not self.is_running():
                self.logger.error("No active program run ID")
                return
            categories = get_semanticpaper_categories()
            for cat in categories:
                if is_category_historically_completed(self._current_program_run_id, cat):
                    continue
                goal_date = self.goal_dates_cache.get(cat)
                if goal_date is None:
                    try:
                        papers_goal, _ = self._arxiv_client.fetch_historical_batch(cat, batch_size=1, start_offset=0)
                        goal_date = papers_goal[0].published if papers_goal else None
                        self.goal_dates_cache[cat] = goal_date
                        self._state_dirty = True
                    except Exception as e:
                        self.logger.error(f"Failed to determine goal date for {cat}: {e}")
                        goal_date = None
                # Ensure we have a start record for this category/runwith optional goal
                if not ensure_historical_start(self._current_program_run_id, cat, goal_date):
                    self.logger.info(f"Skipping {cat} this cycle: could not create start record")
                    continue
                offset = self.historical_fetch_state.get(cat, 0)
                self._arxiv_client.get_rate_limiter().wait()
                papers, has_more = self._arxiv_client.fetch_historical_batch(cat, batch_size=50, start_offset=offset)
                if papers:
                    enqueued_count = 0
                    for paper in papers:
                        if paper:
                            if not self._enqueue_paper(paper):
                                self.logger.info(
                                    f"Queue full while enqueuing historical papers for {cat}; remaining batch dropped"
                                )
                                break
                            enqueued_count += 1
                    self.logger.info(f"Enqueued {enqueued_count} historical papers for {cat}")
                    try:
                        min_date = min(p.published for p in papers if p is not None)
                        update_historical_progress(self._current_program_run_id, cat, min_date)
                    except Exception as e:
                        self.logger.error(f"Failed updating progress for {cat}: {e}")
                self.historical_fetch_state[cat] = offset + (len(papers) if papers else 0)
                self._state_dirty = True
                if not has_more:
                    final_oldest = None
                    if papers and len(papers) > 0:
                        try:
                            final_oldest = min(p.published for p in papers if p is not None)
                        except Exception:
                            final_oldest = None
                    mark_category_historically_completed(self._current_program_run_id, cat, final_oldest)
                    self.logger.info(f"Category {cat} historical fetch completed")
                    self._state_dirty = True
                self._persist_historical_state()
        except Exception as e:
             self.logger.error(f"Error in historical_fetch: {e}")
        finally:
            with self.scheduler_lock:
                self.historical_fetch_state["running"] = False
            self._persist_historical_state(force=True)

    """
    13-August-2025 - Basti
    Abstract: Starts the background scheduler for daily and historical fetch tasks.
    Args:
    - None
    Returns: BackgroundScheduler
    """
    def start_scheduler(self):
        if BackgroundScheduler is None:
            self.logger.error("Cannot start scheduler: APScheduler missing")
            return None
        db_base.metadata.create_all(bind=engine)
        #  Try to reuse existing program run if possible
        #  this is done by checking if the stored ID exists 
        # 
        if self._current_program_run_id and program_run_exists(self._current_program_run_id):
            if not set_active_program_run(self._current_program_run_id):
                self.logger.warning(
                    f"Failed to reactivate stored ProgramRun ID {self._current_program_run_id}; creating a new run"
                )
                self._current_program_run_id = create_program_run()
            else:
                self.logger.info(f"Reusing ProgramRun ID {self._current_program_run_id}")
        else:
            self._current_program_run_id = create_program_run()
        self._state_dirty = True
        self._persist_historical_state()
        if not self.is_running():
            self.logger.error("Failed to create program run")
            return None
        scheduler = BackgroundScheduler()
        # Schedule daily_fetch at 0,6,12,18
        for hr in [0, 6, 12, 18]:
            scheduler.add_job(self.daily_fetch, 'cron', hour=hr, minute=0, id=f"daily_fetch_{hr}")
        # Schedule historical_fetch  start now
        scheduler.add_job(
            self.historical_fetch,
            'interval',
            seconds=self.HISTORICAL_FETCH_INTERVAL_SECONDS,
            next_run_time=datetime.now(),
            id='historical_fetch'
        )
        scheduler.start()
        self.logger.info(f"Scheduler started (run ID {self._current_program_run_id})")
        return scheduler

    def shutdown(self):
        self._persist_historical_state(force=True)

    """ 20-December-2025 - Basti
    Abstract: Loads historical fetch state from disk if available.
    Args: None
    Returns: None
    """
    def _load_historical_state(self):
        if not self.state_path.exists():
            return
        try:
            # Load JSON data from the state file
            with self.state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            # fall back 
            self.logger.warning(f"Failed to load historical state: {exc}")
            return
    # retrieve offsets/positions where we last stopped
        offsets = data.get("offsets", {})
        if isinstance(offsets, dict):
            restored = 0
            with self.scheduler_lock:
                for category, value in offsets.items():
                    try:
                        numeric = int(value)
                    except (ValueError, TypeError):
                        continue
                    if numeric < 0:
                        continue
                    self.historical_fetch_state[category] = numeric
                    restored += 1
                self.historical_fetch_state["running"] = False
            if restored:
                self.logger.info(f"Restored historical offsets for {restored} categories")
        # retrieve program run ID 
        program_run_id = data.get("program_run_id")

        if isinstance(program_run_id, int):
            self._current_program_run_id = program_run_id

        goal_dates = data.get("goal_dates", {})
        if isinstance(goal_dates, dict):
            for category, iso_value in goal_dates.items():
                if not isinstance(iso_value, str):
                    continue
                try:
                    parsed = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
                except Exception:
                    continue
                self.goal_dates_cache[category] = parsed

        self._state_dirty = False

    """ 20-December-2025 - Basti
    Abstract: Persists historical fetch state to disk if dirty or forced
    Args:
    - force: bool = False -> Whether to force persistence even if not dirty
    Returns: None   
    """
    def _persist_historical_state(self, force: bool = False):
        if not force and not self._state_dirty:
            return
        try:
            with self.scheduler_lock:
                offsets = {
                    category: value
                    for category, value in self.historical_fetch_state.items()
                    if category != "running" and isinstance(value, int) and value >= 0
                }
            payload = {
                "program_run_id": self._current_program_run_id,
                "offsets": offsets,
                "goal_dates": {
                    category: value.isoformat()
                    for category, value in self.goal_dates_cache.items()
                    if isinstance(value, datetime)
                },
            }
            temp_path = self.state_path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            temp_path.replace(self.state_path)
            self._state_dirty = False
        except Exception as exc:
            self.logger.warning(f"Failed to persist historical state: {exc}")
