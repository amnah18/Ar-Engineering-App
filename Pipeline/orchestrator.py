"""
orchestrator.py — single entry point for the AR Engineering pipeline

Pipeline steps:
  1. Agent 1  — scan input folder (.mp4/.mov → frames, .jpg/.jpeg → copy)
  2. Agent 2  — analyse each frame with Claude → one JSON per frame
  3. Agent 3  — aggregate all JSONs → aggregated_report.json
  4. Cost engine (Python) → cost_table.json
  5. Agent 4  — generate 5 .docx documents
  6. Validation — verify all outputs exist and are non-empty

Usage:
  python orchestrator.py <input_folder>

Example:
  python orchestrator.py input
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.agent1_frame_extraction import process_input_folder
from agents.agent2_vision_analysis import run_agent2
from agents.agent3_aggregation import aggregate_findings
from agents.agent4_report_generation import build_cost_table
from agents.agent4_part2_claude_code import run_agent4_documents
from config import OUTPUT_FOLDER

EXPECTED_DOCS = [
    "01_Scope_of_Works.docx",
    "02_Cost_Estimate.docx",
    "03_Material_List.docx",
    "04_Trade_Schedule.docx",
    "05_Defect_Log.docx",
]


# ── Logging ────────────────────────────────────────────────────────────────

def _setup_logger(property_id: str) -> logging.Logger:
    log_dir = Path(OUTPUT_FOLDER) / property_id
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(property_id)
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%d/%m/%Y %H:%M:%S"
    ))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s]  %(message)s", datefmt="%H:%M:%S"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ── Validation ─────────────────────────────────────────────────────────────

def _validate(property_id: str, report: dict, docs_dir: Path) -> tuple[bool, list[str]]:
    failures = []

    for doc in EXPECTED_DOCS:
        p = docs_dir / doc
        if not p.exists():
            failures.append(f"Missing document: {doc}")
        elif p.stat().st_size < 500:
            failures.append(f"Document too small (likely empty): {doc}")

    if report.get("total_frames_analysed", 0) == 0:
        failures.append("No frames were analysed — check Agent 1 and Agent 2 output")

    if not report.get("all_defects"):
        failures.append("No defects in aggregated report — check frame quality or Agent 2 output")

    if failures:
        review_dir = Path(OUTPUT_FOLDER) / property_id / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        review_path = review_dir / f"validation_{ts}.txt"
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(f"VALIDATION REPORT — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("=" * 52 + "\n")
            for i, issue in enumerate(failures, 1):
                f.write(f"{i}. {issue}\n")

    return len(failures) == 0, failures


# ── Pipeline ───────────────────────────────────────────────────────────────

def run_pipeline(input_folder: str) -> None:
    property_id = Path(input_folder).name
    started_at  = datetime.now()
    logger      = _setup_logger(property_id)

    base = Path(OUTPUT_FOLDER) / property_id
    frames_dir   = base / "frames"
    reports_dir  = base / "frame_reports"
    cost_path    = base / "cost_table.json"
    agg_path     = base / "aggregated_report.json"
    docs_dir     = base / "docs"

    logger.info(f"Pipeline started — property: {property_id}")
    logger.info(f"Input: {input_folder}")

    # ── Step 1: Agent 1 ───────────────────────────────────────────────────
    logger.info("Step 1/5 — Agent 1: extracting / collecting frames")
    try:
        frame_paths = process_input_folder(input_folder, str(frames_dir))
        logger.info(f"Agent 1 complete — {len(frame_paths)} frames")
    except Exception as exc:
        logger.error(f"Agent 1 FAILED: {exc}")
        _finish(logger, started_at, failed=True)
        return

    # ── Step 2: Agent 2 ───────────────────────────────────────────────────
    logger.info("Step 2/5 — Agent 2: analysing frames")
    try:
        json_paths = run_agent2(str(frames_dir), str(reports_dir))
        logger.info(f"Agent 2 complete — {len(json_paths)} frame reports")
    except Exception as exc:
        logger.error(f"Agent 2 FAILED: {exc}")
        _finish(logger, started_at, failed=True)
        return

    # ── Step 3: Agent 3 ───────────────────────────────────────────────────
    logger.info("Step 3/5 — Agent 3: aggregating findings")
    try:
        report  = aggregate_findings(property_id)
        summary = report["defect_summary"]
        logger.info(
            f"Agent 3 complete — {summary['total']} defects "
            f"(Critical={summary['critical']}, Moderate={summary['moderate']}, Minor={summary['minor']}) "
            f"across {len(report['rooms'])} room(s)"
        )
    except Exception as exc:
        logger.error(f"Agent 3 FAILED: {exc}")
        _finish(logger, started_at, failed=True)
        return

    # ── Step 4: Cost engine ───────────────────────────────────────────────
    logger.info("Step 4/5 — Cost engine: building cost table")
    try:
        cost_table = build_cost_table(report)
        with open(cost_path, "w", encoding="utf-8") as f:
            json.dump(cost_table, f, indent=2, ensure_ascii=False)
        totals = cost_table["total_inc_gst"]
        logger.info(
            f"Cost engine complete — "
            f"AUD ${totals['min']:,.2f} – ${totals['max']:,.2f} inc. GST"
        )
    except Exception as exc:
        logger.error(f"Cost engine FAILED: {exc}")
        _finish(logger, started_at, failed=True)
        return

    # ── Step 5: Agent 4 ───────────────────────────────────────────────────
    logger.info("Step 5/5 — Agent 4: generating documents")
    try:
        run_agent4_documents(str(agg_path), str(cost_path), str(docs_dir))
        logger.info("Agent 4 complete — 5 documents generated")
    except Exception as exc:
        logger.error(f"Agent 4 FAILED: {exc}")
        _finish(logger, started_at, failed=True)
        return

    # ── Validation ────────────────────────────────────────────────────────
    passed, failures = _validate(property_id, report, docs_dir)
    if passed:
        logger.info("Validation PASSED — all outputs verified")
    else:
        logger.warning(f"Validation FAILED — {len(failures)} issue(s):")
        for issue in failures:
            logger.warning(f"  • {issue}")
        logger.info(f"Review saved → outputs/{property_id}/review/")

    _finish(logger, started_at, failed=not passed)


def _finish(logger: logging.Logger, started_at: datetime, failed: bool = False) -> None:
    elapsed = datetime.now() - started_at
    status  = "FAILED" if failed else "SUCCESS"
    logger.info(f"Pipeline {status} — elapsed: {elapsed}")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python orchestrator.py <input_folder>")
        print("Example: python orchestrator.py input")
        sys.exit(1)
    run_pipeline(sys.argv[1])
