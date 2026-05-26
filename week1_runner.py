import sys
import os
from dotenv import load_dotenv

_pipeline_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline")

# Add pipeline to Python path so orchestrator and its agents can be imported
sys.path.insert(0, _pipeline_root)

load_dotenv(os.path.join(_pipeline_root, ".env"))
OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", os.path.join(_pipeline_root, "outputs"))

from orchestrator import run_pipeline  # noqa: E402 — must come after sys.path update


def run_week1_pipeline(input_folder: str) -> dict:
    # Snapshot existing output folders
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    existing = set(os.listdir(OUTPUT_FOLDER))

    try:
        run_pipeline(input_folder)
    except Exception as e:
        return {"error": str(e)}

    # Find new output folder created by the pipeline
    new_folders = set(os.listdir(OUTPUT_FOLDER)) - existing
    if not new_folders:
        all_folders = [os.path.join(OUTPUT_FOLDER, f) for f in os.listdir(OUTPUT_FOLDER)]
        if not all_folders:
            return {"error": "No output folder found."}
        latest = max(all_folders, key=os.path.getmtime)
    else:
        latest = os.path.join(OUTPUT_FOLDER, sorted(new_folders)[-1])

    docs_folder = os.path.join(latest, "docs")
    if not os.path.exists(docs_folder):
        docs_folder = latest

    docx_files = [f for f in os.listdir(docs_folder) if f.endswith(".docx")]
    if not docx_files:
        return {"error": f"No documents found in {docs_folder}"}

    return {"docx": [os.path.join(docs_folder, f) for f in sorted(docx_files)]}
