from SemanticPaper.api.arxiv import ArxivAPI
from SemanticPaper.machine_learning.mapper import Mapper
from SemanticPaper.machine_learning.processor import PaperProcessor
from SemanticPaper.scheduler import Scheduler
from util.logger import Logger
from Database.db import save_paper_to_db, save_paper_relation, get_all_embeddings, engine
from Database.db_models import db_base
from dotenv import load_dotenv
from config import cfg
from SemanticPaper.machine_learning.model import Model
from SemanticPaper.config.category_loader import get_semanticpaper_categories
import threading
import faulthandler
import os
import signal
import sys

logger = Logger("Main")

load_dotenv(".env_public")
HASH_FILE = 'parsed_hashes.txt'

arxiv_client = ArxivAPI()
model = Model(arxiv_client)
scheduler = Scheduler(arxiv_client)
# Initialize the embedding cache, which will store embeddings of papers to avoid fetching them from the db everytime
embedding_cache = {}
embedding_cache_lock = threading.Lock()
try:
    faulthandler.enable()
except Exception:
    pass
"""
25-May-2025 - Basti
Abstract: Loads the local parsed_hashes file
Args:
- None
Returns: Set filled with all parsed/known papers (hashed)
"""
def load_hashes():
    if not os.path.exists(HASH_FILE):
        return set()
    with open(HASH_FILE, "r") as f:
        return set(line.strip() for line in f)
"""
25-May-2025 - Basti
Abstract: Saves one hash string to the local parsed_hashes file
Args:
- hash_str: -> the hash of a peper
Returns: None
"""
def save_hash(hash_str):
    with open(HASH_FILE, "a") as f:
        f.write(hash_str + "\n")

"""
13-August-2025 - Basti
Abstract: Helper Function for the Entry() Method
Args:
- worker_id -> ID of one of x workers that have been assigned
Returns: None
"""
def paper_worker(worker_id, known_hashes):
    logger.info(f"Worker {worker_id} started")
    while True:
        paper =  scheduler.paper_queue.get()
        if paper is None:
            break
        active_categories = get_semanticpaper_categories()
        if getattr(paper, 'category', None) and paper.category not in active_categories:
            logger.warning(f"Worker {worker_id}: Category '{paper.category}' removed; skipping paper '{paper.title}'")
            continue
        processor = PaperProcessor(paper, model)
        if processor.prepare_paper(known_hashes):
            embedding = processor.create_structured_embedding()
            if embedding is not None:
                tsne = model.extract_tsne_coordinates(embedding)
                """
                21-August-2025 - Lenio
                Abstract: Save TSNE into the appropriate field of the paper object, compare the papers embedding to the existing embeddings
                """
                data = {"tsne1": tsne[0], "tsne2": tsne[1]}
                processor.paper.tsne = data
                processor.paper.embedding = embedding
                mapper = Mapper(processor.paper)
                # Get all embeddings from the cache
                with embedding_cache_lock:
                    current_embeddings = embedding_cache.copy()
                relations = mapper.map_paper(current_embeddings)
                logger.info(f"Found {len(relations)} relations for {paper.title}")
                if save_paper_to_db(processor.paper):
                    for relation in relations:
                        logger.info(f"Similar paper: {relation.source_id} with similarity score: {relation.confidence}")
                        save_paper_relation(relation)
                    # Save the embedding to the cache
                    with embedding_cache_lock:
                        embedding_cache[processor.paper.entry_id] = processor.paper.embedding
                    save_hash(processor.paper.hash)
                    known_hashes.add(processor.paper.hash)
    logger.info(f"Worker {worker_id} exiting")

"""
13-August-2025 - Basti
Abstract: Entry Point of SemanticPaper
Args:
- num_workers: Amount of workers to be used to fetch papers (they do not calculate their embeddings!)
Returns: None
"""
def main(num_workers: int = 5):
    log_level = cfg.get("semanticpaper", "log_level", os.getenv("LOG_LEVEL", "DEBUG"))
    logger.set_level(log_level)
    logger.info(f"Initializing scheduler system (log level={log_level})...")

    known_hashes = load_hashes()
    logger.info(f"Loaded {len(known_hashes)} known hashes")
    try:
        db_base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"Failed to pre-create tables: {e}")
    logger.info("Loading existing embeddings into cache...")
    with embedding_cache_lock:
        embedding_cache.update(get_all_embeddings())
    logger.info(f"Loaded {len(embedding_cache)} embeddings into cache.")
    logger.info("Starting scheduler...")
    scheduler.start_scheduler()
    if not scheduler.is_running():
        logger.error("Scheduler failed to start, exiting.")
        return

    logger.info(f"Starting {num_workers} worker threads...")
    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=paper_worker, args=(i+1, known_hashes), name=f"Worker-{i+1}")
        t.start()
        threads.append(t)



    """Graceful shutdown helper - Basti - 13. August 2025"""
    def shutdown(signum, frame):
        logger.info("Shutdown signal received, stopping workers...")
        for _ in threads:
            scheduler.paper_queue.put(None)
        for t in threads:
            t.join()
        logger.info("All workers stopped, exiting.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("System running. Press Ctrl+C to stop.")
    signal.pause()

if __name__ == "__main__":
    workers = cfg.get_int("semanticpaper", "num_workers", int(os.getenv("NUM_WORKERS", str(5))))
    main(workers)