import os
import io
import re
import json
import zipfile
import tempfile
import shutil
from datetime import datetime

import streamlit as st
import requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from week1_runner import run_week1_pipeline  # type: ignore[import]

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))


# ─── PAGE CONFIG ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="AR Engineering — Renovation Automation",
    page_icon="🏗️",
    layout="wide"
)

# ─── HELPERS ──────────────────────────────────────────────────────────
def call_groq(prompt, max_tokens=4000, temperature=0.1):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    )
    return response.json()['choices'][0]['message']['content']


def parse_json(text):
    text = re.sub(r'```json\n?', '', text).replace('```', '').strip()
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        raise ValueError("No JSON found in response")
    return json.loads(match.group())


def generate_pdf(content, title):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "AR Engineering Services Pty Ltd")
    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, title)
    y -= 25
    c.setFont("Helvetica", 9)
    for line in content.split('\n'):
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 9)
        c.drawString(50, y, line[:110])
        y -= 13
    c.save()
    buffer.seek(0)
    return buffer.read()


def get_sheets():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        return client.open_by_key("1FsfXTixyoXCGpPj7J0FkpzESutXdMcimqVKnBM-We2k")
    except Exception:
        return None


# ─── HEADER ───────────────────────────────────────────────────────────
st.title("🏗️ AR Engineering Services")
st.subheader("Property Renovation Automation System")
st.caption("Built by Amnah Aziza | Week 1 + Week 2 Combined | May 2026")
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Property Brief",
    "📝 Progress Update",
    "📊 Investor Report",
    "🎥 Visual Inspection",
    "ℹ️ About"
])

# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — PROPERTY BRIEF
# ═══════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Generate Renovation Package")
    st.caption("Fill in property details. Full package ready in 60 seconds.")

    col1, col2 = st.columns(2)

    with col1:
        address = st.text_input(
            "Property Address *",
            placeholder="46 Darlimurla Ave Newborough VIC 3825"
        )
        bedrooms = st.number_input("Bedrooms *", min_value=1, max_value=10, value=3)
        bathrooms = st.number_input("Bathrooms *", min_value=1, max_value=10, value=1)
        scope = st.selectbox("Renovation Scope *", [
            "Full Renovation",
            "Kitchen Only",
            "Bathrooms Only",
            "Kitchen and Bathrooms",
            "Flooring Only",
            "Exterior Only",
            "Custom"
        ])
        start_date = st.date_input("Planned Start Date")
        details = st.text_area(
            "Additional Details",
            placeholder="e.g. roof inspection, new flooring, exterior repaint"
        )

    with col2:
        st.subheader("Room Measurements (optional)")
        st.caption("Enter in metres for accurate quantities")
        kitchen = st.text_input("Kitchen (L x W)", placeholder="4 x 3")
        living = st.text_input("Living Room (L x W)", placeholder="6 x 4")
        bed1 = st.text_input("Bedroom 1 (L x W)", placeholder="4 x 3.5")
        bed2 = st.text_input("Bedroom 2 (L x W)", placeholder="3.5 x 3")
        bed3 = st.text_input("Bedroom 3 (L x W)", placeholder="3 x 3")
        bath1 = st.text_input("Bathroom 1 (L x W)", placeholder="2.5 x 2")
        bath2 = st.text_input("Bathroom 2 (L x W)", placeholder="2 x 1.8")
        floor_area = st.number_input("Total Floor Area (m²)", min_value=0, value=0)

    st.divider()
    generate_btn = st.button(
        "🚀 Generate Renovation Package",
        type="primary",
        use_container_width=True
    )

    if generate_btn:
        if not address:
            st.error("Please enter a property address.")
        else:
            measurements = f"""
Kitchen: {kitchen or 'Not provided'}
Living Room: {living or 'Not provided'}
Bedroom 1: {bed1 or 'Not provided'}
Bedroom 2: {bed2 or 'Not provided'}
Bedroom 3: {bed3 or 'Not provided'}
Bathroom 1: {bath1 or 'Not provided'}
Bathroom 2: {bath2 or 'Not provided'}
Total Floor Area: {floor_area if floor_area > 0 else 'Not provided'} m²
"""
            prompt = f"""You are an Australian renovation coordinator for AR Engineering Services Pty Ltd.

Property details:
Address: {address}
Bedrooms: {bedrooms}
Bathrooms: {bathrooms}
Renovation Scope: {scope}
Additional Details: {details}
Start Date: {start_date}

Room Measurements:
{measurements}

Return ONLY this JSON — no preamble, no markdown:
{{
  "property": {{"address": "{address}", "bedrooms": {bedrooms}, "bathrooms": {bathrooms}, "renovation_type": "{scope}"}},
  "scope_of_works": [{{"room": "", "works_required": [], "trade": "", "priority": "High"}}],
  "cost_estimate": {{"subtotal_ex_gst": 0, "gst_10pct": 0, "pm_fee_15pct": 0, "contingency_15pct": 0, "grand_total": 0, "currency": "AUD"}},
  "trade_schedule": [{{"phase": 1, "trade": "", "works": "", "estimated_days": 0, "dependency": ""}}],
  "material_list": [{{"item": "", "supplier": "Bunnings Warehouse", "unit": "", "estimated_qty": 0, "unit_rate_aud": 0}}]
}}

RULES:
- Australian terminology: Gyprock not drywall, cornices not crown molding, tapware not faucet, eaves not soffits
- All costs AUD. GST=subtotal*0.10. PM fee=subtotal*0.15. Contingency=subtotal*0.15.
- Trade sequence: Demo→Pest→Structural→Roof→Electrical→Plumbing→Plasterboard→Tiling→Painting→Fix-off
- Use measurements for accurate quantities
- Return ONLY JSON."""

            with st.spinner("Generating renovation package..."):
                try:
                    raw = call_groq(prompt)
                    data = parse_json(raw)

                    # Python calculates costs — never AI
                    sub = data['cost_estimate']['subtotal_ex_gst']
                    data['cost_estimate']['gst_10pct'] = round(sub * 0.10)
                    data['cost_estimate']['pm_fee_15pct'] = round(sub * 0.15)
                    data['cost_estimate']['contingency_15pct'] = round(sub * 0.15)
                    data['cost_estimate']['grand_total'] = round(
                        sub +
                        data['cost_estimate']['gst_10pct'] +
                        data['cost_estimate']['pm_fee_15pct'] +
                        data['cost_estimate']['contingency_15pct']
                    )

                    # Format outputs
                    c = data['cost_estimate']
                    sow = f"SCOPE OF WORKS — {data['property']['address']}\n"
                    sow += f"{data['property']['bedrooms']} bed | {data['property']['bathrooms']} bath | {data['property']['renovation_type']}\n\n"
                    for room in data['scope_of_works']:
                        sow += f"{room['room']} — {room['priority']} priority\n"
                        sow += f"Trade: {room['trade']}\n"
                        sow += f"Works: {', '.join(room['works_required'])}\n\n"

                    cost = "COST ESTIMATE (AUD)\n"
                    cost += f"Subtotal ex GST: ${c['subtotal_ex_gst']:,}\n"
                    cost += f"GST (10%): ${c['gst_10pct']:,}\n"
                    cost += f"PM Fee (15%): ${c['pm_fee_15pct']:,}\n"
                    cost += f"Contingency (15%): ${c['contingency_15pct']:,}\n"
                    cost += f"GRAND TOTAL: ${c['grand_total']:,} AUD\n"
                    cost += "Indicative estimate. Physical inspection required."

                    schedule = "TRADE SCHEDULE\n"
                    for phase in data['trade_schedule']:
                        schedule += f"Phase {phase['phase']}: {phase['trade']} — {phase['works']} ({phase['estimated_days']} days)"
                        if phase.get('dependency'):
                            schedule += f" | After: {phase['dependency']}"
                        schedule += "\n"

                    by_supplier = {}
                    for item in data.get('material_list', []):
                        s = item.get('supplier', 'General')
                        by_supplier.setdefault(s, []).append(item)

                    materials = "MATERIAL LIST\n"
                    for sup, items in by_supplier.items():
                        materials += f"\n{sup}\n"
                        for item in items:
                            total = item['estimated_qty'] * item['unit_rate_aud']
                            materials += f"— {item['item']}: {item['estimated_qty']} {item['unit']} @ ${item['unit_rate_aud']} = ${total:,}\n"

                    order = "MATERIAL ORDER — Ready to send to suppliers\n"
                    for sup, items in by_supplier.items():
                        sup_total = sum(i['estimated_qty'] * i['unit_rate_aud'] for i in items)
                        order += f"\nOrder to {sup} — Est. total: ${sup_total:,} AUD\n"
                        for item in items:
                            order += f"  • {item['item']} — Qty: {item['estimated_qty']} {item['unit']}\n"
                        order += "  Confirm pricing before ordering. Quantities indicative.\n"

                    st.success("✅ Package generated successfully!")
                    st.divider()

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.subheader("📄 Scope of Works")
                        st.text_area("", sow, height=400, key="sow")
                        st.subheader("💰 Cost Estimate")
                        st.text_area("", cost, height=220, key="cost")
                    with col_b:
                        st.subheader("📅 Trade Schedule")
                        st.text_area("", schedule, height=300, key="schedule")
                        st.subheader("🔧 Material List")
                        st.text_area("", materials, height=320, key="materials")

                    st.subheader("📦 Material Order")
                    st.text_area("", order, height=200, key="order")

                    full_output = f"""AR ENGINEERING SERVICES PTY LTD
RENOVATION PACKAGE — {address}
Generated: {str(start_date)}
{'='*60}

{sow}
{'='*60}

{cost}
{'='*60}

{schedule}
{'='*60}

{materials}
{'='*60}

{order}

DISCLAIMER: All quantities are indicative. Physical site inspection required before procurement.
"""
                    # Save to Google Sheets
                    sheet = get_sheets()
                    if sheet:
                        try:
                            ws = sheet.worksheet("Properties")
                            existing = ws.get_all_records()
                            addresses = [r.get('Address', '') for r in existing]
                            if address not in addresses:
                                ws.append_row([
                                    address,
                                    "Preliminary - Awaiting Inspection",
                                    bedrooms,
                                    bathrooms,
                                    c['grand_total'],
                                    str(start_date),
                                    scope,
                                    sow,
                                    cost,
                                    materials,
                                    schedule
                                ])
                                st.info("✅ Property saved to Google Sheets dashboard.")
                        except Exception:
                            pass

                    pdf_data = generate_pdf(full_output, f"Renovation Package — {address}")
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_data,
                        file_name=f"AR_{address.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

                except Exception as e:
                    st.error(f"Error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — PROGRESS UPDATE
# ═══════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Log Progress Update")
    st.caption("Save a progress update for any active property.")

    update_address = st.text_input(
        "Property Address *",
        placeholder="46 Darlimurla Ave Newborough VIC 3825",
        key="update_addr"
    )
    update_note = st.text_area(
        "Progress Note *",
        placeholder="e.g. Demolition complete. Site cleared. Pest inspection booked for tomorrow.",
        key="update_note"
    )

    if st.button("💾 Save Progress Update", type="primary", use_container_width=True):
        if not update_address or not update_note:
            st.error("Please fill in both address and progress note.")
        else:
            sheet = get_sheets()
            if sheet:
                try:
                    ws = sheet.worksheet("Progress update")
                    ws.append_row([
                        update_address,
                        update_note,
                        datetime.now().strftime("%d/%m/%Y %H:%M")
                    ])
                    st.success(f"✅ Progress update saved for {update_address}")
                except Exception as e:
                    st.error(f"Error saving to Google Sheets: {str(e)}")
            else:
                st.warning("Google Sheets not connected. Add credentials.json to connect.")
                st.info(f"Update logged:\nAddress: {update_address}\nNote: {update_note}\nTime: {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — INVESTOR REPORT
# ═══════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Generate Investor Report")
    st.caption("Reads real progress updates and generates a professional weekly report.")

    report_address = st.text_input(
        "Property Address *",
        placeholder="46 Darlimurla Ave Newborough VIC 3825",
        key="report_addr"
    )

    if st.button("📊 Generate Investor Report", type="primary", use_container_width=True):
        if not report_address:
            st.error("Please enter a property address.")
        else:
            with st.spinner("Reading progress data and generating report..."):
                try:
                    updates_text = "No updates recorded yet."
                    property_info = {}

                    sheet = get_sheets()
                    if sheet:
                        props = sheet.worksheet("Properties").get_all_records()
                        updates = sheet.worksheet("Progress update").get_all_records()
                        property_info = next(
                            (p for p in props if report_address.lower() in p.get("Address", "").lower()),
                            {}
                        )
                        property_updates = [
                            u for u in updates
                            if report_address.lower() in u.get("Address", "").lower()
                        ]
                        if property_updates:
                            updates_text = "\n".join([
                                f"[{u.get('Date Time','')}] {u.get('Update Note','')}"
                                for u in property_updates
                            ])

                    report_prompt = f"""You are an Australian renovation project coordinator generating a weekly investor report for AR Engineering Services Pty Ltd.

Property: {report_address}
Status: {property_info.get('Status', 'Preliminary')}
Budget: ${property_info.get('Grand Total AUD', 'TBC')} AUD
Renovation Type: {property_info.get('Renovation Type', 'Full Renovation')}

Progress Updates:
{updates_text}

Write a professional weekly investor progress report in Australian English. Include:
- Overall status (On Track / At Risk / Delayed)
- Completion percentage estimate
- What was completed this week
- What is currently in progress
- Next week plan
- Budget status
- Professional closing message for the investor

Keep it professional, concise, and factual. Base it only on the progress updates provided."""

                    report_text = call_groq(report_prompt, max_tokens=1000, temperature=0.3)

                    st.success("✅ Investor report generated!")
                    st.text_area("Weekly Investor Report", report_text, height=500, key="report_out")

                    pdf_data = generate_pdf(
                        report_text,
                        f"Weekly Investor Report — {report_address}"
                    )
                    st.download_button(
                        label="⬇️ Download Report PDF",
                        data=pdf_data,
                        file_name=f"Investor_Report_{report_address.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

                except Exception as e:
                    st.error(f"Error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — VISUAL INSPECTION
# ═══════════════════════════════════════════════════════════════════════
with tab4:
    st.header("🎥 Visual Inspection Pipeline")
    st.caption("Drag and drop your property videos or images below.")

    uploaded_files = st.file_uploader(
        "Drop files here",
        type=["mp4", "mov", "jpg", "jpeg"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) ready: {', '.join([f.name for f in uploaded_files])}")

        if st.button("🔍 Run Pipeline", type="primary", use_container_width=True):
            # Save all uploaded files into a temp folder
            temp_input = tempfile.mkdtemp()
            for f in uploaded_files:
                save_path = os.path.join(temp_input, f.name)
                with open(save_path, "wb") as out:
                    out.write(f.read())

            with st.spinner("Pipeline running... please wait."):
                result = run_week1_pipeline(temp_input)

            # Clean up temp folder
            shutil.rmtree(temp_input, ignore_errors=True)

            if "error" in result:
                st.error(result["error"])

            else:
                st.success("✅ Pipeline complete.")
                st.divider()
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for docx_path in result["docx"]:
                        zf.write(docx_path, os.path.basename(docx_path))

                zip_buffer.seek(0)

                st.download_button(
                    label="⬇️ Download All Documents",
                    data=zip_buffer,
                    file_name="AR_Engineering_Reports.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary",
                    key="download_all_docs_tab2"
                )
# ═══════════════════════════════════════════════════════════════════════
# TAB 5 — ABOUT
# ═══════════════════════════════════════════════════════════════════════
with tab5:
    st.header("About This System")
    st.markdown("""
    **AR Engineering Services — Property Renovation Automation**

    Built by Amnah Aziza | Trial Contractor | May 2026

    ---

    ### What This System Does
    Replaces the Project Manager Assistant for renovation coordination.
    Three functions — property brief, progress update, investor report — replace 13–23 hours of manual work per property.

    | Function | Manual Time | Automated Time |
    |---|---|---|
    | Scope of Works | 2–3 hours | 60 seconds |
    | Cost Estimate | 1–2 hours | 60 seconds |
    | Material List + Order | 1–2 hours | 60 seconds |
    | Trade Schedule | 1–2 hours | 60 seconds |
    | Progress Update | 30 min/day | 5 seconds |
    | Investor Report | 1–2 hours/week | 60 seconds |

    ---

    ### Stack
    - **AI:** Groq API (llama-3.3-70b-versatile)
    - **Vision Pipeline:** Claude Code CLI + OpenCV + PySceneDetect (Week 1)
    - **Database:** Google Sheets
    - **Framework:** Streamlit
    - **Language:** Python

    ---

    ### Known Limitations
    - Material quantities are indicative — physical site measurement required
    - Prices are estimates — verify current pricing before ordering
    - Trade schedule is a planning tool — confirm contractor availability
    - Investor report quality depends on progress updates entered
    - Visual inspection requires Week 1 pipeline installed locally

    ---

    *AR Engineering Services Pty Ltd — Confidential*
    """)