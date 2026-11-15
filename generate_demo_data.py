import json
import os
from backend.app.irsa_client import fetch_spherex_data
from backend.app.astronomical_data import TARGET_CATALOG
from backend.app.gaia_client import get_gaia_dr3_sources

out_dir = os.path.abspath("frontend/demo_data")
os.makedirs(out_dir, exist_ok=True)

targets_list = []
for tid, tinfo in TARGET_CATALOG.items():
    print(f"Generating demo data for {tinfo['name']}...")
    blink_data = fetch_spherex_data(str(tinfo["ra"]), str(tinfo["dec"]), fov_arcmin=5.0, mode="blink")
    diff_data = fetch_spherex_data(str(tinfo["ra"]), str(tinfo["dec"]), fov_arcmin=5.0, mode="diff")
    stack_data = fetch_spherex_data(str(tinfo["ra"]), str(tinfo["dec"]), fov_arcmin=5.0, mode="stack")
    gaia_sources = get_gaia_dr3_sources(tinfo["ra"], tinfo["dec"], fov_arcmin=5.0)

    target_bundle = {
        "target_info": tinfo,
        "blink": blink_data,
        "diff": diff_data,
        "stack": stack_data,
        "gaia": gaia_sources
    }
    with open(os.path.join(out_dir, f"{tid}.json"), "w", encoding="utf-8") as f:
        json.dump(target_bundle, f)
    targets_list.append(tinfo)

with open(os.path.join(out_dir, "targets.json"), "w", encoding="utf-8") as f:
    json.dump(targets_list, f, indent=2)

print("Demo data generated successfully!")

