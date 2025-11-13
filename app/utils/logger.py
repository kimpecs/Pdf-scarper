# app/utils/logger.py
import logging
import sys
from pathlib import Path

try:
    from .config import settings
except ImportError:
    # Fallback for when running scripts directly
    class DefaultSettings:
        LOG_LEVEL = "INFO"
        BASE_DIR = Path(__file__).parent.parent.parent
    
    settings = DefaultSettings()

class UnicodeStreamHandler(logging.StreamHandler):
    """Custom stream handler that handles Unicode characters"""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Write the message with proper encoding
            stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            # If Unicode fails, remove non-ASCII characters
            try:
                msg = msg.encode('ascii', 'ignore').decode('ascii')
                stream.write(msg + self.terminator)
                self.flush()
            except Exception:
                pass
        except Exception:
            self.handleError(record)

def setup_logging(name=__name__):
    """Setup logging with proper path handling"""
    logger = logging.getLogger(name)
    
    # Only setup if not already configured
    if not logger.handlers:
        # Set log level
        try:
            log_level = getattr(logging, settings.LOG_LEVEL)
        except (AttributeError, ValueError):
            log_level = logging.INFO
            
        logger.setLevel(log_level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler with Unicode support
        console_handler = UnicodeStreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler with error handling
        try:
            log_file = settings.BASE_DIR / 'app.log'
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (AttributeError, PermissionError) as e:
            print(f"⚠️ Could not setup file logging: {e}")
    
    return logger

# Create a default logger instance
logger = setup_logging('app')