// MeetingTool's page. Every change goes to the server as JSON (or a raw
// upload) with the X-MeetingTool header; what comes back is placed with
// textContent, never as HTML. Every text it shows is an entry of the list of
// messages, in the application's language: the page brings them in the
// data-texts attribute of its body (meetingtool/app/pages.py).
"use strict";

const HEADERS = { "X-MeetingTool": "1" };
let TEXTS = {};

function text(key, values) {
  let said = Object.prototype.hasOwnProperty.call(TEXTS, key) ? TEXTS[key] : key;
  for (const [name, value] of Object.entries(values || {})) said = said.split("{" + name + "}").join(String(value));
  return said;
}

function money(value) {
  const fixed = Number(value || 0).toFixed(3);
  return "US$" + (document.documentElement.lang === "es" ? fixed.replace(".", ",") : fixed);
}

function say(form, message, bad) {
  const place = form.querySelector(".message");
  if (place) {
    place.textContent = message;
    place.classList.toggle("bad", Boolean(bad));
  }
}

// What failed, with what came from outside the program as its detail.
function failure(answer, fallback) {
  const details = Array.isArray(answer.detail) ? answer.detail : [];
  return [answer.error || text(fallback)].concat(details.map((detail) => text("js.detail", { detail: detail })))
    .join(" — ");
}

async function send(path, data) {
  const response = await fetch(path, {
    method: "POST",
    headers: Object.assign({ "Content-Type": "application/json" }, HEADERS),
    body: JSON.stringify(data || {}),
    credentials: "same-origin",
  });
  const answer = await response.json().catch(() => ({ error: text("js.unreadable") }));
  if (!response.ok) throw new Error(failure(answer, "js.failed"));
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
      try { answer = JSON.parse(request.responseText); } catch (error) { answer = { error: text("js.unreadable") }; }
      if (request.status >= 200 && request.status < 300) resolve(answer);
      else reject(new Error(failure(answer, "js.upload_failed")));
    };
    request.onerror = () => reject(new Error(text("js.connection_lost")));
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
      say(form, text("js.wait"));
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
        say(holder, text("js.opening"));
      } catch (error) {
        say(holder, error.message, true);
      }
    });
  }
}

// A file of the settings (the Word template, the logo), sent to its own address.
function settingForm(id, field, address, choose, checking) {
  const form = document.getElementById(id);
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = form.elements[field].files[0];
    if (!file) return say(form, text(choose), true);
    say(form, text(checking));
    try {
      await upload(address + "?name=" + encodeURIComponent(file.name), file);
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
    if (!transcript) return say(form, text("js.missing_transcript"), true);
    if (data.format === "summary" && !recording) return say(form, text("js.summary_needs_video"), true);
    button.disabled = true;
    try {
      say(form, text("js.uploading_transcript"));
      data.transcript = (await upload("/api/upload?kind=transcript&name=" + encodeURIComponent(transcript.name),
        transcript)).upload;
      if (recording) {
        data.recording = (await upload("/api/upload?kind=recording&name=" + encodeURIComponent(recording.name),
          recording, (percent) => say(form, text("js.uploading_video", { percent: percent })))).upload;
      }
      say(form, text("js.starting"));
      const answer = await send("/api/process", data);
      window.location.href = "/job/" + encodeURIComponent(answer.job);
    } catch (error) {
      say(form, error.message, true);
      button.disabled = false;
    }
  });
}

function cell(row, value) {
  const td = document.createElement("td");
  td.textContent = value;
  row.appendChild(td);
}

const STATES = { pending: "js.state.pending", running: "js.state.running", done: "js.state.done",
  skipped: "js.state.skipped", failed: "js.state.failed" };

function drawJob(place, job) {
  place.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = job.title;
  place.appendChild(title);
  const table = document.createElement("table");
  table.className = "list";
  const head = document.createElement("tr");
  for (const key of ["js.col.stage", "js.col.state", "js.col.time", "js.col.cost"]) {
    const th = document.createElement("th");
    th.textContent = text(key);
    head.appendChild(th);
  }
  table.appendChild(head);
  for (const stage of job.stages) {
    const row = document.createElement("tr");
    row.className = "stage " + stage.state;
    cell(row, stage.label);
    cell(row, Object.prototype.hasOwnProperty.call(STATES, stage.state) ? text(STATES[stage.state]) : stage.state);
    cell(row, stage.state === "pending" || stage.state === "skipped" ? "" : Math.round(stage.seconds) + " s");
    cell(row, stage.state === "pending" || stage.state === "skipped" ? "" : money(stage.cost_usd));
    table.appendChild(row);
  }
  place.appendChild(table);
  const spent = document.createElement("p");
  spent.textContent = text("js.spent", { spent: money(job.spent_usd), ceiling: money(job.max_cost_usd),
    seconds: Math.round(job.seconds) });
  place.appendChild(spent);
  if (job.state === "done") {
    const done = document.createElement("p");
    const link = document.createElement("a");
    link.className = "button";
    link.href = "/p/" + encodeURIComponent(job.project) + "/m/" + encodeURIComponent(job.meeting);
    link.textContent = text("js.see_meeting");
    done.appendChild(link);
    place.appendChild(done);
  } else if (job.state === "failed") {
    const failed = document.createElement("p");
    failed.className = "bad";
    failed.textContent = text("js.failed_at", { stage: job.failed_stage, error: job.error });
    place.appendChild(failed);
    for (const detail of job.detail || []) {
      const said = document.createElement("p");
      said.className = "hint detail";
      said.textContent = text("js.detail", { detail: detail });
      place.appendChild(said);
    }
    const back = document.createElement("a");
    back.href = "/p/" + encodeURIComponent(job.project) + "/new";
    back.textContent = text("js.retry");
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
      place.textContent = text("js.connection_job");
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
    link.textContent = text("js.running", { title: answer.job.title });
    banner.replaceChildren(link);
    banner.hidden = false;
  } catch (error) {
    // no banner
  }
}

document.addEventListener("DOMContentLoaded", () => {
  try { TEXTS = JSON.parse(document.body.dataset.texts || "{}"); } catch (error) { TEXTS = {}; }
  apiForms();
  openButtons();
  settingForm("template", "template", "/api/template", "js.choose_template", "js.checking_template");
  settingForm("logo", "logo", "/api/logo", "js.choose_logo", "js.checking_logo");
  processForm();
  jobPage();
  runningBanner();
});
