const $ = (s) => document.querySelector(s);
// Modo cloud: si existe window.STUDIO_API_BASE, el dashboard habla con la API remota
// (Bearer = token guardado). Sin él, modo local contra el mismo servidor.
const API_BASE = window.STUDIO_API_BASE || "";
const TOKEN = () => localStorage.getItem("studio_cloud_token") || "";
async function api(url, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const t = TOKEN();
  if (t && !opts.noAuth) headers["Authorization"] = `Bearer ${t}`;
  const r = await fetch(API_BASE + url, { ...opts, headers });
  if (!r.ok) { const txt = await r.text().catch(() => r.statusText); throw new Error(`${r.status} · ${txt.slice(0, 400)}`); }
  return r.json();
}
const assetUrl = (path) => {
  const t = TOKEN();
  const base = API_BASE ? `${API_BASE}/api/cloud/files/${encodeURIComponent(path)}` : path;
  if (t && API_BASE) return `${base}?token=${encodeURIComponent(t)}`;
  return base;
};
{
  const b = document.querySelector("#cloudBase"), tk = document.querySelector("#cloudToken");
  if (b && tk) {
    b.value = localStorage.getItem("studio_api_base") || "";
    tk.value = localStorage.getItem("studio_cloud_token") || "";
    document.querySelector("#btnSaveCloud").addEventListener("click", () => {
      localStorage.setItem("studio_api_base", b.value.trim());
      localStorage.setItem("studio_cloud_token", tk.value.trim());
      location.reload();
    });
  }
}
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---------- navegación ----------
document.querySelectorAll("#nav button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#nav button").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + b.dataset.view));
  if (b.dataset.view === "projects") refreshProjects();
  if (b.dataset.view === "influencers") refreshInfluencers();
  if (b.dataset.view === "dashboard") refreshDashboard();
}));

// ---------- dashboard ----------
async function refreshDashboard() {
  try {
    const [projects, influencers, jobs, engines, health] = await Promise.all([
      api("/api/projects"), api("/api/influencers"), api("/api/jobs?limit=30"), api("/api/engines"), api("/api/health").catch(() => ({})),
    ]);
    $("#statProjects").textContent = projects.length;
    $("#statVideos").textContent = projects.filter((p) => p.final_path).length;
    $("#statPending").textContent = jobs.filter((j) => ["queued", "running"].includes(j.status)).length;
    $("#statInfluencers").textContent = influencers.length;
    $("#healthLine").textContent = health.status ? `· backend ${health.status}` : "";
    const lp = engines.liveportrait, w = engines.wav2lip, f = engines.fish_audio;
    $("#enginePill").textContent = `LP ${lp.available ? "✓" : "✗"} · Fish ${f.ok ? "✓" : "✗"} · W2L ${w.available ? "✓" : "pendiente"}`;
    $("#engineCards").innerHTML = [
      ["LivePortrait (CPU)", lp.available, lp.message],
      ["Fish Audio", f.ok, f.message || (f.configured ? "Configurado" : "Sin configurar")],
      ["Wav2Lip", w.available, w.message],
      ["FFmpeg", engines.ffmpeg.available, engines.ffmpeg.available ? "Listo" : "No encontrado"],
    ].map(([n, ok, m]) => `<div class="card ${ok ? "ok" : "warn"}"><b>${n}</b><div class="lbl">${esc(m)}</div></div>`).join("");
    $("#recentProjects").innerHTML = projects.slice(0, 8).map((p) =>
      `<tr><td>${p.id}</td><td>${esc(p.name)}</td><td>${esc(p.product || "—")}</td><td>${esc(p.status)}</td><td>${p.final_path ? "✔" : "—"}</td></tr>`).join("") || "<tr><td colspan=5>Sin proyectos todavía.</td></tr>";
    $("#lipsyncStatus").innerHTML = `<b>Wav2Lip:</b> ${esc(w.message)}`;
    renderJobs(jobs.slice(0, 5), "#recentJobs");
  } catch (e) { $("#healthLine").textContent = "· error: " + e.message; }
}
function renderJobs(list, selector) {
  $(selector).innerHTML = list.map((j) => `
    <div class="job">
      <b>#${j.id} ${esc(j.kind)}</b> · <span class="status-${esc(j.status)}">${esc(j.status)}</span>
      · ${esc(j.step || "")}
      ${j.status === "running" || j.status === "queued" ? `<button data-cancel="${j.id}">Cancelar</button>` : ""}
      ${j.result_path ? `<br><video controls src="${assetUrl(encodeURIComponent(j.result_path))}" style="max-width:320px;margin-top:8px"></video>` : ""}
      <div class="bar"><i style="width:${j.progress ?? 0}%"></i></div>
      ${j.error ? `<div class="status-error">${esc(j.error)}</div>` : ""}
      <pre>${esc((j.log || "").slice(-1200))}</pre>
    </div>`).join("") || "<p class=muted>Sin trabajos todavía.</p>";
  $(selector).querySelectorAll("[data-cancel]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/api/jobs/${b.dataset.cancel}/cancel`, { method: "POST" }); refreshDashboard();
  }));
}

// ---------- influencers ----------
async function refreshInfluencers() {
  const list = await api("/api/influencers").catch(() => []);
  $("#influencersGrid").innerHTML = list.map((inf) => `
    <div class="tile"><img src="${assetUrl(encodeURIComponent(inf.photo_path))}" alt="">
      <b>${esc(inf.name)}</b><br><small class="muted">ID ${inf.id}</small>
      <button data-delinf="${inf.id}">Eliminar</button></div>`).join("") || "<p class=muted>Sube tu primer personaje.</p>";
  $("#influencersGrid").querySelectorAll("[data-delinf]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/api/influencers/${b.dataset.delinf}`, { method: "DELETE" }); refreshInfluencers();
  }));
}
$("#formInfluencer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(); fd.append("photo", $("#infPhoto").files[0]);
  const up = await api("/api/influencers/upload", { method: "POST", body: fd });
  await api("/api/influencers", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: $("#infName").value, photo_path: up.path }) });
  refreshInfluencers();
});

// ---------- scripts ----------
$("#formScript").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api("/api/scripts/generate", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product: $("#scriptProduct").value, campaign: $("#scriptCampaign").value, tone: $("#scriptTone").value }) });
  $("#scriptNote").textContent = r.nota || "";
  $("#scriptVariants").innerHTML = (r.variantes || []).map((v, i) => `
    <div class="variant"><b>${esc(v.titulo)}</b> <span class="meta">· ${v.duracion_segundos}s · LLM: ${v.used_llm ? "sí" : "no"}</span>
      <p><i>Hook:</i> ${esc(v.hook)}</p><p>${esc(v.guion)}</p><p><i>CTA:</i> ${esc(v.cta)}</p>
      <button data-use="${i}">Usar en proyecto…</button></div>`).join("");
  $("#scriptVariants").querySelectorAll("[data-use]").forEach((b) => b.addEventListener("click", async () => {
    const pid = prompt("ID del proyecto donde guardar este guion:");
    if (!pid) return;
    const v = r.variantes[Number(b.dataset.use)];
    await api(`/api/projects/${pid}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ script: v.guion, status: "script" }) });
    alert("Guion guardado en el proyecto " + pid);
  }));
});

// ---------- voice ----------
$("#btnFishTest").addEventListener("click", async () => {
  $("#fishStatus").textContent = "Probando…";
  const r = await api("/api/voice/test");
  $("#fishStatus").textContent = r.message + (r.status ? ` (HTTP ${r.status})` : "");
});
$("#btnFishVoices").addEventListener("click", async () => {
  const r = await api("/api/voice/list");
  $("#fishVoices").innerHTML = (r.voices || []).map((v) => `<li>${esc(v.title)} · <code>${esc(v.id)}</code></li>`).join("");
});
$("#voiceSpeed").addEventListener("input", (e) => ($("#voiceSpeedVal").textContent = e.target.value));
async function loadLocalVoices() {
  try {
    const r = await api("/api/voice/local/list");
    $("#voiceLocal").innerHTML = '<option value="">Automática (español)</option>' +
      (r.voices || []).map((v) => `<option value="${esc(v.id)}">${esc(v.name)} (${esc(v.culture)})</option>`).join("");
  } catch { /* voces locales opcionales */ }
}
loadLocalVoices();
$("#formVoice").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { text: $("#voiceText").value, reference_id: $("#voiceRef").value || null,
    format: $("#voiceFormat").value, speed: Number($("#voiceSpeed").value),
    provider: $("#voiceProvider").value, voice_name: $("#voiceLocal").value || null,
    project_id: $("#voiceProject").value ? Number($("#voiceProject").value) : null };
  const r = await api("/api/voice/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  $("#voiceResult").innerHTML = `<b>Audio generado ✔</b> <audio controls src="${assetUrl(encodeURIComponent(r.path))}"></audio><br><small class=muted>${esc(r.path)}</small>`;
});
$("#formLip").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api("/api/lipsync/run", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face_path: $("#lipFace").value, audio_path: $("#lipAudio").value,
      project_id: $("#lipProject").value ? Number($("#lipProject").value) : null }) });
  pollJob(r.job_id, "#lipJobs");
});
async function refreshMemory() {
  try {
    const m = await api("/api/system/memory");
    const lvl = m.level === "normal" ? "status-done" : m.level === "elevada" ? "status-cancelled" : "status-error";
    $("#memAlert").innerHTML = `RAM ${m.level} · ${m.free_gb} GB libres de ${m.total_gb} GB · CPU ${m.cpu_percent ?? "—"}% · ${esc(m.stage)}${m.eta_seconds ? ` · ETA ~${Math.round(m.eta_seconds)}s` : ""}`;
    $("#memAlert").className = `hint ${lvl}`;
    $("#memTable").innerHTML = [
      ["RAM total", `${m.total_gb} GB`],
      ["RAM usada", `${m.used_gb} GB (${m.load_percent}%)`],
      ["RAM disponible", `${m.free_gb} GB`],
      ["Python (backend)", `${m.python_mb} MB`],
      ["LivePortrait", `${m.liveportrait_mb} MB`],
      ["Wav2Lip", `${m.wav2lip_mb} MB`],
      ["CPU", `${m.cpu_percent ?? "—"}%`],
      ["Etapa actual", esc(m.stage)],
      ["Perfil", esc(m.profile)],
    ].map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
  } catch { /* monitor opcional */ }
}
$("#btnCleanup").addEventListener("click", async () => {
  const r = await api("/api/system/cleanup", { method: "POST" });
  $("#cleanupMsg").textContent = `Limpieza: ${r.archivos} archivos, ${r.carpetas} carpetas (${(r.bytes / 1024).toFixed(0)} KB).`;
});
setInterval(refreshMemory, 3000);
refreshMemory();

// ---------- animation ----------
$("#formAnimation").addEventListener("submit", async (e) => {
  e.preventDefault();
  let source = $("#animPhotoPath").value.trim(), driving = $("#animDrivingPath").value.trim();
  if ($("#animPhoto").files[0]) { const fd = new FormData(); fd.append("photo", $("#animPhoto").files[0]); source = (await api("/api/influencers/upload", { method: "POST", body: fd })).path; }
  if ($("#animDriving").files[0]) { const fd = new FormData(); fd.append("video", $("#animDriving").files[0]); driving = (await api("/api/upload/video", { method: "POST", body: fd })).path; }
  if (!source || !driving) return alert("Indica foto y vídeo de referencia (o rutas).");
  const r = await api("/api/animation/run", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_path: source, driving_path: driving, project_id: $("#animProject").value ? Number($("#animProject").value) : null }) });
  $("#animationJobs").innerHTML = `<p>Trabajo #${r.job_id} en cola. Sigue el progreso aquí:</p><div id="animJobs"></div>`;
  pollJob(r.job_id, "#animJobs");
});

// ---------- editor ----------
$("#formEditor").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api("/api/editor/render", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    visual_path: $("#edVisual").value, audio_path: $("#edAudio").value || null,
    music_path: $("#edMusic").value || null, subtitles_path: $("#edSubs").value || null,
    title: $("#edTitle").value, voice_volume: Number($("#edVoiceVol").value),
    music_volume: Number($("#edMusicVol").value), zoom: $("#edZoom").checked,
    resolution: $("#edRes").value, trim_start: Number($("#edTrimS").value) || 0,
    trim_end: $("#edTrimE").value ? Number($("#edTrimE").value) : null,
    project_id: $("#edProject").value ? Number($("#edProject").value) : null }) });
  pollJob(r.job_id, "#editorJobs");
});
$("#formPreview").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api("/api/editor/preview", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_path: $("#pvPhoto").value }) });
  pollJob(r.job_id, "#editorJobs");
});

// ---------- projects & flow ----------
async function refreshProjects() {
  const list = await api("/api/projects").catch(() => []);
  $("#projectsTable").innerHTML = list.map((p) => `
    <tr><td>${p.id}</td><td>${esc(p.name)}</td><td>${esc(p.product || "—")}</td><td>${esc(p.status)}</td>
    <td>${p.final_path ? `<a href="${assetUrl(encodeURIComponent(p.final_path))}" download>MP4</a> ` : ""}
    <button data-delproj="${p.id}">Eliminar</button></td></tr>`).join("") || "<tr><td colspan=5>Sin proyectos.</td></tr>";
  $("#projectsTable").querySelectorAll("[data-delproj]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/api/projects/${b.dataset.delproj}`, { method: "DELETE" }); refreshProjects();
  }));
}
$("#formProject").addEventListener("submit", async (e) => {
  e.preventDefault();
  await api("/api/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    name: $("#projName").value, product: $("#projProduct").value,
    influencer_id: $("#projInfluencer").value ? Number($("#projInfluencer").value) : null,
    script: $("#projScript").value, voice_id: $("#projVoice").value, status: "draft" }) });
  refreshProjects();
});
$("#formFlow").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api("/api/flow/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    project_id: Number($("#flowProject").value), influencer_photo: $("#flowPhoto").value,
    driving_video: $("#flowDriving").value, title: $("#flowTitle").value,
    use_lipsync: $("#flowLipsync").checked, audio_provider: $("#flowAudioProvider").value,
    resolution: $("#flowRes").value }) });
  pollJob(r.job_id, "#jobPanel");
});

// ---------- jobs polling (progreso real, sin % inventados) ----------
function pollJob(id, selector) {
  const tick = async () => {
    const j = await api(`/api/jobs/${id}`).catch(() => null);
    if (!j) return;
    $(selector).innerHTML = `<div class="job"><b>Trabajo #${j.id} ${esc(j.kind)}</b>
      · <span class="status-${esc(j.status)}">${esc(j.status)}</span> · ${esc(j.step || "")}
      ${["queued", "running"].includes(j.status) ? `<button id="cancelBtn">Cancelar</button>` : ""}
      <div class="bar"><i style="width:${j.progress ?? 0}%"></i></div>
      ${j.error ? `<div class="status-error">${esc(j.error)}</div>` : ""}
      ${j.result_path ? `<video controls src="${assetUrl(encodeURIComponent(j.result_path))}" style="max-width:360px"></video><br><a href="${assetUrl(encodeURIComponent(j.result_path))}" download>Descargar MP4</a>` : ""}
      <pre>${esc((j.log || "").slice(-1500))}</pre></div>`;
    const cb = $("#cancelBtn");
    if (cb) cb.addEventListener("click", async () => { await api(`/api/jobs/${id}/cancel`, { method: "POST" }); });
    if (["queued", "running"].includes(j.status)) setTimeout(tick, 1500);
  };
  tick();
}

refreshDashboard();
