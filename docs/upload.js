import { getSessionToken } from "./auth.js";

let fileInput, uploadBtn, uploadResult;

export function initUpload(apiBase) {
  fileInput = document.getElementById("fileInput");
  uploadBtn = document.getElementById("uploadBtn");
  uploadResult = document.getElementById("uploadResult");

  uploadBtn.onclick = async () => {
    const token = getSessionToken();
    if (!token) {
      uploadResult.textContent = "Please sign in first.";
      return;
    }

    const f = fileInput.files && fileInput.files[0];
    if (!f) {
      uploadResult.textContent = "Pick a file first.";
      return;
    }

    const form = new FormData();
    form.append("file", f);

    const r = await fetch(apiBase + "/api/upload", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token },
      body: form,
    });

    const text = await r.text();
    if (!r.ok) {
      uploadResult.textContent = "Upload failed:\n" + text;
      return;
    }

    uploadResult.textContent = text;
  };
}
