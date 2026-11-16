"""
Precalcula los 5 objetivos de prueba con DATOS REALES de SPHEREx (IRSA) y los
guarda en frontend/demo_data/ para que la demo funcione sin red.

Uso:  python generate_demo_data.py            (todos)
      python generate_demo_data.py barnard    (uno)
      python generate_demo_data.py --refresh  (ignora la caché y vuelve a consultar IRSA)
"""

import json
import os
import sys
import time
import traceback

from backend.app import viewer
from backend.app.targets import TARGETS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "demo_data")
os.makedirs(OUT, exist_ok=True)


def run(tid: str, refresh: bool):
    t = TARGETS[tid]
    bundle = {"target": t, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "errors": []}
    t0 = time.time()
    try:
        bundle["view"] = viewer.build_view(t["ra"], t["dec"], tid, 5.0, None, True, refresh=refresh)
        print(f"  visor: {bundle['view']['status']} ({time.time() - t0:.0f}s)")
    except Exception as e:
        bundle["errors"].append(f"visor: {e}")
        traceback.print_exc()
    for name, fn in (("spectrum", viewer.build_spectrum), ("lightcurve", viewer.build_lightcurve)):
        t1 = time.time()
        try:
            bundle[name] = fn(t["ra"], t["dec"], tid, refresh=refresh) if name == "lightcurve" else \
                fn(t["ra"], t["dec"], tid, None, refresh)
            print(f"  {name}: {bundle[name]['status']} ({time.time() - t1:.0f}s)")
        except Exception as e:
            bundle["errors"].append(f"{name}: {e}")
            traceback.print_exc()
    with open(os.path.join(OUT, f"{tid}.json"), "w", encoding="utf-8") as f:
        json.dump(bundle, f)
    return bundle


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    refresh = "--refresh" in sys.argv
    ids = args or list(TARGETS)
    for tid in ids:
        print(f"[{tid}] {TARGETS[tid]['name']}")
        run(tid, refresh)
    with open(os.path.join(OUT, "targets.json"), "w", encoding="utf-8") as f:
        json.dump(list(TARGETS.values()), f, ensure_ascii=False, indent=2)
    print("Listo:", OUT)
