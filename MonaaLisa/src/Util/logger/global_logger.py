import logging

# Global logger, for general use in the project
def setup_logger(purpose:str ="GENERAL", logfile:str ='general'):
    logger = logging.getLogger(purpose)
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    # Copy pasted from the semantic paper logger, twaeked
    file_handler = logging.FileHandler(f"{logfile}-latest.log", mode='w', encoding='utf-8')
    file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)

    return logger