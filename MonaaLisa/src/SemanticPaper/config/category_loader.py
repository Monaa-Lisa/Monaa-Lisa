import json
import threading
import time
import os
from pathlib import Path

from util.logger import Logger
from config import cfg


CONFIG_PATH = Path(
    cfg.get("semanticpaper", "category_config_path", os.getenv("CATEGORY_CONFIG_PATH", str(Path(__file__).resolve().parents[2] / "categories.json")))
)
RELOAD_INTERVAL = cfg.get_int("semanticpaper", "reload_interval", int(os.getenv("RELOAD_INTERVAL", "60")))

logger = Logger("CategoryLoader")


class CategoryLoader:
    """
    13-August-2025 - Basti
    Abstract: Initializes loader with config path and reload interval, loads initial config and starts watcher thread.
    Args:
    - config_path: path to JSON config file
    - reload_interval: Seconds between config reloads
    Returns: None
    """
    def __init__(self, config_path=CONFIG_PATH, reload_interval=RELOAD_INTERVAL):
        self.config_path = config_path
        self.reload_interval = reload_interval
        self.arxiv_categories = []
        self.semanticpaper_categories = []
        self._lock = threading.Lock()
        self.load_config()
        thread = threading.Thread(target=self._watch_config, daemon=True, name="CategoryWatcher")
        thread.start()

    """
    13-August-2025 - Basti
    Abstract: Reads JSON config and updates `arxiv_categories` and `semanticpaper_categories`, logging any new entries.
    Args:
    - None
    Returns: None
    """
    def load_config(self):

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            with self._lock:
                old_set = set(self.semanticpaper_categories)
                self.arxiv_categories = data.get("arxiv_categories", [])
                new_list = data.get("semanticpaper_categories", [])
                new_set = set(new_list)
                added = new_set - old_set
                removed = old_set - new_set
                self.semanticpaper_categories = new_list
            if added:
                logger.info(f"New SemanticPaper categories added: {sorted(added)}")
            if removed:
                logger.info(f"SemanticPaper categories removed: {sorted(removed)}")
        except Exception as e:
            logger.error(f"Failed to load categories config: {e}")

    """
    13-August-2025 - Basti
    Abstract: Background thread loop that reloads the categories JSON at fixed intervals.
    Args:
    - None
    Returns: None
    """
    def _watch_config(self):
        while True:
            time.sleep(self.reload_interval)
            self.load_config()

    """
    13-August-2025 - Basti
    Abstract: Returns a thread-safe copy of the current semanticpaper categories list.
    Args:
    - None
    Returns: List[str]
    """
    def get_semanticpaper_categories(self):
        with self._lock:
            return list(self.semanticpaper_categories)


# actual singleton instance - take that OOP classes
_loader = CategoryLoader()

"""
13-August-2025 - Basti
Abstract: Module-level helper returning semanticpaper categories from the singleton CategoryLoader.
Args:
- None
Returns: List[str]
"""
def get_semanticpaper_categories():
    return _loader.get_semanticpaper_categories()
