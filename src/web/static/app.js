/* Painel Admin — polling, upload, sync e SPED estruturado. */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const fmt = (n) => n.toLocaleString("pt-BR");
  let uploads = [];

  async function health() {
    try {
      const r = await fetch("/api/migracao/health");
      const d = await r.json();
      const el = $("#health");
      el.textContent = d.status === "ok" ? "🟢 DB OK" : "🔴 " + (d.detalhe || "erro");
      el.className = "badge " + (d.status === "ok" ? "ok" : "bad");
    } catch { $("#health").textContent = "🔴 API offline"; }
  }

  async function syncStatus() {
    try {
      const r = await fetch("/api/migracao/sync/status");
      if (!r.ok) { $("#sync-resumo").textContent = "auth necessária"; return; }
      const d = await r.json();
      $("#sync-resumo").textContent =
        `⏳ Pendentes: ${fmt(d.pendentes)} · ` +
        `🕐 Agendados: ${fmt(d.agendados)} · ` +
        `⚠️ Com erro: ${fmt(d.com_erro)} · ` +
        `✅ Últimas 24h: ${fmt(d.sincronizados_24h)} · ` +
        `💀 DLQ: ${fmt(d.dlq_total)}`;
    } catch { $("#sync-resumo").textContent = "erro"; }
  }

  async function testarFortes() {
    const form = $("#fortes-form");
    const data = Object.fromEntries(new FormData(form).entries());
    data.porta = parseInt(data.porta, 10);
    delete data.etapas;
    const r = await fetch("/api/migracao/fortes/testar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!r.ok) { alert("Auth ou erro: " + (await r.text())); return; }
    const d = await r.json();
    alert(d.ok ? "✅ Conexão OK" : "❌ Falha (ver migracao_erros.log)");
  }

  async function iniciarFortes(e) {
    e.preventDefault();
    const form = $("#fortes-form");
    const data = Object.fromEntries(new FormData(form).entries());
    data.porta = parseInt(data.porta, 10);
    data.etapas = [...form.querySelectorAll("input[name=etapas]:checked")]
      .map((i) => i.value);
    if (!data.etapas.length) { alert("Selecione ao menos uma etapa"); return; }
    const r = await fetch("/api/migracao/fortes/iniciar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!r.ok) { alert("Erro: " + (await r.text())); return; }
    acompanhar((await r.json()).job_id);
  }

  function renderUploads() {
    const ul = $("#lista-arquivos");
    ul.innerHTML = "";
    uploads.forEach((u) => {
      const li = document.createElement("li");
      li.textContent = u.nome;
      ul.appendChild(li);
    });
    $("#arq-iniciar").disabled = uploads.length === 0;
    $("#arq-estruturar").disabled = uploads.length === 0;
  }

  async function enviarArquivos(files) {
    const empresaId = $("#empresa-id-arq").value.trim();
    if (!empresaId) { alert("Preencha Empresa ID antes"); return; }
    const fd = new FormData();
    for (const f of files) fd.append("arquivos", f);
    const r = await fetch(
      `/api/migracao/arquivos/upload?empresa_id=${encodeURIComponent(empresaId)}`,
      { method: "POST", body: fd },
    );
    if (!r.ok) { alert("Erro upload: " + (await r.text())); return; }
    const d = await r.json();
    d.arquivos.forEach((p, i) => uploads.push({ caminho: p, nome: files[i].name }));
    renderUploads();
  }

  async function iniciarArquivos() {
    const empresaId = $("#empresa-id-arq").value.trim();
    const caminhos = uploads.map((u) => u.caminho);
    const r = await fetch(
      `/api/migracao/arquivos/iniciar?empresa_id=${encodeURIComponent(empresaId)}`,
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(caminhos) },
    );
    if (!r.ok) { alert("Erro: " + (await r.text())); return; }
    acompanhar((await r.json()).job_id);
  }

  async function iniciarSpedEstruturado() {
    const empresaId = $("#empresa-id-arq").value.trim();
    const caminhos = uploads.map((u) => u.caminho);
    const r = await fetch("/api/migracao/arquivos/estruturado", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ empresa_id: empresaId, caminhos }),
    });
    if (!r.ok) { alert("Erro: " + (await r.text())); return; }
    acompanhar((await r.json()).job_id);
  }

  function acompanhar(jobId) {
    $("#progresso-card").hidden = false;
    $("#job-id").textContent = jobId.slice(0, 8);
    const iv = setInterval(async () => {
      const r = await fetch(`/api/migracao/status/${jobId}`);
      if (!r.ok) { clearInterval(iv); return; }
      const d = await r.json();
      $("#progress-bar").style.width = d.percentual.toFixed(1) + "%";
      $("#progress-bar").textContent = d.percentual.toFixed(1) + "%";
      $("#etapa").textContent = d.etapa_atual || "—";
      $("#processados").textContent = fmt(d.registros_processados);
      $("#erros").textContent = fmt(d.registros_com_erro);
      $("#importados").textContent = fmt(d.importados);
      $("#erro").textContent = d.erro || "";
      if (["CONCLUIDO", "FALHOU", "CANCELADO"].includes(d.status)) {
        clearInterval(iv);
        $("#etapa").textContent = d.status === "CONCLUIDO"
          ? "✅ Concluído" : "❌ " + (d.erro || "falhou");
      }
    }, 1000);
  }

  // bindings
  $("#fortes-test").addEventListener("click", testarFortes);
  $("#fortes-form").addEventListener("submit", iniciarFortes);
  $("#arq-iniciar").addEventListener("click", iniciarArquivos);
  $("#arq-estruturar").addEventListener("click", iniciarSpedEstruturado);
  $("#arquivo-input").addEventListener("change", (e) => enviarArquivos(e.target.files));
  $("#dropzone").addEventListener("dragover", (e) => e.preventDefault());
  $("#dropzone").addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer?.files?.length) enviarArquivos(e.dataTransfer.files);
  });

  health(); syncStatus();
  setInterval(health, 30_000);
  setInterval(syncStatus, 15_000);
})();
