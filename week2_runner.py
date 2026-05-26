import os
import json
import re
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

def generate_renovation_package(address, bedrooms, bathrooms, scope, details, measurements, start_date):
    
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

Return ONLY this JSON with real data — no preamble, no markdown:
{{
  "property": {{"address": "{address}", "bedrooms": {bedrooms}, "bathrooms": {bathrooms}, "renovation_type": "{scope}"}},
  "scope_of_works": [{{"room": "", "works_required": [], "trade": "", "priority": "Critical|High|Medium|Low"}}],
  "cost_estimate": {{"subtotal_ex_gst": 0, "gst_10pct": 0, "pm_fee_15pct": 0, "contingency_15pct": 0, "grand_total": 0, "currency": "AUD"}},
  "trade_schedule": [{{"phase": 1, "trade": "", "works": "", "estimated_days": 0, "dependency": ""}}],
  "material_list": [{{"item": "", "supplier": "Bunnings Warehouse|Reece Plumbing|Beaumont Tiles|Dulux|Colorbond", "unit": "", "estimated_qty": 0, "unit_rate_aud": 0}}]
}}

RULES:
- Australian terminology: Gyprock not drywall, cornices not crown molding, tapware not faucet
- All costs AUD. GST=subtotal*0.10. PM fee=subtotal*0.15. Contingency=subtotal*0.15.
- Trade sequence: Demo→Pest→Structural→Roof→Electrical→Plumbing→Plasterboard→Tiling→Painting→Fix-off
- Use measurements for accurate quantities
- Return ONLY JSON. No other text."""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 4000
        }
    )
    
    text = response.json()['choices'][0]['message']['content']
    text = re.sub(r'```json\n?', '', text).replace('```', '').strip()
    jsonMatch = re.search(r'\{[\s\S]*\}', text)
    data = json.loads(jsonMatch.group())
    
    # Python calculates costs
    subtotal = data['cost_estimate']['subtotal_ex_gst']
    data['cost_estimate']['gst_10pct'] = round(subtotal * 0.10)
    data['cost_estimate']['pm_fee_15pct'] = round(subtotal * 0.15)
    data['cost_estimate']['contingency_15pct'] = round(subtotal * 0.15)
    data['cost_estimate']['grand_total'] = round(
        subtotal +
        data['cost_estimate']['gst_10pct'] +
        data['cost_estimate']['pm_fee_15pct'] +
        data['cost_estimate']['contingency_15pct']
    )
    
    return data


def format_output(data):
    output = {}
    
    # SOW
    sow = f"SCOPE OF WORKS — {data['property']['address']}\n"
    sow += f"{data['property']['bedrooms']} bed | {data['property']['bathrooms']} bath | {data['property']['renovation_type']}\n\n"
    for room in data['scope_of_works']:
        sow += f"{room['room']} — {room['priority']} priority\n"
        sow += f"Trade: {room['trade']}\n"
        sow += f"Works: {', '.join(room['works_required'])}\n\n"
    output['sow'] = sow

    # Cost
    c = data['cost_estimate']
    cost = "COST ESTIMATE (AUD)\n"
    cost += f"Subtotal ex GST: ${c['subtotal_ex_gst']:,}\n"
    cost += f"GST (10%): ${c['gst_10pct']:,}\n"
    cost += f"PM Fee (15%): ${c['pm_fee_15pct']:,}\n"
    cost += f"Contingency (15%): ${c['contingency_15pct']:,}\n"
    cost += f"GRAND TOTAL: ${c['grand_total']:,} AUD\n"
    cost += "Indicative estimate. Physical inspection required."
    output['cost'] = cost

    # Schedule
    schedule = "TRADE SCHEDULE\n"
    for phase in data['trade_schedule']:
        schedule += f"Phase {phase['phase']}: {phase['trade']} — {phase['works']} ({phase['estimated_days']} days)"
        if phase['dependency']:
            schedule += f" | After: {phase['dependency']}"
        schedule += "\n"
    output['schedule'] = schedule

    # Materials
    materials = "MATERIAL LIST\n"
    by_supplier = {}
    for item in data.get('material_list', []):
        supplier = item.get('supplier', 'General')
        if supplier not in by_supplier:
            by_supplier[supplier] = []
        by_supplier[supplier].append(item)
    
    for supplier, items in by_supplier.items():
        materials += f"\n{supplier}\n"
        for item in items:
            total = item['estimated_qty'] * item['unit_rate_aud']
            materials += f"— {item['item']}: {item['estimated_qty']} {item['unit']} @ ${item['unit_rate_aud']} = ${total:,}\n"
    output['materials'] = materials

    # Orders
    order = "MATERIAL ORDER — Ready to send to suppliers\n"
    for supplier, items in by_supplier.items():
        supplier_total = sum(i['estimated_qty'] * i['unit_rate_aud'] for i in items)
        order += f"\nOrder to {supplier} — Est. total: ${supplier_total:,} AUD\n"
        for item in items:
            order += f"  • {item['item']} — Qty: {item['estimated_qty']} {item['unit']}\n"
        order += "  Confirm pricing before ordering. Quantities indicative.\n"
    output['order'] = order

    return output