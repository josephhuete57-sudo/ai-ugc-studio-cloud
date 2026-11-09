# RAM_OPTIMIZATION_REPORT — perfil LOW_RAM_12GB

Equipo: 12 GB RAM, sin GPU NVIDIA, CPU Intel i7-4702MQ (4c/8h), Windows.
Perfil permanente: `PROFILE=LOW_RAM_12GB` (en `.env`).
Paginación Windows: `True` (automática, 1920 MB asignados) — no modificada.

## Réplica implementada

- **Una tarea pesada a la vez**: cola de 1 worker (`max_workers=1`); sin cambios de arquitectura.
- **Hilos limitados**: `CPU_THREADS=2`, `FFMPEG_THREADS=2`, `OMP/MKL_NUM_THREADS=2`
  en LivePortrait y Wav2Lip (subprocesos), `-threads 2` en FFmpeg.
- **Batches mínimos**: Wav2Lip `face_det=1`, `wav2lip=2`, `resize_factor=2`.
- **Resolución de trabajo**: `--source-max-dim 512` en LivePortrait; editor 720×1280
  por defecto y 1080×1920 opcional (ambos verificados).
- **Liberación entre etapas**: `gc.collect()` + `cleanup_temp_safe()` tras animación
  y tras lip-sync (con reporte de RAM libre en el log del trabajo).
- **Pausa si RAM baja**: pausa con aviso si hay < 2.5 GB libres; tras 10 min
  continúa con advertencia (sin límite artificial que rompa la asignación).
- **Control de procesos hijos**: LivePortrait/Wav2Lip como subprocesos que
  terminan solos; cancelación mata el árbol.
- **Limpieza segura** (`/api/system/cleanup`): solo temporales viejos
  (`Wav2Lip/temp/result.avi`, carpetas `render_*` >1 día, `.pkl` de caché >7 días).
  Nunca toca proyectos ni exports finales.

## Monitor (dashboard + `/api/system/memory`)

RAM total/usada/disponible, consumo Python / LivePortrait / Wav2Lip por child
(scan de cmdline vía CIM), CPU del sistema, etapa actual, ETA estimado (solo con
histórico), alertas normal/elevada/crítica. Caché de 5 s.

## Mediciones reales (flujo completo con el perfil, job #16)

| Momento | Libre | Usada | Carga | Python | LivePortrait | Wav2Lip |
|---|---|---|---|---|---|---|
| Antes (reposo) | 8.17 GB | 3.75 GB | 31 % | ~56 MB | 0 | 0 |
| Animando (38 frames) | 6.26–6.64 GB | 5.3–5.7 GB | 44–47 % | 53–56 MB | **1359–1528 MB** | — |
| Tras animación | **8.1 GB libres** (log) | — | — | — | (proceso cerrado) | — |
| Tras lip-sync | **8.1 GB libres** (log) | — | — | — | — | (proceso cerrado) |
| Después (reposo) | 7.74 GB | 4.18 GB | 35 % | 53 MB | 0 | 0 |

- **Mínimo libre observado**: 6.26 GB (frente a umbral de pausa de 2.5 GB).
- **Pico de LivePortrait**: ~1.5 GB; Wav2Lip termina y libera (0 MB en reposo).
- **Nivel**: `normal` en todas las lecturas; CPU 36–54 % durante animación.
- **Tiempo total del flujo**: ~12 min (voz SAPI + 38 frames LivePortrait
  + lip-sync 5 s + editor). Con driving de 2.5 s (58 frames) ≈ 18 min;
  con 3.1 s (78) ≈ 25 min. Recorta el driving para iterar rápido.
- **MP4 final**: `exports/anuncio_1794251176.mp4` — H.264 720×1280 24 fps +
  AAC 48 kHz, 5.0 s, 458 KB (ffprobe).

## Calidad (verificada)

- Voz SAPI 16 kHz clara; lip-sync Wav2Lip real; subtítulos quemados (drawtext);
  1080×1920 + trim verificados; editor con progreso real por tiempo.

## Límites honestos

- LivePortrait en CPU con 2 hilos: ~24 s/frame. `source_max_dim` no baja de
  512 para no degradar la cara; el editor queda en 720×1280 por defecto.
- No se tocó la paginación (automática) ni servicios esenciales de Windows.
- Sin límites artificiales de RAM: si la presión persiste tras 10 min, el
  trabajo continúa con advertencia (nunca se finaliza el proceso).
