import sys
import os

# Add pipeline to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pipeline"))

from orchestrator import run_pipeline
import tempfile
import shutil
import zipfile
import io

OUTPUTS_ROOT = os.path.join(os.path.dirname(__file__), "pipeline", "outputs")

def run_week1_pipeline(uploaded_files: list) -> dict:
    # Save uploaded files to temp input folder
    temp_input = tempfile.mkdtemp()
    for f in uploaded_files:
        save_path = os.path.join(temp_input, f.name)
        with open(save_path, "wb") as out:
            out.write(f.read())

    # Snapshot existing output folders
    os.makedirs(OUTPUTS_ROOT, exist_ok=True)
    existing = set(os.listdir(OUTPUTS_ROOT))

    try:
        # Call orchestrator directly — same Python process, same environment
        run_pipeline(temp_input)
    except Exception as e:
        shutil.rmtree(temp_input, ignore_errors=True)
        return {"error": str(e)}

    shutil.rmtree(temp_input, ignore_errors=True)

    # Find new output folder
    new_folders = set(os.listdir(OUTPUTS_ROOT)) - existing
    if not new_folders:
        all_folders = [os.path.join(OUTPUTS_ROOT, f) for f in os.listdir(OUTPUTS_ROOT)]
        if not all_folders:
            return {"error": "No output folder found."}
        latest = max(all_folders, key=os.path.getmtime)
    else:
        latest = os.path.join(OUTPUTS_ROOT, sorted(new_folders)[-1])

    docs_folder = os.path.join(latest, "docs")
    if not os.path.exists(docs_folder):
        docs_folder = latest

    docx_files = [f for f in os.listdir(docs_folder) if f.endswith(".docx")]
    if not docx_files:
        return {"error": f"No documents found in {docs_folder}"}

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for f in docx_files:
            zf.write(os.path.join(docs_folder, f), f)
    zip_buffer.seek(0)

    return {"zip": zip_buffer}