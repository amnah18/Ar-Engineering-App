"""
agent3_aggregation.py
Input:  outputs/{property_id}/frame_reports/*.json  (one file per frame from Agent 2)
Output: outputs/{property_id}/aggregated_report.json (whole-video findings)

Pure Python — no LLM.
Steps:
  1. Load all frame JSONs
  2. Group frames by room type
  3. Deduplicate defects within each room (fuzzy name + location match)
  4. Merge severity upward — if same defect seen twice, keep the worst rating
  5. Union materials, actions, trades across all rooms
  6. Write aggregated_report.json
"""

import json
from difflib import SequenceMatcher
from pathlib import Path

from config import OUTPUT_FOLDER


# ---------------------------
# SEVERITY
# ---------------------------
_SEVERITY_RANK = {"Critical": 3, "Moderate": 2, "Minor": 1}

_DUPE_NAME_THRESHOLD = 0.70   # name similarity to count as same defect
_DUPE_LOC_THRESHOLD  = 0.50   # location similarity to count as same location


# ---------------------------
# DEDUPLICATION
# ---------------------------
def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _merge_or_add_defect(candidate: dict, defects: list) -> None:
    """
    Add candidate defect to the list.
    If a similar defect already exists (same name + location), upgrade its
    severity and action instead of adding a duplicate entry.
    """
    for existing in defects:
        name_sim = _similarity(candidate.get("name", ""), existing.get("name", ""))
        loc_sim  = _similarity(candidate.get("location", ""), existing.get("location", ""))

        if name_sim >= _DUPE_NAME_THRESHOLD and loc_sim >= _DUPE_LOC_THRESHOLD:
            # Same defect seen again — keep the worst severity
            if _SEVERITY_RANK.get(candidate.get("severity"), 0) > _SEVERITY_RANK.get(existing.get("severity"), 0):
                existing["severity"] = candidate["severity"]
                if candidate.get("action"):
                    existing["action"] = candidate["action"]
            return

    defects.append(dict(candidate))


# ---------------------------
# CORE FUNCTION
# ---------------------------
def aggregate_findings(property_id: str) -> dict:
    """
    Read all frame JSONs for property_id, deduplicate, and return the
    aggregated report dict (also saved to disk).
    """

    frame_dir = Path(OUTPUT_FOLDER) / property_id / "frame_reports"
    json_files = sorted(frame_dir.glob("*.json"))

    if not json_files:
        raise FileNotFoundError(f"No frame JSON files found in {frame_dir}")

    print(f"\n[Agent3] Loading {len(json_files)} frame reports...")

    frames = []
    for jf in json_files:
        with open(jf, encoding="utf-8") as f:
            frames.append(json.load(f))

    # ---------------------------
    # GROUP BY ROOM
    # ---------------------------
    room_data: dict[str, dict] = {}

    for frame in frames:
        room = (frame.get("room_type") or frame.get("room") or "unknown").lower().strip()

        if room not in room_data:
            room_data[room] = {
                "frame_ids":        [],
                "condition_ratings": [],
                "defects":          [],
                "materials":        set(),
                "actions":          set(),
                "trades":           set(),
            }

        r = room_data[room]
        r["frame_ids"].append(frame.get("frame_id", ""))
        r["condition_ratings"].append(frame.get("condition_rating", 3))

        for mat   in frame.get("materials_identified", []):
            r["materials"].add(mat.lower().strip())
        for act   in frame.get("recommended_actions", []):
            r["actions"].add(act.lower().strip())
        for trade in frame.get("trades_required", []):
            r["trades"].add(trade.lower().strip())

        for defect in frame.get("defects", []):
            _merge_or_add_defect(defect, r["defects"])

    # ---------------------------
    # BUILD OUTPUT
    # ---------------------------
    rooms_output = {}
    all_defects  = []
    all_trades:   set = set()
    all_actions:  set = set()
    overall_rating = 5

    for room, r in room_data.items():
        room_condition = min(r["condition_ratings"])
        overall_rating = min(overall_rating, room_condition)

        # Sort defects worst-first
        r["defects"].sort(key=lambda d: _SEVERITY_RANK.get(d.get("severity"), 0), reverse=True)

        rooms_output[room] = {
            "frame_count":        len(r["frame_ids"]),
            "frame_ids":          r["frame_ids"],
            "condition_rating":   room_condition,
            "defects":            r["defects"],
            "materials_identified": sorted(r["materials"]),
            "recommended_actions":  sorted(r["actions"]),
            "trades_required":      sorted(r["trades"]),
        }

        all_defects.extend(r["defects"])
        all_trades  |= r["trades"]
        all_actions |= r["actions"]

    # Deduplicate across rooms (same defect can appear in frames labelled differently)
    global_defects: list = []
    for d in all_defects:
        _merge_or_add_defect(d, global_defects)

    global_defects.sort(key=lambda d: _SEVERITY_RANK.get(d.get("severity"), 0), reverse=True)

    critical_count = sum(1 for d in global_defects if d.get("severity") == "Critical")
    moderate_count = sum(1 for d in global_defects if d.get("severity") == "Moderate")
    minor_count    = sum(1 for d in global_defects if d.get("severity") == "Minor")

    report = {
        "property_id":            property_id,
        "total_frames_analysed":  len(frames),
        "overall_condition_rating": overall_rating,
        "defect_summary": {
            "total":    len(global_defects),
            "critical": critical_count,
            "moderate": moderate_count,
            "minor":    minor_count,
        },
        "rooms":                  rooms_output,
        "all_defects":            global_defects,
        "all_trades_required":    sorted(all_trades),
        "all_recommended_actions": sorted(all_actions),
    }

    # ---------------------------
    # SAVE
    # ---------------------------
    out_path = Path(OUTPUT_FOLDER) / property_id / "aggregated_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[Agent3] Done - {len(global_defects)} unique defects across {len(rooms_output)} rooms")
    print(f"         Critical={critical_count}  Moderate={moderate_count}  Minor={minor_count}")
    print(f"[Agent3] Saved -> {out_path}")

    return report
