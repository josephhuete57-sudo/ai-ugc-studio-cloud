"""Prueba real: animar foto + driving corto en un Space público (GPU remota).

Nº de frames mínimo: driving de 1.5 s para no saturar la cola gratuita.
"""
import sys

from gradio_client import Client

SPACE = "KlingTeam/LivePortrait"
PHOTO = r"C:\AI_UGC_STUDIO\LivePortrait\assets\examples\source\s0.jpg"
DRIVING = r"C:\AI_UGC_STUDIO\projects\driving_short15.mp4"

client = Client(SPACE)
info = client.view_api()
print("API:")
for fn_name, fn in info.get("named_endpoints", {}).items():
    params = [p.get("label") or p.get("parameter_name") for p in fn.get("parameters", [])]
    print(" ", fn_name, "->", params)

# Predecir con el endpoint principal probable.
pred = client.predict(PHOTO, DRIVING, api_name="/predict")
print("PRED", str(pred)[:400])
