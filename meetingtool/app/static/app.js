// MeetingTool's page. Every change goes to the server as JSON (or a raw
// upload) with the X-MeetingTool header; what comes back is placed with
// textContent, never as HTML.
"use strict";

const HEADERS = { "X-MeetingTool": "1" };

function money(value) {
  return "US$" + Number(value || 0).toFixed(3).replace(".", ",");
}

function say(form, text, bad) {
  const place = form.querySelector(".message");
  if (place) {
    place.textContent = text;
    place.classList.toggle("bad", Boolean(bad));
  }
}

async function send(path, data) {
  const response = await fetch(path, {
    method: "POST",
    headers: Object.assign({ "Content-Type": "application/json" }, HEADERS),
    body: JSON.stringify(data || {}),
    credentials: "same-origin",
  });
  const answer = await response.json().catch(() => ({ error: "la respuesta no se pudo leer" }));
  if (!response.ok) throw new Error(answer.error || "no se pudo");
  return answer;
}

function upload(path, file, progress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", path);
    request.setRequestHeader("X-MeetingTool", "1");
    request.setRequestHeader("Content-Type", "application/octet-stream");
    request.upload.onprogress = (event) => {
      if (event.lengthComputable && progress) progress(Math.round((100 * event.loaded) / event.total));
    };
    request.onload = () => {
      let answer = {};
      try { answer = JSON.parse(request.responseText); } catch (error) { answer = { error: "la respuesta no se pudo leer" }; }
      if (request.status >= 200 && request.status < 300) resolve(answer);
      else reject(new Error(answer.error || "no se pudo subir"));
    };
    request.onerror = () => reject(new Error("se cortó la conexión con MeetingTool"));
    request.send(file);
  });
}

function fields(form) {
  const data = {};
  for (const element of form.elements) {
    if (!element.name || element.type === "file") continue;
    if (element.type === "radio" && !element.checked) continue;
    data[element.name] = element.value;
  }
  return data;
}

function apiForms() {
  for (const form of document.querySelectorAll("form[data-api]")) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) return;
      say(form, "Un momento…");
      try {
        const answer = await send(form.dataset.api, fields(form));
        if (form.dataset.then === "project") window.location.href = "/p/" + encodeURIComponent(answer.id);
        else window.location.reload();
      } catch (error) {
        say(form, error.message, true);
      }
    });
  }
}

function openButtons() {
  for (const button of document.querySelectorAll("button[data-open]")) {
    button.addEventListener("click", async () => {
      const holder = button.parentElement;
      try {
        await send("/api/open", { target: button.dataset.open });
        say(holder, "Abriendo el Word…");
      } catch (error) {
        say(holder, error.message, true);
      }
    });
  }
}

function templateForm() {
  const form = document.getElementById("template");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = form.elements.template.files[0];
    if (!file) return say(form, "Elegí la plantilla.", true);
    say(form, "Revisando la plantilla…");
    try {
      await upload("/api/template?name=" + encodeURIComponent(file.name), file);
      window.location.reload();
    } catch (error) {
      say(form, error.message, true);
    }
  });
}

function processForm() {
  const form = document.getElementById("process");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    const data = fields(form);
    data.project = form.dataset.project;
    data.max_cost = Number(data.max_cost);
    const transcript = form.elements.transcript.files[0];
    const recording = form.elements.recording.files[0];
    if (!transcript) return say(form, "Falta la transcripción.", true);
    if (data.format === "summary" && !recording) {
      return say(form, "El resumen necesita el video. Sin video, elegí preguntas y respuestas.", true);
    }
    button.disabled = true;
    try {
      say(form, "Subiendo la transcripción…");
      data.transcript = (await upload("/api/upload?kind=transcript&name=" + encodeURIComponent(transcript.name),
        transcript)).upload;
      if (recording) {
        data.recording = (await upload("/api/upload?kind=recording&name=" + encodeURIComponent(recording.name),
          recording, (percent) => say(form, "Subiendo el video… " + percent + " %"))).upload;
      }
      say(form, "Empezando…");
      const answer = await send("/api/process", data);
      window.location.href = "/job/" + encodeURIComponent(answer.job);
    } catch (error) {
      say(form, error.message, true);
      button.disabled = false;
    }
  });
}

function cell(row, text) {
  const td = document.createElement("td");
  td.textContent = text;
  row.appendChild(td);
}

const STATES = { pending: "en espera", running: "en curso…", done: "listo", skipped: "no hace falta", failed: "falló" };

function drawJob(place, job) {
  place.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = job.title;
  place.appendChild(title);
  const table = document.createElement("table");
  table.className = "list";
  const head = document.createElement("tr");
  for (const name of ["Etapa", "Estado", "Tiempo", "Costo"]) {
    const th = document.createElement("th");
    th.textContent = name;
    head.appendChild(th);
  }
  table.appendChild(head);
  for (const stage of job.stages) {
    const row = document.createElement("tr");
    row.className = "stage " + stage.state;
    cell(row, stage.label);
    cell(row, STATES[stage.state] || stage.state);
    cell(row, stage.state === "pending" || stage.state === "skipped" ? "" : Math.round(stage.seconds) + " s");
    cell(row, stage.state === "pending" || stage.state === "skipped" ? "" : money(stage.cost_usd));
    table.appendChild(row);
  }
  place.appendChild(table);
  const spent = document.createElement("p");
  spent.textContent = "Gastado: " + money(job.spent_usd) + " de un techo de " + money(job.max_cost_usd) +
    " · " + Math.round(job.seconds) + " s";
  place.appendChild(spent);
  if (job.state === "done") {
    const done = document.createElement("p");
    const link = document.createElement("a");
    link.className = "button";
    link.href = "/p/" + encodeURIComponent(job.project) + "/m/" + encodeURIComponent(job.meeting);
    link.textContent = "Ver la reunión";
    done.appendChild(link);
    place.appendChild(done);
  } else if (job.state === "failed") {
    const failed = document.createElement("p");
    failed.className = "bad";
    failed.textContent = "Falló en «" + job.failed_stage + "»: " + job.error +
      ". La reunión no se agregó al proyecto y no quedó nada a medias.";
    place.appendChild(failed);
    const back = document.createElement("a");
    back.href = "/p/" + encodeURIComponent(job.project) + "/new";
    back.textContent = "Volver a intentar";
    place.appendChild(back);
  }
}

function jobPage() {
  const place = document.getElementById("job");
  if (!place) return;
  const poll = async () => {
    try {
      const response = await fetch("/api/jobs/" + encodeURIComponent(place.dataset.job), { credentials: "same-origin" });
      const job = await response.json();
      drawJob(place, job);
      if (job.state === "running") setTimeout(poll, 1000);
    } catch (error) {
      place.textContent = "Se cortó la conexión con MeetingTool: fijate que su ventana siga abierta.";
    }
  };
  poll();
}

async function runningBanner() {
  const banner = document.getElementById("running");
  if (!banner || document.getElementById("job")) return;
  try {
    const response = await fetch("/api/running", { credentials: "same-origin" });
    const answer = await response.json();
    if (!answer.job) return;
    const link = document.createElement("a");
    link.href = "/job/" + encodeURIComponent(answer.job.id);
    link.textContent = "Se está procesando «" + answer.job.title + "»: ver el avance";
    banner.replaceChildren(link);
    banner.hidden = false;
  } catch (error) {
    // no banner
  }
}

document.addEventListener("DOMContentLoaded", () => {
  apiForms();
  openButtons();
  templateForm();
  processForm();
  jobPage();
  runningBanner();
});
