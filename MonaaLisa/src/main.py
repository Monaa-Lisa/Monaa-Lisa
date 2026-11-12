"""
Abstract: Entry point of the SemanticPaper application (refactored).

New flow:
    1. First run -> download dataset + models from Google Drive -> import into DB
    2. Every run  -> ensure pre-trained models (PCA + UMAP) are present
    3. Load the EmbeddingPipeline (768 ->128 ->2D)
    4. Run an immediate incremental update (arXiv gap-fill)
    5. Schedule monthly incremental updates and bi-weekly uncaught-paper retries
    6. Wait for shutdown signal
"""

import os
import sys
import signal
import faulthandler
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from config import cfg
from util.logger import Logger
from Database.db import is_database_empty, engine
from Database.db_models import db_base
from SemanticPaper.api.semantic_scholar import SemanticScholarAPI
from SemanticPaper.api.arxiv import ArxivAPI
from SemanticPaper.data.downloader import (
    ensure_all_downloaded,
    ensure_models_exist,
    get_dataset_path,
    cleanup_dataset,
)
from SemanticPaper.data.importer import run_import
from SemanticPaper.pipeline.embedding_pipeline import EmbeddingPipeline
from SemanticPaper.pipeline.incremental import (
    run_incremental_update,
    retry_uncaught_papers,
)

logger = Logger("Main")

load_dotenv()

try:
    faulthandler.enable()
except Exception:
    pass


def main():
    log_level = cfg.get("semanticpaper", "log_level", os.getenv("LOG_LEVEL", "DEBUG"))
    logger.set_level(log_level)
    logger.info(f"SemanticPaper starting (log level={log_level})...")

    # ---- 1. Database Check (WAIT for Prisma) ----
    # WICHTIG: Wir erstellen keine Tabellen mehr selbst!
    # Wir warten stattdessen kurz, bis die DB erreichbar ist.
    logger.info("Checking database connection...")
    
    # Einfacher Retry-Loop, falls der DB-Container noch nicht bereit ist
    for i in range(10):
        try:
            with engine.connect() as connection:
                logger.info("Database connection established.")
                break
        except Exception as e:
            logger.warning(f"Database not ready yet, retrying in 2s... ({e})")
            time.sleep(2)
    else:
        logger.error("Could not connect to database after 20s. Exiting.")
        sys.exit(1)

    # ---- 2. First-run: download & import ----
    first_run = is_database_empty()
    if first_run:
        logger.info("First run detected – database is empty.")
        logger.info("Downloading dataset and pre-trained models from Google Drive...")

        if not ensure_all_downloaded():
            logger.error("Failed to download required files. Exiting.")
            sys.exit(1)

        dataset_path = get_dataset_path()
        batch_size = cfg.get_int("semanticpaper", "import_batch_size", int(os.getenv("IMPORT_BATCH_SIZE", "20000")))
        logger.info(f"Importing dataset from {dataset_path} ...")

        if not run_import(dataset_path, batch_size):
            logger.error("Dataset import failed. Exiting.")
            sys.exit(1)

        logger.info("Dataset imported successfully. Cleaning up raw file...")
        cleanup_dataset()
    else:
        logger.info("Existing data found in database.")
        logger.info("Ensuring pre-trained models are available...")
        if not ensure_models_exist():
            logger.error("Failed to ensure ML models are present. Exiting.")
            sys.exit(1)

    # ---- 3. Load the embedding pipeline ----
    logger.info("Loading EmbeddingPipeline (PCA + UMAP)...")
    try:
        pipeline = EmbeddingPipeline()
    except FileNotFoundError as e:
        logger.error(f"Cannot load pipeline models: {e}")
        sys.exit(1)
    logger.info("EmbeddingPipeline ready.")

    # ---- 4. Initialise API clients ----
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    s2_client = SemanticScholarAPI(api_key if api_key else None)
    arxiv_client = ArxivAPI()

    # ---- 5. Schedule periodic tasks ----
    update_interval_days = cfg.get_int(
        "semanticpaper", "incremental_update_interval_days",
        int(os.getenv("INCREMENTAL_UPDATE_INTERVAL_DAYS", "30"))
    )
    uncaught_interval_days = cfg.get_int(
        "semanticpaper", "uncaught_retry_interval_days",
        int(os.getenv("UNCAUGHT_RETRY_INTERVAL_DAYS", "14"))
    )

    scheduler = BackgroundScheduler()

    # Run incremental update immediately, then on schedule
    scheduler.add_job(
        run_incremental_update,
        "interval",
        days=update_interval_days,
        next_run_time=datetime.now(),
        args=[arxiv_client, s2_client, pipeline],
        id="incremental_update",
        max_instances=1,
    )
    logger.info(f"Scheduled incremental update: every {update_interval_days} days")

    # Uncaught paper retry
    scheduler.add_job(
        retry_uncaught_papers,
        "interval",
        days=uncaught_interval_days,
        args=[s2_client, pipeline],
        id="uncaught_retry",
        max_instances=1,
    )
    logger.info(f"Scheduled uncaught paper retry: every {uncaught_interval_days} days")

    scheduler.start()
    logger.info("Scheduler started. System is running.")

    # ---- 6. Wait for shutdown ----
    def shutdown(signum, frame):
        logger.info("Shutdown signal received...")
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped. Exiting.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Press Ctrl+C to stop.")
    try:
        signal.pause()
    except AttributeError:
        # signal.pause() not available on Windows
        import time
        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()