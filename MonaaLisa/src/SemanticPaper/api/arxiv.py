import os

import arxiv as arx

from config import cfg
from util.logger import Logger


class ArxivAPI:
    """
    Original File by Basti - 04-May-2025, refactored into a class by Lenio - 20-September-2025

    Holds the arxiv library client used by the incremental pipeline. The client
    takes care of waiting between page requests and retrying failed pages.
    """

    def __init__(self):
        self.logger = Logger("ArxivAPI")
        interval = cfg.get_float("semanticpaper", "arxiv_min_interval", float(os.getenv("ARXIV_MIN_INTERVAL", "3.0")))
        # arXiv asks clients to wait at least 3 seconds between requests
        self.client = arx.Client(delay_seconds=max(interval, 3.0), num_retries=5)
