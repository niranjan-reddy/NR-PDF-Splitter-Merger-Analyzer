"use strict";

const rows = document.querySelector("#merge-rows");
const count = document.querySelector("#file-count");
let rowSequence = 0;

function updateRows() {
  const children = Array.from(rows.children);
  children.forEach((row, index) => {
    row.querySelector("label").textContent = `PDF ${index + 1}`;
    row.querySelector(".up").disabled = index === 0;
    row.querySelector(".down").disabled = index === children.length - 1;
  });
  count.value = children.length;
}

function addRow() {
  const row = document.createElement("div");
  row.className = "upload-row";
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "file";
  input.name = "files";
  input.accept = ".pdf,application/pdf";
  input.required = true;
  input.id = `upload-${++rowSequence}`;
  label.htmlFor = input.id;
  row.append(label, input);
  for (const [direction, text] of [["up", "Move up"], ["down", "Move down"]]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `secondary ${direction}`;
    button.textContent = text;
    button.addEventListener("click", () => {
      if (direction === "up" && row.previousElementSibling) {
        rows.insertBefore(row, row.previousElementSibling);
      } else if (direction === "down" && row.nextElementSibling) {
        rows.insertBefore(row.nextElementSibling, row);
      }
      updateRows();
    });
    row.append(button);
  }
  rows.append(row);
}

document.querySelector("#apply-count").addEventListener("click", () => {
  if (!count.reportValidity()) return;
  const desired = Number(count.value);
  while (rows.children.length < desired) addRow();
  while (rows.children.length > desired) rows.lastElementChild.remove();
  updateRows();
});
addRow();
addRow();
updateRows();

function downloadLink(file, label) {
  const link = document.createElement("a");
  link.href = file.url;
  link.textContent = label || file.name;
  link.download = file.name;
  link.className = "download";
  return link;
}

function showResults(container, data, operation) {
  if (operation === "analyze") {
    for (const [index, result] of data.analyses.entries()) {
      const section = document.createElement("section");
      section.className = "analysis-document";
      const heading = document.createElement("h3");
      heading.id = `analysis-document-${index + 1}`;
      heading.textContent = `${index + 1}. ${result.analysis ? result.analysis.filename : result.filename}`;
      section.setAttribute("aria-labelledby", heading.id);
      section.append(heading);
      if (result.error) {
        const error = document.createElement("p");
        error.className = "error";
        error.textContent = result.error;
        section.append(error);
      } else {
        showAnalysis(section, result.analysis);
      }
      container.append(section);
    }
    return;
  }
  const title = document.createElement("h3");
  title.textContent = operation === "split" ? "Your split files are ready" : "Your merged PDF is ready";
  container.append(title);
  if (operation === "split") {
    container.append(downloadLink(data.archive, "Download all files as ZIP"));
    for (const file of data.files) {
      const item = document.createElement("div");
      item.className = "result-item";
      item.append(downloadLink(file));
      const detail = document.createElement("small");
      detail.textContent = `${file.pages} page${file.pages === 1 ? "" : "s"}`;
      item.append(detail);
      container.append(item);
    }
  } else {
    container.append(downloadLink(data.file));
    const detail = document.createElement("p");
    detail.textContent = `${data.file.pages} pages, in your selected file order.`;
    container.append(detail);
  }
}

function showAnalysis(container, analysis) {
  const title = document.createElement("h3");
  title.textContent = "Document summary";
  container.append(title);
  const summary = document.createElement("dl");
  summary.className = "analysis-summary";
  for (const [label, value] of [
    ["Filename", analysis.filename],
    ["File size", `${analysis.size_bytes.toLocaleString()} bytes (${(analysis.size_bytes / 1048576).toFixed(2)} MiB)`],
    ["Encrypted", analysis.encrypted ? "Yes" : "No"],
    ["Page count", analysis.page_count === null ? "Unavailable (encrypted)" : analysis.page_count],
  ]) {
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value;
    summary.append(term, detail);
  }
  container.append(summary);
  if (analysis.encrypted) {
    const notice = document.createElement("p");
    notice.textContent = "Upload an unencrypted copy to inspect metadata and page dimensions.";
    container.append(notice);
    return;
  }
  const metadataTitle = document.createElement("h3");
  metadataTitle.textContent = "Document metadata";
  container.append(metadataTitle);
  const metadata = document.createElement("dl");
  metadata.className = "analysis-summary";
  const labels = {
    Title: "Title", Author: "Author", Subject: "Subject", Keywords: "Keywords",
    Creator: "Creator application", Producer: "PDF producer",
    CreationDate: "Created", ModDate: "Modified",
  };
  const properties = { ...analysis.document_properties };
  for (const [key, value] of Object.entries(analysis.metadata)) {
    if (!(key in properties)) properties[key] = value;
  }
  for (const [key, value] of Object.entries(properties)) {
    const term = document.createElement("dt");
    term.textContent = labels[key] || key;
    const detail = document.createElement("dd");
    detail.textContent = value || "Not provided";
    metadata.append(term, detail);
  }
  if (!metadata.children.length) {
    const empty = document.createElement("p");
    empty.textContent = "No document metadata available.";
    container.append(empty);
  } else {
    container.append(metadata);
  }
  const wrapper = document.createElement("div");
  wrapper.className = "analysis-table";
  wrapper.tabIndex = 0;
  const table = document.createElement("table");
  const caption = document.createElement("caption");
  caption.textContent = "Page dimensions: MediaBox, adjusted for rotation and UserUnit. 72 points = 1 inch; cropped visible areas may differ.";
  table.append(caption);
  const head = table.createTHead().insertRow();
  for (const text of ["Page", "Width (pt)", "Height (pt)", "Orientation", "Rotation"]) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = text;
    head.append(cell);
  }
  const body = table.createTBody();
  for (const page of analysis.pages) {
    const row = body.insertRow();
    for (const value of [page.number, page.width_points, page.height_points, page.orientation, `${page.rotation} degrees`]) {
      row.insertCell().textContent = value;
    }
  }
  wrapper.append(table);
  container.append(wrapper);
}

for (const operation of ["split", "merge", "analyze"]) {
  const form = document.querySelector(`#${operation}-form`);
  const results = document.querySelector(`#${operation}-results`);
  const error = form.querySelector(".error");
  const status = form.querySelector(".status");
  const fieldset = form.querySelector("fieldset");
  let cleanupUrl = null;
  let busy = false;

  function setBusy(value, message) {
    busy = value;
    fieldset.disabled = value;
    status.hidden = !value;
    form.querySelector(".status-text").textContent = message || "";
    form.setAttribute("aria-busy", String(value));
    if (!value && operation === "merge") updateRows();
  }

  function showError(failure) {
    error.textContent = failure instanceof TypeError
      ? "Could not reach the server. Check your connection and try again."
      : failure.message;
    error.hidden = false;
  }

  async function cleanupPreviousJob() {
    if (!cleanupUrl) return;
    const response = await fetch(cleanupUrl, { method: "DELETE" });
    if (!response.ok) {
      const data = (response.headers.get("content-type") || "").includes("application/json")
        ? await response.json() : {};
      throw new Error(data.error || `Could not clean up the previous job (${response.status}). Try again.`);
    }
    cleanupUrl = null;
  }

  form.querySelector(".reset").addEventListener("click", async () => {
    if (busy) return;
    error.hidden = true;
    setBusy(true, "Cleaning up the previous job...");
    try {
      await cleanupPreviousJob();
      form.reset();
      if (operation === "merge") {
        rows.replaceChildren();
        addRow();
        addRow();
      }
      results.replaceChildren();
      error.textContent = "";
    } catch (failure) {
      showError(failure);
    } finally {
      setBusy(false);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    const payload = new FormData(form);
    error.hidden = true;
    setBusy(true, "Uploading and processing PDFs. Please keep this page open...");
    try {
      await cleanupPreviousJob();
      results.replaceChildren();
      const response = await fetch(`/api/${operation}`, { method: "POST", body: payload });
      if (!(response.headers.get("content-type") || "").includes("application/json")) {
        throw new Error(`The server returned an unexpected response (${response.status}).`);
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The PDF operation failed.");
      cleanupUrl = data.cleanup_url;
      showResults(results, data, operation);
    } catch (failure) {
      showError(failure);
    } finally {
      setBusy(false);
    }
  });
}
