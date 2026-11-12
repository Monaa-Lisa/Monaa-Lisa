import os
import json
import time
from pathlib import Path
from typing import Optional

import requests
import gdown
import joblib

from util.logger import Logger
from config import cfg


logger = Logger("Downloader")

# Laedt die Mirror Config aus dem Root des Projekts
def _load_mirrors_config() -> dict:
    possible_paths = [
        Path("/app/mirrors.json"),  
        # wenn nicht docker dann hier hardcoded
        Path(__file__).parent.parent.parent.parent.parent.parent / "mirrors.json",  
    ]
    # FallBack-Mechanismus: Versuche verschiedene Pfade, um die Konfigurationsdatei zu finden
    for config_path in possible_paths:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                logger.info(f"Loaded mirrors config from {config_path}")
                return json.load(f)
    logger.warning("mirrors.json not found, using defaults")
    return {"files": {}, "download_settings": {}}


MIRRORS_CONFIG = _load_mirrors_config()
DOWNLOAD_SETTINGS = MIRRORS_CONFIG.get("download_settings", {})
FILES_CONFIG = MIRRORS_CONFIG.get("files", {})


def _data_dir() -> Path:
    """Resolve the main data directory, ensuring it exists."""
    d = Path(cfg.get("semanticpaper", "data_dir", os.getenv("DATA_DIR", "/app/data")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _models_dir() -> Path:
    """Resolve the models sub-directory, ensuring it exists."""
    d = _data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_file_config(file_key: str) -> dict:
    """Get configuration for a specific file from mirrors.json."""
    return FILES_CONFIG.get(file_key, {})

"""
Abstract: Downloads a file from an HTTP mirror using streaming.
        Args:
        - url: Direct HTTP URL
        - dest: Local destination path
        - description: Human-readable label for log messages
        Returns: bool -> True if download succeeded
"""
def _download_http(url: str, dest: Path, description: str) -> bool:

    timeout = DOWNLOAD_SETTINGS.get("timeout_seconds", 300)
    chunk_size = DOWNLOAD_SETTINGS.get("chunk_size_bytes", 8 * 1024 * 1024)
    
    try:
        logger.info(f"Downloading {description} from {url}...")
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        last_log_percent = -10
        # streamed den Download in Chunks, damit wir große Dateien herunterladen können ohne zu viel RAM zu verbrauchen
        with open(dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int(downloaded * 100 / total_size)
                        if percent >= last_log_percent + 10:
                            logger.info(f"  {description}: {percent}% ({downloaded / (1024**2):.1f} MB / {total_size / (1024**2):.1f} MB)")
                            last_log_percent = percent
        # Nach dem Download prüfen wir, ob die Datei existiert und nicht leer ist, um sicherzustellen, dass der Download erfolgreich war
        if dest.exists() and dest.stat().st_size > 0:
            logger.info(f"Downloaded {description}: {dest.stat().st_size:,} bytes  {dest}")
            return True
        else:
            # Wenn die Datei nicht existiert oder leer ist, behandeln wir das als Fehler, löschen die Datei (falls sie existiert) und loggen eine Fehlermeldung
            logger.error(f"Download resulted in empty file: {dest}")
            dest.unlink(missing_ok=True)
            return False
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"HTTP download failed for {description} from {url}: {e}")
        dest.unlink(missing_ok=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error downloading {description}: {e}")
        dest.unlink(missing_ok=True)
        return False

"""
    Abstract: Downloads a single file from Google Drive (fallback method).
              Retries on transient failures (e.g. Google Drive rate limits).
    Args:
    - file_id: Google Drive file ID
    - dest: Local destination path
    - description: Human-readable label for log messages
    - max_retries: Maximum number of retry attempts
    - retry_delay: Seconds to wait between retries (doubles each attempt)
    Returns: bool -> True if download succeeded and file is non-empty
"""
def _download_gdrive(file_id: str, dest: Path, description: str, max_retries: int = 3, retry_delay: int = 60) -> bool:
    # Fallback falls kein HTTP Mirror gegeben wird - dann ists noch auf meiner Google Drive 
    url = f"https://drive.google.com/uc?id={file_id}"
    delay = retry_delay

    for attempt in range(1, max_retries + 1):
        logger.info(f"Downloading {description} from Google Drive (attempt {attempt}/{max_retries})...")
        try:
            output = gdown.download(url, str(dest), quiet=False, fuzzy=True)
            if output is None or not dest.exists():
                logger.error(f"GDrive download failed for {description}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                    continue
                return False
            size = dest.stat().st_size
            if size == 0:
                logger.error(f"Downloaded file {dest} is empty!")
                dest.unlink(missing_ok=True)
                if attempt < max_retries:
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                    continue
                return False
            logger.info(f"Downloaded {description} from GDrive: {size:,} bytes  {dest}")
            return True
        except Exception as e:
            logger.error(f"Error downloading {description} from GDrive: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2
            else:
                return False
    return False

"""
    Abstract: Downloads a file using the mirror-first strategy.
              1. Try each HTTP mirror in order
              2. Fall back to Google Drive if all mirrors fail
    Args:
    - file_key: Key in mirrors.json (e.g., "dataset", "pca_model", "umap_model")
    - dest: Local destination path
    Returns: bool -> True if download succeeded
"""
def _download_file(file_key: str, dest: Path) -> bool:
    # Liest die Konfiguration für die angegebene Datei aus mirrors.json, einschließlich Beschreibung, HTTP-Mirrors und optionaler Google Drive Fallback-Informationen. Überprüft zuerst, ob die Datei bereits existiert und nicht leer ist, um unnötige Downloads zu vermeiden. Versucht dann, die Datei von jedem HTTP-Mirror herunterzuladen, mit konfigurierbaren Wiederholungsversuchen und Verzögerungen. Wenn alle HTTP-Mirrors fehlschlagen, versucht es den Download von Google Drive mit ähnlichen Wiederholungsmechanismen. Gibt True zurück, wenn der Download erfolgreich war und die Datei existiert, andernfalls False.
    config = _get_file_config(file_key)
    if not config:
        logger.error(f"No configuration found for file: {file_key}")
        return False
    # Beschreibung, die in Log-Nachrichten verwendet wird, z.B. "Dataset", "PCA model", "UMAP model"
    description = config.get("description", file_key)
    mirrors = config.get("mirrors", [])
    gdrive_fallback = config.get("gdrive_fallback", {})
    
    # Vor dem Download prüfen wir, ob die Datei bereits existiert und eine vernünftige Größe hat, um unnötige Downloads zu vermeiden (z.B. wenn
    if dest.exists() and dest.stat().st_size > 0:
        logger.info(f"{description} already exists at {dest} ({dest.stat().st_size:,} bytes), skipping download.")
        return True
    
    max_retries = DOWNLOAD_SETTINGS.get("max_retries", 3)
    retry_delay = DOWNLOAD_SETTINGS.get("retry_delay_seconds", 10)
    
    # versucht zuerst die HTTP-Mirrors in der angegebenen Reihenfolge, mit Wiederholungsversuchen bei Fehlern (z.B. Netzwerkprobleme, Mirror-Ausfälle)
    for mirror_url in mirrors:
        for attempt in range(1, max_retries + 1):
            if _download_http(mirror_url, dest, description):
                return True
            if attempt < max_retries:
                logger.info(f"Mirror attempt {attempt}/{max_retries} failed, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
        logger.warning(f"Mirror {mirror_url} exhausted, trying next...")
    
    # dann fallback auf Google Drive, wenn alle HTTP-Mirrors fehlschlagen. Auch hier mit Wiederholungsversuchen, da Google Drive manchmal unzuverlässig sein kann (z.B. bei großen Dateien oder wenn sie kürzlich aktualisiert wurden)
    gdrive_id = gdrive_fallback.get("file_id")
    if gdrive_id:
        logger.info(f"All mirrors failed for {description}, falling back to Google Drive...")
        return _download_gdrive(gdrive_id, dest, description, max_retries=5, retry_delay=60)
    
    logger.error(f"No mirrors or GDrive fallback available for {description}")
    return False

"""
    Abstract: Verifies that a .pkl file is valid.
              When full_load=True, loads the entire object with joblib (suitable for small models).
              When full_load=False, does a lightweight check (file size + pickle header)
              to avoid OOM on very large models like UMAP (6+ GB).
    Args:
    - path: File path
    - label: Human-readable label for log messages
    - full_load: Whether to fully load the model into memory for verification
    Returns: bool
"""
def _verify_pkl(path: Path, label: str, full_load: bool = True) -> bool:

    if not path.exists():
        logger.error(f"{label} file does not exist: {path}")
        return False

    file_size = path.stat().st_size
    if file_size < 1024:
        logger.error(f"{label} file is suspiciously small ({file_size} bytes): {path}")
        return False

    if not full_load:
        # Für sehr große Modelle wie UMAP wollen wir nicht das gesamte Objekt laden, da das zu OOM führen könnte. Stattdessen prüfen wir nur die Dateigröße und den Pickle-Header, um eine grundlegende Validierung durchzuführen.
        try:
            with open(path, "rb") as f:
                header = f.read(2)
                if header[0:1] != b'\x80':
                    logger.error(f"{label} does not have a valid pickle header.")
                    return False
            logger.info(f"{label} header verified ({file_size / (1024**3):.2f} GB). Full load deferred to pipeline.")
            return True
        except Exception as e:
            logger.error(f"Failed lightweight verification of {label}: {e}")
            return False

    try:
        obj = joblib.load(path)
        if obj is None:
            logger.error(f"{label} loaded as None – file may be corrupt.")
            return False
        logger.info(f"{label} loaded and verified successfully (type: {type(obj).__name__}).")
        return True
    except Exception as e:
        logger.error(f"Failed to verify {label}: {e}")
        return False




def _get_filename(file_key: str) -> str:
    """Get the filename for a file from mirrors.json config."""
    config = _get_file_config(file_key)
    return config.get("filename", f"{file_key}.bin")


def download_dataset() -> Path | None:
    """
    Abstract: Downloads the full dataset JSONL.
              Tries HTTP mirrors first, then falls back to Google Drive.
    Returns: Path to the downloaded file, or None on failure.
    """
    filename = _get_filename("dataset")
    dest = _data_dir() / filename
    if _download_file("dataset", dest):
        return dest
    return None


def download_models() -> bool:
    """
    Abstract: Downloads PCA and UMAP pre-trained models and verifies they can be loaded.
              Tries HTTP mirrors first, then falls back to Google Drive.
    Returns: bool -> True if both models were downloaded and verified.
    """
    models_dir = _models_dir()
    
    pca_filename = _get_filename("pca_model")
    umap_filename = _get_filename("umap_model")
    
    pca_path = models_dir / pca_filename
    umap_path = models_dir / umap_filename

    pca_ok = _download_file("pca_model", pca_path)
    umap_ok = _download_file("umap_model", umap_path)

    if not pca_ok or not umap_ok:
        return False

    if not _verify_pkl(pca_path, "PCA model"):
        return False
    if not _verify_pkl(umap_path, "UMAP model", full_load=False):
        return False

    return True


def ensure_all_downloaded() -> bool:
    """
    Abstract: Ensures dataset + models are downloaded. Returns False if anything fails.
    """
    dataset_path = download_dataset()
    if dataset_path is None:
        return False
    if not download_models():
        return False
    return True


def ensure_models_exist() -> bool:
    """
    Abstract: Ensures only the ML models (PCA + UMAP) are present (no dataset needed).
              Called on non-first runs where the dataset has already been imported.
    Returns: bool
    """
    return download_models()


def get_dataset_path() -> Path:
    return _data_dir() / _get_filename("dataset")


def get_pca_model_path() -> Path:
    return _models_dir() / _get_filename("pca_model")


def get_umap_model_path() -> Path:
    return _models_dir() / _get_filename("umap_model")


def cleanup_dataset():
    """
    Abstract: Removes the dataset JSONL after successful import to reclaim disk space.
    """
    path = get_dataset_path()
    if path.exists():
        size = path.stat().st_size
        path.unlink()
        logger.info(f"Cleaned up dataset file ({size / (1024**3):.2f} GB freed)")
