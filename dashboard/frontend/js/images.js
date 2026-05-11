import { setStatus } from "./ui.js";
import { fetchJSON, invalidateRuns } from "./api.js";

export function buildImageGallery(run) {
  if (!run.image_files || !run.image_files.length) return null;

  const gal = document.createElement("div");
  gal.className = "image-gallery";

  const galHeader = document.createElement("div");
  galHeader.className = "gallery-header";
  galHeader.innerHTML = `<strong>Generated Images (${run.image_files.length})</strong>`;
  gal.appendChild(galHeader);

  const allCount = run.image_files.length;
  const ar45 = run.image_files.filter((f) => f.includes("/GEMINI_4_5/")).length;
  const ar916 = run.image_files.filter((f) => f.includes("/GEMINI_9_16/")).length;

  if (ar45 > 0 && ar916 > 0) {
    const filterBar = document.createElement("div");
    filterBar.className = "gallery-filters";
    [{ label: `All (${allCount})`, value: "" }, { label: `4:5 (${ar45})`, value: "GEMINI_4_5" }, { label: `9:16 (${ar916})`, value: "GEMINI_9_16" }].forEach((f) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `gallery-filter ${f.value === "" ? "active" : ""}`;
      btn.textContent = f.label;
      btn.dataset.filter = f.value;
      btn.onclick = () => {
        filterBar.querySelectorAll(".gallery-filter").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        gal.querySelectorAll(".image-card").forEach((c) => {
          c.style.display = !f.value || c.dataset.aspect === f.value ? "" : "none";
        });
      };
      filterBar.appendChild(btn);
    });
    gal.appendChild(filterBar);
  }

  const grid = document.createElement("div");
  grid.className = "image-grid";

  run.image_files.forEach((path) => {
    const card = document.createElement("div");
    card.className = "image-card";

    const is916 = path.includes("/GEMINI_9_16/");
    const arLabel = is916 ? "9:16" : "4:5";
    card.dataset.aspect = is916 ? "GEMINI_9_16" : "GEMINI_4_5";
    card.dataset.aspectLabel = arLabel;

    const cleanPath = path.replace(/^generated_images\//, "");
    const url = `/generated_images/${cleanPath}`;

    const imgWrap = document.createElement("div");
    imgWrap.className = "image-wrap";

    const img = document.createElement("img");
    img.className = "gallery-thumb";
    img.loading = "lazy";
    img.src = url;
    img.alt = path.split("/").pop() || "generated image";
    img.title = arLabel;
    imgWrap.appendChild(img);

    const imgDeleteBtn = document.createElement("button");
    imgDeleteBtn.type = "button";
    imgDeleteBtn.className = "image-delete-btn";
    imgDeleteBtn.textContent = "\u2715";
    imgDeleteBtn.title = "Delete this image";
    imgWrap.appendChild(imgDeleteBtn);

    const imgDlBtn = document.createElement("button");
    imgDlBtn.type = "button";
    imgDlBtn.className = "image-download-btn";
    imgDlBtn.textContent = "\u2B07";
    imgDlBtn.title = "Download image with metadata";
    imgWrap.appendChild(imgDlBtn);

    const badge = document.createElement("span");
    badge.className = `aspect-badge ${is916 ? "ar-916" : "ar-45"}`;
    badge.textContent = arLabel;
    card.appendChild(badge);
    card.appendChild(imgWrap);

    const fname = document.createElement("div");
    fname.className = "image-filename";
    fname.textContent = path.split("/").pop() || path;
    card.appendChild(fname);

    card.addEventListener("click", (event) => {
      if (event.target.closest(".image-delete-btn")) return;
      window.open(url, "_blank");
    });

    imgDeleteBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!confirm(`Delete image "${path.split("/").pop()}"?`)) return;
      imgDeleteBtn.disabled = true;
      try {
        await fetchJSON(`/api/runs/${run.run_id}/delete-image`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_file: path }),
        });
        setStatus(`Deleted image: ${path.split("/").pop()}`);
        card.remove();
        invalidateRuns();
      } catch (err) {
        setStatus(`Delete error: ${String(err)}`);
        imgDeleteBtn.disabled = false;
      }
    });

    imgDlBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      const dlUrl = `/api/runs/${run.run_id}/download-image?image_file=${encodeURIComponent(path)}`;
      const a = document.createElement("a");
      a.href = dlUrl;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      a.remove();
    });

    grid.appendChild(card);
  });

  gal.appendChild(grid);
  return gal;
}
