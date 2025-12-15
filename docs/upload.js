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
        uploadResult.textContent = "Pick a PDF first.";
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

        const data = JSON.parse(text);
        console.log("upload response", data);

        // show a message
        uploadResult.textContent = "Upload complete. Downloading Word doc...";

        // trigger download
       const url = API_BASE + data.download_url;

        const r2 = await fetch(url, {
        method: "GET",
        headers: { "Authorization": "Bearer " + token },
        });

        if (!r2.ok) {
        const errText = await r2.text();
        uploadResult.textContent = "Download failed:\n" + errText;
        return;
        }

        const blob = await r2.blob();
        const blobUrl = URL.createObjectURL(blob);

        const filename =
        (data.generated_doc && data.generated_doc.filename) ? data.generated_doc.filename : "output.docx";

        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();

        URL.revokeObjectURL(blobUrl);
        uploadResult.textContent = "Downloaded " + filename;
    };
};
