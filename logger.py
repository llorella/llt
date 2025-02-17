# logger.py
import os
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Any

class LLTLog:
    def __init__(self, log_dir: str, max_bytes: int = 0, backup_count: int = 5):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.logger = logging.getLogger('llt')
        self.logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            os.path.join(self.log_dir, 'llt.log'),
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _format_message(self, message: Dict[str, Any]) -> str:
        return json.dumps(message, indent=2)

    def log_command(self, command: str, messages_before: Dict[str, Any], messages_after: Dict[str, Any], args: Dict[str, Any]) -> None:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'command': command,
            'messages_before': messages_before,
            'messages_after': messages_after,
            'args': vars(args),
            'tokens_before': self.count_tokens(messages_before),
            'tokens_after': self.count_tokens(messages_after)
        }
        self.logger.info(f"Command executed: {command}")
        self.logger.debug(self._format_message(log_entry))

    def log_error(self, error_message: str, context: Dict[str, Any] = None) -> None:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'error': error_message,
            'context': context
        }
        self.logger.error(self._format_message(log_entry))

    def log_info(self, message: str, context: Dict[str, Any] = None) -> None:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'context': context
        }
        self.logger.info(self._format_message(log_entry))

    def count_tokens(self, messages: Dict[str, Any]) -> int:
        # Implement token counting logic here
        # For now, we'll use a simple character count as a placeholder
        return sum(len(str(msg.get('content', ''))) for msg in messages) if messages else 0

llt_logger = LLTLog(os.path.join(os.getenv('LLT_PATH', ''), 'logs'))