"""
agent4_report_generation.py
Input:  aggregated_report dict from Agent 3
Output: 5 document files in outputs/{property_id}/docs/
          scope_of_work.txt
          cost_estimate.txt
          material_list.txt
          trade_schedule.txt
          defect_log.txt
        + cost_table.json at outputs/{property_id}/cost_table.json (Python-calculated)

Hybrid approach:
  Step 1 — Python cost engine builds an exact cost table from AU_LABOUR_RATES.
            The AI model never sees raw rates or calculates anything.
  Step 2 — Claude Cowork reads the saved context file and writes all 5 documents.
            Pipeline pauses until user presses ENTER after Cowork finishes.
"""

import json
import os
from datetime import date
from pathlib import Path

from config import OUTPUT_FOLDER
from config.rates import AU_LABOUR_RATES, GST_RATE, TRADE_SEQUENCE
from groq import Groq
import os
import json
from pathlib import Path
from datetime import date

GROQ_MODEL_TEXT = "llama-3.3-70b-versatile"



# ---------------------------
# SYSTEM PROMPT
# ---------------------------
SYSTEM_PROMPT = """You are an Australian renovation document writer.

You will receive:
1. A structured property inspection report
2. A pre-calculated cost table — all figures are exact, do not modify them

Your job is to format these into professional documents using Australian building terminology throughout.

RULES:
- Never modify any number from the cost table
- Use Australian terminology only: Gyprock not drywall, cornices not crown molding, eaves not soffits, plasterboard not sheetrock
- For any item marked REQUIRES_TRADE_QUOTE write exactly: "Requires licensed trade inspection and quote — not included in estimate"
- For any item marked CLIENT_DECISION write exactly: "Pending client decision — cost range provided for planning purposes only"
- For any item marked REQUIRES_SITE_MEASURE write: "Quantity TBC — requires physical site measurement"
- Trade sequence must follow Australian standard: Demo -> Pest -> Structural -> Roof -> Rough-in electrical -> Rough-in plumbing -> Frame -> Insulation -> Plasterboard -> Cornice -> Fit-off -> Paint -> Floor -> Fix
- All dates in DD/MM/YYYY format
- All measurements in metric
- All figures in AUD"""


# ---------------------------
# DOCUMENT INSTRUCTIONS
# One AI call per document — keeps focus tight on each output
# ---------------------------
# Maps each document to its output format.
# docx = narrative Word document   xlsx = structured Excel spreadsheet
_DOC_FORMATS = {
    "scope_of_work":  "docx",   # prose narrative — Word suits it best
    "cost_estimate":  "xlsx",   # financial table with formulas/subtotals
    "material_list":  "xlsx",   # row-per-material tabular list
    "trade_schedule": "xlsx",   # schedule grid with date columns
    "defect_log":     "xlsx",   # sortable defect register
}

_DOCUMENTS = {
    "scope_of_work": (
        "File format: scope_of_work.docx (Word document).\n"
        "Use python-docx to create it. Structure:\n"
        "  - Title: 'Scope of Work' + property ID + date\n"
        "  - One Heading 1 section per trade, in Australian trade sequence order\n"
        "  - Under each trade: bullet list of work items from the report\n"
        "  - No cost figures — scope only\n"
        "  - Footer: 'Prepared by AR Engineering'"
    ),
    "cost_estimate": (
        "File format: cost_estimate.xlsx (Excel spreadsheet).\n"
        "Use openpyxl to create it. Structure:\n"
        "  - Sheet name: 'Cost Estimate'\n"
        "  - Header row (bold): Trade | Description | Hrs Min | Hrs Max | Rate Min (AUD/hr) | Rate Max (AUD/hr) | Cost ex-GST Min | Cost ex-GST Max | GST Min | GST Max | Total inc-GST Min | Total inc-GST Max | Flag\n"
        "  - One row per line item from cost_table['line_items'] — copy figures exactly\n"
        "  - Subtotal rows per trade (bold, shaded)\n"
        "  - Final rows: Total ex-GST | GST Amount | Grand Total inc-GST (from cost_table totals)\n"
        "  - Currency columns formatted as AUD accounting format\n"
        "  - Flag column: show REQUIRES_TRADE_QUOTE or REQUIRES_SITE_MEASURE where present"
    ),
    "material_list": (
        "File format: material_list.xlsx (Excel spreadsheet).\n"
        "Use openpyxl to create it. Structure:\n"
        "  - Sheet name: 'Material List'\n"
        "  - Header row (bold): Room | Trade | Material | Quantity | Notes\n"
        "  - One row per material from report['rooms'][room]['materials_identified']\n"
        "  - Quantity: write 'TBC — site measure required' where trade is painter or tiler\n"
        "  - Group rows by room with merged room cells and light fill colour per room\n"
        "  - Use Australian supplier names where relevant (Dulux, Beaumont, Reece, Gyprock)"
    ),
    "trade_schedule": (
        "File format: trade_schedule.xlsx (Excel spreadsheet).\n"
        "Use openpyxl to create it. Structure:\n"
        "  - Sheet name: 'Trade Schedule'\n"
        "  - Header row (bold): Trade | Scope Summary | Est. Duration (days) | Start Date | Completion Date | Dependencies\n"
        "  - One row per trade, ordered by Australian trade sequence\n"
        "  - Scope Summary: 1-2 sentence description of work for that trade\n"
        "  - Est. Duration: derive from total hours in cost_table for that trade (assume 8hr day)\n"
        "  - Start Date / Completion Date: leave blank (DD/MM/YYYY format label only)\n"
        "  - Dependencies: name the preceding trade from the sequence"
    ),
    "defect_log": (
        "File format: defect_log.xlsx (Excel spreadsheet).\n"
        "Use openpyxl to create it. Structure:\n"
        "  - Sheet name: 'Defect Log'\n"
        "  - Header row (bold): Defect ID | Room | Defect Name | Severity | Location | Recommended Action | Trade | Est. Cost Min (AUD) | Est. Cost Max (AUD)\n"
        "  - One row per defect from cost_table['line_items']\n"
        "  - Sort: Critical first (red fill), then Moderate (orange fill), then Minor (yellow fill)\n"
        "  - Est. Cost: use total_min / total_max from the line item; write 'Trade quote required' if REQUIRES_TRADE_QUOTE\n"
        "  - Auto-filter on header row"
    ),
}


# ---------------------------
# COWORK PROMPT
# ---------------------------
_COWORK_PROMPT = """TASK FOR CLAUDE COWORK — PROPERTY REPORT DOCUMENT GENERATION

Step 1 — Read this JSON context file:
{context_file}

It contains two keys:
  "report"     — the aggregated inspection findings
  "cost_table" — pre-calculated costs in AUD (NEVER modify any figure)

Step 2 — Install required Python libraries if not already installed:
  pip install python-docx openpyxl

Step 3 — Write a Python script and run it to generate all five documents in:
{out_dir}

--- RULES ---
{system_prompt}

--- DOCUMENTS TO GENERATE ---

1. scope_of_work.docx
{scope_of_work}

2. cost_estimate.xlsx
{cost_estimate}

3. material_list.xlsx
{material_list}

4. trade_schedule.xlsx
{trade_schedule}

5. defect_log.xlsx
{defect_log}

--- IMPORTANT ---
- Write and execute a Python script to produce all five files.
- Do NOT produce placeholder or stub content — each file must contain real data from the context JSON.
- Verify each file exists on disk after running the script before reporting completion."""


# ---------------------------
# PYTHON COST ENGINE
# All figures produced here — AI model only formats, never calculates
# ---------------------------
_TRADE_KEYWORDS = [
    (["wiring", "electrical", "outlet", "circuit", "switch", "powerpoint", "junction"], "electrician"),
    (["pipe", "plumbing", "leak", "tap", "drain", "toilet", "basin", "waterproof"],    "plumber"),
    (["plasterboard", "gyprock", "plaster", "cornice", "join", "set"],                 "plasterer"),
    (["paint", "coat", "primer", "repaint", "surface prep"],                            "painter"),
    (["tile", "tiling", "grout", "floor tile", "wall tile"],                           "tiler"),
    (["timber", "frame", "joist", "stud", "door frame", "window frame", "skirting"],  "carpenter"),
    (["crack", "structural", "concrete", "brick", "render", "footing", "slab"],        "builder"),
]

_BASE_HOURS = {
    "Critical": (8, 16),
    "Moderate": (3, 8),
    "Minor":    (1, 3),
}

_ALWAYS_QUOTE   = {"electrician"}
_MEASURE_NEEDED = {"painter", "tiler"}


def _infer_trade(defect: dict) -> str:
    text = f"{defect.get('name', '')} {defect.get('action', '')}".lower()
    for keywords, trade in _TRADE_KEYWORDS:
        if any(kw in text for kw in keywords):
            return trade
    return "builder"


def build_cost_table(report: dict) -> dict:
    """
    Pure Python. Reads defects from aggregated report, infers trade, looks up
    AU_LABOUR_RATES, applies GST. Returns a fully calculated cost_table dict.
    The AI model receives this and must not alter any figure.
    """
    line_items = []
    subtotals: dict[str, dict] = {}
    running_min = 0.0
    running_max = 0.0

    for i, defect in enumerate(report.get("all_defects", []), 1):
        severity = defect.get("severity", "Minor")
        trade    = _infer_trade(defect)
        rates    = AU_LABOUR_RATES.get(trade, AU_LABOUR_RATES["builder"])
        h_min, h_max = _BASE_HOURS.get(severity, (1, 3))

        base = {
            "defect_id": f"D{i:03d}",
            "defect":    defect.get("name", ""),
            "room":      defect.get("location", ""),
            "action":    defect.get("action", ""),
            "severity":  severity,
            "trade":     trade,
        }

        if trade in _ALWAYS_QUOTE:
            item = {**base, "flag": "REQUIRES_TRADE_QUOTE",
                    "cost_min": None, "cost_max": None,
                    "gst_min":  None, "gst_max":  None,
                    "total_min": None, "total_max": None}
        else:
            cost_min = round(rates["min"] * h_min, 2)
            cost_max = round(rates["max"] * h_max, 2)
            gst_min  = round(cost_min * GST_RATE, 2)
            gst_max  = round(cost_max * GST_RATE, 2)
            flag     = "REQUIRES_SITE_MEASURE" if trade in _MEASURE_NEEDED else None

            item = {
                **base,
                "flag":      flag,
                "hours_min": h_min,
                "hours_max": h_max,
                "rate_min":  rates["min"],
                "rate_max":  rates["max"],
                "cost_min":  cost_min,
                "cost_max":  cost_max,
                "gst_min":   gst_min,
                "gst_max":   gst_max,
                "total_min": round(cost_min + gst_min, 2),
                "total_max": round(cost_max + gst_max, 2),
            }
            running_min += cost_min
            running_max += cost_max

            subtotals.setdefault(trade, {"min": 0.0, "max": 0.0})
            subtotals[trade]["min"] = round(subtotals[trade]["min"] + cost_min, 2)
            subtotals[trade]["max"] = round(subtotals[trade]["max"] + cost_max, 2)

        line_items.append(item)

    gst_min = round(running_min * GST_RATE, 2)
    gst_max = round(running_max * GST_RATE, 2)

    return {
        "generated_date":     date.today().strftime("%d/%m/%Y"),
        "currency":           "AUD",
        "gst_rate":           f"{int(GST_RATE * 100)}%",
        "trade_sequence":     TRADE_SEQUENCE,
        "line_items":         line_items,
        "subtotals_by_trade": subtotals,
        "total_ex_gst":       {"min": round(running_min, 2), "max": round(running_max, 2)},
        "gst_amount":         {"min": gst_min, "max": gst_max},
        "total_inc_gst":      {"min": round(running_min + gst_min, 2),
                               "max": round(running_max + gst_max, 2)},
    }


# ---------------------------
# DOCUMENT GENERATOR — CLAUDE COWORK
# ---------------------------

def _run_groq_documents(property_id: str, report: dict, cost_table: dict) -> dict:
    from config import OUTPUT_FOLDER
    from agents.agent4_part2_claude_code import run_agent4_documents

    out_dir = Path(OUTPUT_FOLDER) / property_id / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Agent 4 part 2 (python-docx) handles all document generation
    # No AI needed here — it reads directly from report and cost_table dicts
    # Save them as JSON so agent4_part2 can read them
    aggregated_path = out_dir / "_aggregated.json"
    cost_table_path = out_dir / "_cost_table.json"

    with open(aggregated_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    with open(cost_table_path, "w", encoding="utf-8") as f:
        json.dump(cost_table, f, indent=2, ensure_ascii=False)

    # Run the python-docx document generator directly
    success = run_agent4_documents(
        str(aggregated_path),
        str(cost_table_path),
        str(out_dir)
    )

    if not success:
        raise RuntimeError("Document generation failed")

    # Collect outputs
    outputs = {}
    for f in out_dir.iterdir():
        if f.suffix == ".docx" and not f.name.startswith("_"):
            outputs[f.stem] = str(f)

    if not outputs:
        raise RuntimeError(f"No documents found in {out_dir}")

    print(f"[Agent 4] Complete — {len(outputs)} documents generated")
    return outputs


def generate_reports(property_id: str, aggregated_report: dict, cost_table: dict = None) -> dict:
    if cost_table is None:
        print("\n[Agent 4] Building cost table (Python engine)...")
        cost_table = build_cost_table(aggregated_report)

    total_inc = cost_table["total_inc_gst"]
    print(f"[Agent 4] Cost engine complete — AUD ${total_inc['min']:,.2f} – ${total_inc['max']:,.2f} (inc. GST)")

    return _run_groq_documents(property_id, aggregated_report, cost_table)