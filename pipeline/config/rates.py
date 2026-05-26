AU_LABOUR_RATES = {
  "electrician": {"min": 120, "max": 150},
  "plumber": {"min": 110, "max": 140},
  "carpenter": {"min": 80, "max": 110},
  "plasterer": {"min": 70, "max": 100},
  "painter": {"min": 45, "max": 65},
  "tiler": {"min": 60, "max": 90},
  "builder": {"min": 90, "max": 130},
}

GST_RATE = 0.10

MATERIAL_SUPPLIERS = ["Bunnings Warehouse", "Beaumont Tiles", "Reece Plumbing"]

TRADE_SEQUENCE = [
  "Demolition",
  "Rough-in electrical",
  "Rough-in plumbing",
  "Framing",
  "Insulation",
  "Plasterboard",
  "Cornice",
  "Fit-off",
  "Paint",
  "Flooring",
  "Fix",
]

DEFECT_SEVERITY = ["Critical", "Moderate", "Minor"]