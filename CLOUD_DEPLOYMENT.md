# CLOUD_DEPLOYMENT — desplegar todo gratis (sin tarjetas)

## 1. Backend (gratis)

```powershell
Copy-Item CLOUD_ENV.example .env   # no subir claves a Git si se publica
flyctl launch --config cloud/fly.toml   # o: Render → New Web Service (Docker)
flyctl secrets set CLOUD_API_TOKEN="tu-token-fuerte"
flyctl deploy
```

URL resultante: `https://ai-ugc-studio-cloud.fly.dev` (o la que asigne el proveedor).

## 2. Motor de IA (HF Space gratis, ZeroGPU)

1. Crea cuenta gratuita en huggingface.co (sin tarjeta).
2. `hf spaces` o web → «New Space» → SDK **Gradio**.
3. Sube `cloud/inference/app.py` + `cloud/inference/requirements.txt`.
4. En el Space, define variables:
   - `LIVEPORTRAIT_DIR` (ruta del repo clonado) y `WAV2LIP_DIR` (ruta del repo).
   - Pesos: LivePortrait se descargan de `KwaiVGI/LivePortrait` (HF).
     Wav2Lip: coloca `wav2lip_gan.pth` oficial en `cloud/data/weights/`
     (la conversión a `wav2lip_gan_state.pth` la hace el adaptador).
5. Espera a que el Space quede **Running**.
6. En el backend: `INFERENCE_URL=https://<tu-space>.hf.space`.

## 3. Frontend

El dashboard ya está listo: abre tu dominio (o el backend) y en la cabecera
pega la **URL del backend** y el **token**. Se guarda en el navegador
(`localStorage`) y todas las llamadas usan Bearer + enlaces de archivo con token.

## 4. Variables (entorno)

Ver `CLOUD_ENV.example`. Obligatorias: `CLOUD_API_TOKEN`, `INFERENCE_URL`.
Opcionales: `FISH_AUDIO_*` (Fish, requiere saldo), `S3_*` (almacenamiento gratis),
`CLOUD_MODE` (FREE_CLOUD por defecto; CLOUD_GPU solo con `ALLOW_PAID=1`).

## 5. GPU de pago (futuro, opcional)

1. En el Space, cambia hardware a GPU de pago (tú pagas).
2. En el backend, define `CLOUD_MODE=CLOUD_GPU` **y** `ALLOW_PAID=1`.
3. Sin ambos, el sistema permanece en FREE_CLOUD.

## 6. Detener servicios

```powershell
flyctl apps destroy ai-ugc-studio-cloud   # o Render → Delete
```

Y en HF: Spaces → tu Space → «Pause» (no consume GPU si está pausado).

## 7. Pruebas (tras desplegar)

```powershell
httpx --verify=no GET https://<backend>/api/cloud/health
.venv\Scripts\python.exe cloud\tests\test_cloud_backend.py   # con BASE/TOKEN de producción
```

Ver `CLOUD_API_DOCUMENTATION.md` para endpoints.
