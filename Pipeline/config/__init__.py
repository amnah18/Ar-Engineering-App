"""
config.py — Central configuration for AR Engineering CV Pipeline
All Australian labour rates, trade sequences, and paths live here.
Never hardcode values in agents — always import from this file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

INPUT_FOLDER = os.environ.get("INPUT_FOLDER", "./tests/sample_input")
OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", "./outputs")

FRAME_INTERVAL_SEC = 5