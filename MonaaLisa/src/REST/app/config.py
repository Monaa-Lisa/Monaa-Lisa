import os

class Config:
    DEBUG = os.getenv('DEBUG', False)
    TESTING = os.getenv('TESTING', False)
