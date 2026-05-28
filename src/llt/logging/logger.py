"""Structured event logging for LLT."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


class LLTLogger:
    """Small file-backed logger used by the runtime."""

    def __init__(self, log_dir: Optional[str] = None) -> None:
        base_dir = os.getenv("LLT_PATH", os.path.join(os.path.expanduser("~"), ".llt"))
        self.log_dir = os.path.abspath(os.path.expanduser(log_dir or os.path.join(base_dir, "logs")))
        os.makedirs(self.log_dir, exist_ok=True)

        self.sys_logger = logging.getLogger("llt")
        self.sys_logger.setLevel(logging.INFO)
        if not self.sys_logger.handlers:
            handler = logging.FileHandler(os.path.join(self.log_dir, "llt.log"))
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )
            self.sys_logger.addHandler(handler)

    def _log(self, level: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4()),
            "level": level,
            "message": message,
        }
        if metadata:
            entry["metadata"] = metadata

        if level == "ERROR":
            self.sys_logger.error(message)
        elif level == "WARNING":
            self.sys_logger.warning(message)
        else:
            self.sys_logger.info(message)

        try:
            with open(os.path.join(self.log_dir, "llt_event.jsonl"), "a", encoding="utf-8") as handle:
                json.dump(entry, handle)
                handle.write("\n")
        except OSError as exc:
            self.sys_logger.error("Failed to write event log: %s", exc)

    def log_info(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._log("INFO", message, metadata)

    def log_warning(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._log("WARNING", message, metadata)

    def log_error(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._log("ERROR", message, metadata)


llt_logger = LLTLogger()
