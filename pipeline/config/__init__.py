"""
config.py — Central configuration for AR Engineering CV Pipeline
All Australian labour rates, trade sequences, and paths live here.
Never hardcode values in agents — always import from this file.
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_pipeline_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FOLDER = os.environ.get("INPUT_FOLDER", os.path.join(_pipeline_root, "tests", "sample_input"))
OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", os.path.join(_pipeline_root, "outputs"))

FRAME_INTERVAL_SEC = 5