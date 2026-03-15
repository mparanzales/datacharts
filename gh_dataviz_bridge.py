# ═══════════════════════════════════════════════════════════════
# GH Data Visualization Bridge
# Paste this into a GHPython component
#
# INPUTS to add on the component:
#   data  → the GH data (list of rows, each row is a list of values)
#   keys  → list of column name strings  e.g. ["Floor","Type","GFA","Facade Area"]
#   run   → Boolean (connect a Button component to trigger refresh)
#
# OUTPUT:
#   out   → status message (connect a Panel to see it)
# ═══════════════════════════════════════════════════════════════

import json
import os
import re

# ── 1. Default column names if none provided ──────────────────
col_names = list(keys) if keys else ["Floor", "Type", "GFA", "Facade Area"]

# ── 2. Build JSON rows from input data ────────────────────────
rows = []

if data:
    for row in data:
        obj = {}
        # row might be a single value or a list of values
        vals = list(row) if hasattr(row, "__iter__") and not isinstance(row, str) else [row]
        for j, v in enumerate(vals):
            k = col_names[j] if j < len(col_names) else "Col{}".format(j)
            # Try to cast to number, keep as string otherwise
            try:
                obj[k] = int(v) if str(v).lstrip("-").isdigit() else float(v)
            except (ValueError, TypeError):
                obj[k] = str(v)
        rows.append(obj)

# ── 3. Find the HTML file on the Desktop ─────────────────────
# Tries both OneDrive Desktop (Spanish) and standard Desktop
possible_paths = [
    os.path.join(os.path.expanduser("~"), "OneDrive", "Escritorio", "rhino-dataviz-v2.html"),
    os.path.join(os.path.expanduser("~"), "Desktop",                 "rhino-dataviz-v2.html"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop",     "rhino-dataviz-v2.html"),
]
html_path = next((p for p in possible_paths if os.path.exists(p)), None)

# ── 4. Inject data + open browser ────────────────────────────
if not rows:
    out = "No data connected. Connect your GH data to the 'data' input."

elif html_path is None:
    out = "Could not find rhino-dataviz-v2.html. Make sure it is on your Desktop."

else:
    json_str = json.dumps(rows, indent=2)

    # Read the HTML
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Replace the embedded JSON data block
    new_html = re.sub(
        r'(<script id="chart-data" type="application/json">).*?(</script>)',
        lambda m: m.group(1) + "\n" + json_str + "\n" + m.group(2),
        html,
        flags=re.DOTALL
    )

    # Write back
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    # Open in default browser only when run = True
    if run:
        os.startfile(html_path)

    out = "OK — {} rows written. {}".format(
        len(rows),
        "Browser opened." if run else "Toggle 'run' to open browser."
    )
