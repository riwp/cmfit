"""Shared persistent logging for CMFit service modules."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        return logger

    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    log_dir = os.path.join(project_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(log_dir, 'cmfit.log'),
        maxBytes=2_000_000,
        backupCount=5,
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    ))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
