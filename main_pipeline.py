"""
main_pipeline.py — Enterprise Detection Pipeline Daemon Entry Point
====================================================================
Usage:
    python main_pipeline.py
"""
import logging
from app.core.config import get_config
from app.core.logging import setup_logging
from app.db.schema import init_db
from app.pipeline.runner import PipelineRunner

if __name__ == "__main__":
    cfg = get_config()
    setup_logging(level=cfg.log_level, log_file=cfg.log_file)
    init_db(cfg.db_path)
    runner = PipelineRunner()
    runner.run()