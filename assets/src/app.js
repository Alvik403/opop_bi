import "./app.css";

function initSortableTables() {
  const parseNumber = (text) => {
    const normalized = String(text || "")
      .replace(/\s+/g, "")
      .replace(/%/g, "")
      .replace(/,/g, ".")
      .replace(/[^0-9.\-]/g, "");
    const value = Number.parseFloat(normalized);
    return Number.isFinite(value) ? value : 0;
  };

  const compare = (a, b, type) => {
    if (type === "number") return parseNumber(a) - parseNumber(b);
    return String(a || "").localeCompare(String(b || ""), "ru");
  };

  document.querySelectorAll("table.sortable-table").forEach((table) => {
    const headers = Array.from(table.querySelectorAll("thead th.sortable"));
    const tbody = table.querySelector("tbody");
    if (!tbody || !headers.length) return;

    headers.forEach((th, index) => {
      th.dataset.sortDir = "none";
      th.addEventListener("click", () => {
        const rows = Array.from(tbody.querySelectorAll("tr"));
        if (!rows.length) return;
        if (rows.some((row) => row.querySelector("td[colspan]"))) return;

        const nextDir = th.dataset.sortDir === "asc" ? "desc" : "asc";
        headers.forEach((item) => {
          item.dataset.sortDir = "none";
        });
        th.dataset.sortDir = nextDir;

        const type = th.dataset.sortType || "text";
        rows.sort((rowA, rowB) => {
          const a = rowA.children[index]?.innerText?.trim() || "";
          const b = rowB.children[index]?.innerText?.trim() || "";
          const base = compare(a, b, type);
          return nextDir === "asc" ? base : -base;
        });
        rows.forEach((row) => tbody.appendChild(row));
      });
    });
  });
}

function initFileMenu() {
  const root = document.querySelector("[data-file-menu]");
  if (!root) return;

  const toggle = root.querySelector("[data-file-menu-toggle]");
  const panel = root.querySelector("[data-file-menu-panel]");
  const uploadForm = root.querySelector("[data-file-upload-form]");
  const uploadStatus = root.querySelector("[data-file-upload-status]");

  const showStatus = (message, isError = false) => {
    if (!uploadStatus) return;
    uploadStatus.textContent = message || "";
    uploadStatus.className = `mt-2 text-xs ${isError ? "text-red-600" : "text-gray-500"}`;
  };

  toggle?.addEventListener("click", () => {
    panel?.classList.toggle("hidden");
  });

  document.addEventListener("click", (event) => {
    if (!panel || !toggle) return;
    if (root.contains(event.target)) return;
    panel.classList.add("hidden");
  });

  root.querySelectorAll("[data-file-select]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const response = await fetch(`/api/session/active-file/${button.dataset.fileSelect}`, {
          method: "POST",
        });
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось выбрать файл");
        }
        window.location.reload();
      } catch (error) {
        showStatus(error.message, true);
        button.disabled = false;
      }
    });
  });

  uploadForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fileInput = uploadForm.querySelector('input[type="file"]');
    if (!fileInput?.files?.length) {
      showStatus("Выберите .xlsx файл", true);
      return;
    }

    const formData = new FormData(uploadForm);
    showStatus("Проверяем структуру файла...");
    try {
      const response = await fetch("/api/files/upload", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Файл не прошёл проверку");
      }
      showStatus("Файл загружен. Обновляем дашборд...");
      window.location.reload();
    } catch (error) {
      showStatus(error.message, true);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initSortableTables();
  initFileMenu();
});
