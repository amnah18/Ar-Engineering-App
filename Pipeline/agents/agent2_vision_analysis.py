import os
import re
import json
import base64
from pathlib import Path
from groq import Groq

GROQ_MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def run_agent2(frames_folder: str, output_folder: str) -> list:
    os.makedirs(output_folder, exist_ok=True)

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    frame_files = sorted(
        list(Path(frames_folder).glob("*.jpg")) +
        list(Path(frames_folder).glob("*.jpeg"))
    )

    if not frame_files:
        raise RuntimeError(f"No frames found in {frames_folder}")

    print(f"\n[Agent 2] Analysing {len(frame_files)} frames via Groq Vision...")

    saved = []
    failed = []

    for frame_path in frame_files:
        output_json = Path(output_folder) / (frame_path.stem + ".json")

        prompt = f"""You are an Australian renovation inspector.

Analyse this property image carefully.

Output ONLY a raw JSON object. No explanation. No markdown. No code fences.
Start your response with {{ and end with }}.

Use this exact structure:
{{
  "frame_id": "{frame_path.stem}",
  "room": "lounge|kitchen|bathroom|toilet|laundry|bedroom|hallway|exterior_site|exterior_roof|exterior_walls|garage|shed",
  "defects": [
    {{
      "name": "defect name",
      "severity": "Critical|Moderate|Minor",
      "location": "precise location",
      "action": "recommended action"
    }}
  ],
  "trades_required": ["trade1"],
  "materials_identified": ["material1"]
}}

Australian terminology only: Gyprock, cornices, eaves, tapware, plasterboard.
If image is unreadable: {{"frame_id": "{frame_path.stem}", "image_unreadable": true, "reason": "why"}}
Output the JSON object only. Nothing else."""

        try:
            image_data = _encode_image(str(frame_path))

            response = client.chat.completions.create(
                model=GROQ_MODEL_VISION,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=1024
            )

            stdout = response.choices[0].message.content.strip()
            json_match = re.search(r'\{.*\}', stdout, re.DOTALL)

            if json_match:
                with open(output_json, 'w', encoding='utf-8') as f:
                    f.write(json_match.group())
                saved.append(str(output_json))
                print(f"[Agent 2] Saved: {output_json.name}")
            else:
                failed.append(frame_path.name)
                print(f"[Agent 2] No JSON in response for: {frame_path.name}")

        except Exception as e:
            failed.append(frame_path.name)
            print(f"[Agent 2] Error on {frame_path.name}: {str(e)}")
            continue

    print(f"\n[Agent 2] Complete — {len(saved)} saved, {len(failed)} failed")

    if not saved:
        raise RuntimeError("No JSON files produced by Agent 2")

    return saved