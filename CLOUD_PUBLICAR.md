# PUBLICAR AI UGC STUDIO — pasos exactos (gratis, sin tarjeta)

No hay forma de publicar un backend sin una cuenta. Por eso necesitas 2 cuentas
gratuitas (sin tarjeta): **Hugging Face** (motor GPU) y **Render o Fly**
(backend). Todo lo demás ya está preparado y probado.

## Paso 1 — Hugging Face (motor ZeroGPU) · 3 minutos

1. Entra en <https://huggingface.co>, **Sign up** (gratis, sin tarjeta).
2. Haz clic en tu avatar → **Settings** → **Access Tokens**.
3. **Create new token** → nombre: `studio-deploy` → rol: **Write** → Create.
4. Copia el token (empieza por `hf_`). Pégalo aquí en el chat **o** ejecútalo tú:
   ```powershell
   $env:HF_TOKEN = "hf_tu_token"
   .venv\Scripts\python.exe cloud\deploy_hf.py
   ```
   Eso crea tu Space (`<usuario>/ai-ugc-studio-motor`), sube el adaptador y
   devuelve la `SPACE_URL`. En el Space, espera a que ponga **Running**
   (puede tardar unos minutos la primera vez).
5. Autorizas solo: **crear un Space público** en tu cuenta y **subir 3 archivos**
   (`app.py`, `requirements.txt`, `README.md`). Nada más.

## Paso 2 — Backend (API) · 5 minutos

Opción A (Render, gratis sin tarjeta):
1. Sube este proyecto a GitHub (gratis).
2. <https://render.com> → **New Web Service** → conecta el repo.
3. Variables de entorno:
   - `CLOUD_API_TOKEN` = token fuerte que elijas (p. ej. 32 letras).
   - `INFERENCE_URL` = la `SPACE_URL` del paso 1.
   - `CLOUD_MODE` = `FREE_CLOUD` (resto por defecto).
4. Deploy → obtienes `https://<nombre>.onrender.com`.

Opción B (Fly): `flyctl auth login` en tu PC y `flyctl deploy` con `cloud/fly.toml`.
(Nota: Fly ya no tiene plan 100 % gratis; Render sí.)

## Paso 3 — Frontend

El dashboard vive en el mismo hosting que el backend (o en GitHub Pages).
En la cabecera del dashboard pega la **URL del backend** y el **token**
(se guarda en tu navegador). Modo cloud: ningún modelo corre en tu PC.

## Costes y límites (gratuitos)

- **HF Space ZeroGPU**: GPU gratuita con cola y límites de tiempo por petición.
  Los trabajos largos pueden tardar o fallar si la cola gratuita está llena
  (el backend guarda el estado `failed` y no finge éxito).
- **Render free**: el servicio se duerme tras 15 min sin uso (30 s para despertar).
- **Fish Audio**: opcional y de pago por uso (sin saldo → TTS remoto gratuito).
- **Pago**: solo si tú activas `CLOUD_MODE=CLOUD_GPU` + `ALLOW_PAID=1`. Por defecto, imposible.

## Qué NO necesitas

Python, FFmpeg, LivePortrait ni Wav2Lip en tu PC para el modo cloud.
El modo local (`127.0.0.1:8001`) sigue como respaldo y no se modificó.
