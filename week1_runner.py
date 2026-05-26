import subprocess
import os
import shutil
from datetime import datetime

PIPELINE_ROOT = os.path.join(os.path.dirname(__file__), "pipeline")
OUTPUTS_ROOT  = os.path.join(os.path.dirname(__file__), "pipeline", "outputs")
ORCHESTRATOR  = os.path.join(os.path.dirname(__file__), "pipeline", "orchestrator.py")

def run_week1_pipeline(input_folder: str) -> dict:

    # Snapshot existing output folders before running
    existing = set(os.listdir(OUTPUTS_ROOT)) if os.path.exists(OUTPUTS_ROOT) else set()

    # Run the pipeline
    result = subprocess.run(
        ["python", ORCHESTRATOR, input_folder],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=PIPELINE_ROOT
    )

    if result.returncode != 0:
        return {"error": f"Pipeline failed.\n\n{result.stderr}"}

    # Find the new output folder
    new_folders = set(os.listdir(OUTPUTS_ROOT)) - existing

    if not new_folders:
        all_folders = [os.path.join(OUTPUTS_ROOT, f) for f in os.listdir(OUTPUTS_ROOT)]
        if not all_folders:
            return {"error": "No output folder found after pipeline ran."}
        latest = max(all_folders, key=os.path.getmtime)
    else:
        latest = os.path.join(OUTPUTS_ROOT, sorted(new_folders)[-1])

    # Find docs subfolder
    docs_folder = os.path.join(latest, "docs")
    if not os.path.exists(docs_folder):
        docs_folder = latest

    # Collect all docx files
    docx_files = [
        os.path.join(docs_folder, f)
        for f in os.listdir(docs_folder)
        if f.endswith(".docx")
    ]

    if not docx_files:
        return {"error": f"Pipeline ran but no documents found in {docs_folder}"}

    return {
        "docx": docx_files,
        "folder": docs_folder
    }