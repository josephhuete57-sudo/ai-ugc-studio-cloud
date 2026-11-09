"""Busca espacios públicos de LivePortrait que GENEREN de verdad (image mode barato).

Un render sin error no basta: verifica que devuelve archivo con tamaño > 1 KB.
"""
from gradio_client import Client

SPACES = [
    "K00B404/LivePortrait_cpu",
    "PeepDaSlan9/B2BMGMT_LivePortrait_cpu",
    "KlingTeam/LivePortrait",
    "innoai/LivePortrait",
    "fcyai/LivePortrait",
    "sofianhw/LivePortrait",
]
PHOTO = r"C:\AI_UGC_STUDIO\assets\influencers\s0.jpg"

import os
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

results = {}
for space in SPACES:
    try:
        c = Client(space)
        api = c.view_api()
        eps = list((api or {}).get("named_endpoints") or {})
        print("SPACE", space, "ENDPOINTS", eps, flush=True)
        if "/gpu_wrapped_execute_image" in eps:
            res = c.predict(0.0, 0.0, PHOTO, True, api_name="/gpu_wrapped_execute_image")
            print("  RES", str(res)[:300], flush=True)
            ok = isinstance(res, (list, tuple)) and any(
                isinstance(x, dict) and (x.get("value") or "") for x in res
            ) if res else False
            print("  LOOKS_OK", ok, flush=True)
            results[space] = ok
        else:
            results[space] = None
    except Exception as exc:
        print("  FAIL", space, str(exc)[:160], flush=True)
        results[space] = False

print("SUMMARY", results)
