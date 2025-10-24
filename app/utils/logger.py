import logging
import sys
from .config import settings

def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.BASE_DIR / 'app.log')
        ]
    )
    return logging.getLogger(__name__)