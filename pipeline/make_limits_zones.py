import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
L = json.load(open(ROOT / "docs/limits.json"))
a, b = L["limits"]["1"], L["limits"]["300"]
P = L["planet_nine_literature"]
out = {"schema": "limits-zones-1.0", "distances_au": L["distances_au"],
       "bodies": [{"name": x["name"], "mag": x["mag"]} for x in L["bodies"]],
       "zones": [{"id": "single_frame", "label": "Visible in one SPHEREx frame", "mag_max": a},
                 {"id": "stack_only", "label": "Visible only by stacking up to 300 frames", "mag_min": a, "mag_max": b},
                 {"id": "undetectable", "label": "Too faint for SPHEREx", "mag_min": b}],
       "limits": L["limits"],
       "planet_nine": {"label": "Planet Nine (predicted)", "distance_au": [290, 800], "mag": P["V_range"],
                       "source": P["source"], "source_url": "https://arxiv.org/abs/2507.22297"},
       "caveats": L["caveats"]}
json.dump(out, open(ROOT / "docs/limits_zones.json", "w"), indent=1)
print("wrote docs/limits_zones.json; zones at", a, "and", b)
