// document.addEventListener("DOMContentLoaded", () => {
//     const config = document.getElementById("schedule-config");

//     const listUrl = config.dataset.listUrl;
//     const createUrl = config.dataset.createUrl;
//     const locationsUrl = config.dataset.locationsUrl;

//     const scheduleList = document.getElementById("schedule-list");
//     const scheduleForm = document.getElementById("schedule-form");
//     const scheduleMessage = document.getElementById("schedule-message");
//     const locationSelect = document.getElementById("cod-location");

//     const csrfToken = scheduleForm.querySelector(
//         "[name=csrfmiddlewaretoken]"
//     ).value;

//     const updateUrlTemplate = config.dataset.updateUrl;
//     const deleteUrlTemplate = config.dataset.deleteUrl;

//     const submitButton = document.getElementById("schedule-submit-btn");
//     const cancelEditButton = document.getElementById("cancel-edit-btn");

//     const UUID_PLACEHOLDER =
//         "00000000-0000-0000-0000-000000000000";

//     let editingId = null;

//     function buildScheduleUrl(template, id) {
//         return template.replace(UUID_PLACEHOLDER, id);
//     }

//     // ==========================================
//     // 1. MENGAMBIL DAFTAR LOKASI COD
//     // ==========================================

//     async function loadLocations() {
//         try {
//             const response = await fetch(locationsUrl);

//             if (!response.ok) {
//                 throw new Error("Gagal mengambil lokasi COD.");
//             }

//             const data = await response.json();

//             locationSelect.innerHTML =
//                 '<option value="">Pilih lokasi COD</option>';

//             data.locations.forEach(location => {
//                 const option = document.createElement("option");

//                 option.value = location.id;
//                 option.textContent =
//                     `${location.name} - ${location.address}`;

//                 locationSelect.appendChild(option);
//             });

//         } catch (error) {
//             scheduleMessage.textContent = error.message;
//         }
//     }

//     // ==========================================
//     // 2. MENAMPILKAN JADWAL COD
//     // ==========================================

//     function editSchedule(schedule) {
//         editingId = schedule.id;

//         scheduleForm.elements.schedule_type.value =
//             schedule.schedule_type;

//         scheduleForm.elements.cod_location.value =
//             schedule.cod_location;

//         const date = new Date(schedule.scheduled_time);

//         // Konversi ke waktu lokal untuk input datetime-local
//         const localDate = new Date(
//             date.getTime() - date.getTimezoneOffset() * 60000
//         );

//         scheduleForm.elements.scheduled_time.value =
//             localDate.toISOString().slice(0, 16);

//         scheduleForm.elements.notes.value =
//             schedule.notes || "";

//         submitButton.textContent = "Simpan Perubahan";
//         cancelEditButton.hidden = false;

//         scheduleMessage.textContent = "Sedang mengedit jadwal COD.";

//         scheduleForm.scrollIntoView({
//             behavior: "smooth",
//             block: "start"
//         });
//     }

//     async function deleteSchedule(schedule) {
//         const confirmed = confirm(
//             `Hapus jadwal ${schedule.schedule_type_label}?`
//         );

//         if (!confirmed) return;

//         const url = buildScheduleUrl(
//             deleteUrlTemplate,
//             schedule.id
//         );

//         try {
//             const response = await fetch(url, {
//                 method: "POST",
//                 headers: {
//                     "X-CSRFToken": csrfToken
//                 }
//             });

//             const data = await response.json();

//             if (!response.ok) {
//                 throw new Error(
//                     data.message || "Gagal menghapus jadwal."
//                 );
//             }

//             if (editingId === schedule.id) {
//                 resetEditMode();
//             }

//             scheduleMessage.textContent =
//                 "Jadwal berhasil dihapus.";

//             await loadSchedules();

//         } catch (error) {
//             scheduleMessage.textContent = error.message;
//         }
//     }

//     async function loadSchedules() {
//         scheduleList.textContent = "Memuat jadwal COD...";

//         try {
//             const response = await fetch(listUrl);

//             if (!response.ok) {
//                 throw new Error("Gagal mengambil jadwal COD.");
//             }

//             const data = await response.json();

//             scheduleList.replaceChildren();

//             if (data.schedules.length === 0) {
//                 scheduleList.textContent =
//                     "Belum ada jadwal COD.";
//                 return;
//             }

//             data.schedules.forEach(schedule => {
//                 const card = document.createElement("div");
//                 card.className = "schedule-card";

//                 const title = document.createElement("h3");
//                 title.textContent = schedule.schedule_type_label;

//                 const location = document.createElement("p");
//                 location.textContent =
//                     `Lokasi: ${schedule.location_name}`;

//                 const time = document.createElement("p");
//                 time.textContent =
//                     `Waktu: ${new Date(
//                         schedule.scheduled_time
//                     ).toLocaleString("id-ID")}`;

//                 const notes = document.createElement("p");
//                 notes.textContent =
//                     `Catatan: ${schedule.notes || "-"}`;

//                 const actions = document.createElement("div");
//                 actions.className = "schedule-actions";

//                 const editButton = document.createElement("button");
//                 editButton.type = "button";
//                 editButton.textContent = "Edit";

//                 editButton.addEventListener("click", () => {
//                     editSchedule(schedule);
//                 });

//                 const deleteButton = document.createElement("button");
//                 deleteButton.type = "button";
//                 deleteButton.textContent = "Hapus";

//                 deleteButton.addEventListener("click", () => {
//                     deleteSchedule(schedule);
//                 });
                

//                 actions.append(editButton, deleteButton);

//                 card.append(title, location, time, notes, actions);
//                 scheduleList.appendChild(card);
//             });

//         } catch (error) {
//             scheduleList.textContent = error.message;
//         }
//     }

//     // ==========================================
//     // 3. MENYIMPAN JADWAL COD
//     // ==========================================

//     function resetEditMode() {
//         editingId = null;

//         scheduleForm.reset();

//         submitButton.textContent = "Simpan Jadwal";
//         cancelEditButton.hidden = true;
//     }

//     cancelEditButton.addEventListener("click", () => {
//         resetEditMode();
//         scheduleMessage.textContent = "";
//     });

//     scheduleForm.addEventListener("submit", async event => {
//         event.preventDefault();

//         const submitButton = scheduleForm.querySelector(
//             'button[type="submit"]'
//         );

//         submitButton.disabled = true;
//         scheduleMessage.textContent = "Menyimpan jadwal...";

//         try {
//             const url = editingId
//                 ? buildScheduleUrl(updateUrlTemplate, editingId)
//                 : createUrl;

//             const response = await fetch(url, {
//                 method: "POST",
//                 headers: {
//                     "X-CSRFToken": csrfToken
//                 },
//                 body: new FormData(scheduleForm)
//             });

//             const data = await response.json();

//             if (!response.ok) {
//                 const errors = data.errors
//                     ? Object.values(data.errors)
//                         .flat()
//                         .map(error => error.message)
//                         .join(" ")
//                     : data.message;

//                 throw new Error(
//                     errors || "Gagal menyimpan jadwal."
//                 );
//             }

//             scheduleMessage.textContent =
//                 "Jadwal COD berhasil disimpan.";

//             // scheduleForm.reset();
//             resetEditMode();

//             await loadSchedules();

//         } catch (error) {
//             scheduleMessage.textContent = error.message;
//         } finally {
//             submitButton.disabled = false;
//         }
//     });

//     // ==========================================
//     // 4. INISIALISASI
//     // ==========================================

//     loadLocations();
//     loadSchedules();
// });

/* Management Jadwal COD — Leaflet + MapLibre; data lokasi dari endpoint location_list.
   Tidak membutuhkan endpoint schedule_locations atau perubahan backend khusus. */
(() => {
  "use strict";

  const config = document.getElementById("schedule-config");
  if (!config) return;

  const form = document.getElementById("schedule-form");
  const scheduleList = document.getElementById("schedule-list");
  const scheduleCount = document.getElementById("schedule-count");
  const locationSelect = document.getElementById("cod-location");
  const scheduleType = document.getElementById("schedule-type");
  const scheduledTime = document.getElementById("scheduled-time");
  const locationLabel = document.getElementById("cod-location-label");
  const locationHint = document.getElementById("cod-location-hint");
  const notes = document.getElementById("schedule-notes");
  const submitButton = document.getElementById("schedule-submit-btn");
  const cancelEdit = document.getElementById("cancel-edit-btn");
  const formHeading = document.getElementById("schedule-form-heading");
  const message = document.getElementById("schedule-message");
  const selectedLocation = document.getElementById("selected-location");
  const canEdit = config.dataset.allowEdit === "true";
  const canDelete = config.dataset.allowDelete === "true";

  const csrfToken = form?.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";
  const locationsById = new Map();
  let schedules = [];
  let editId = null;
  let map = null;
  let markers = new Map();

  function asError(error) {
    if (!error) return "Terjadi kesalahan saat memproses permintaan.";
    if (typeof error === "string") return error;
    return error.message || "Terjadi kesalahan. Silakan coba lagi.";
  }

  function getErrorText(data, fallback) {
    if (data?.message) return data.message;
    if (data?.errors && typeof data.errors === "object") {
      const parts = [];
      for (const [field, problems] of Object.entries(data.errors)) {
        const messages = Array.isArray(problems) ? problems : [problems];
        const texts = messages.map((problem) =>
          (typeof problem === "string" ? problem : problem?.message) || "Input tidak valid"
        );
        parts.push(`${field}: ${texts.join(", ")}`);
      }
      if (parts.length) return parts.join(". ");
    }
    return fallback;
  }

  async function requestJSON(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: { Accept: "application/json", ...(options.headers || {}) },
    });
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error(response.redirected
        ? "Sesi login berakhir. Silakan login kembali."
        : `Server tidak mengirim JSON (HTTP ${response.status}).`);
    }
    const data = await response.json();
    if (!response.ok || data.success === false) {
      throw new Error(getErrorText(data, `Permintaan gagal (HTTP ${response.status}).`));
    }
    return data;
  }

  function report(text, type = "") {
    if (!message) return;
    message.textContent = text;
    message.className = `cod-schedule-message${type ? ` is-${type}` : ""}`;
  }

  function createText(tag, className, content) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = content == null ? "" : String(content);
    return element;
  }

  function localInputDate(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso).slice(0, 16);
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }

  function formatDateTime(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso);
    return new Intl.DateTimeFormat("id-ID", {
      day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
    }).format(date);
  }

  function setSelectedLocation(location) {
    if (!selectedLocation) return;
    selectedLocation.replaceChildren();
    if (!location) {
      selectedLocation.append(
        createText("strong", "", "Belum ada lokasi dipilih"),
        createText("span", "", "Pilih lokasi COD untuk melihat titik pertemuan.")
      );
      return;
    }
    selectedLocation.append(
      createText("strong", "", location.name),
      createText("span", "", location.address || "Alamat belum tersedia")
    );
  }

  function initMap() {
    const element = document.getElementById("schedule-map");
    if (!element) return;
    if (!window.L) {
      element.textContent = "Peta tidak dapat dimuat. Periksa koneksi Leaflet.";
      return;
    }
    map = L.map(element, { scrollWheelZoom: false }).setView([-6.3653, 106.8315], 13);
    if (typeof L.maplibreGL === "function") {
      L.maplibreGL({
        style: "https://tiles.openfreemap.org/styles/liberty",
        attribution: '&copy; <a href="https://openfreemap.org">OpenFreeMap</a>',
      }).addTo(map);
    } else {
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);
    }
    // Biarkan Leaflet mengukur ukuran peta setelah layout utama tampil.
    requestAnimationFrame(() => map.invalidateSize());
  }

  function refreshMapMarkers() {
    if (!map) return;
    for (const marker of markers.values()) marker.remove();
    markers = new Map();
    const coordinates = [];

    for (const [id, location] of locationsById) {
      const latitude = Number(location.latitude);
      const longitude = Number(location.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) continue;
      if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) continue;

      const marker = L.marker([latitude, longitude]).addTo(map);
      const popup = document.createElement("div");
      popup.append(
        createText("strong", "", location.name),
        document.createElement("br"),
        createText("span", "", location.address || "Alamat belum tersedia")
      );
      marker.bindPopup(popup);
      marker.on("click", () => {
        if (locationSelect) {
          locationSelect.value = id;
          locationSelect.dispatchEvent(new Event("change"));
        } else {
          focusLocation(id);
        }
      });
      markers.set(id, marker);
      coordinates.push([latitude, longitude]);
    }

    if (coordinates.length === 1) map.setView(coordinates[0], 15);
    else if (coordinates.length > 1) map.fitBounds(coordinates, { padding: [32, 32], maxZoom: 15 });
    if (locationSelect?.value && locationsById.has(locationSelect.value)) {
      focusLocation(locationSelect.value);
    }
  }

  function focusLocation(id) {
    const location = locationsById.get(String(id));
    setSelectedLocation(location);
    if (!map || !location) return;
    const lat = Number(location.latitude);
    const lng = Number(location.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    map.setView([lat, lng], 16, { animate: true });
    markers.get(String(id))?.openPopup();
  }

  function updateLocationField() {
    const isReturn = scheduleType.value === "return";

    locationLabel.textContent = isReturn
        ? "Lokasi Pengembalian"
        : "Lokasi Pengambilan";

    locationHint.textContent = isReturn
        ? "Pilih lokasi pengembalian barang. Lokasi boleh berbeda dari lokasi pengambilan."
        : "Pilih lokasi pengambilan barang.";

    // Kosongkan pilihan sebelumnya agar pengguna memilih lokasi
    // secara khusus untuk jenis jadwal yang baru.
    locationSelect.value = "";
    focusLocation("");
  }

scheduleType?.addEventListener("change", updateLocationField);

  async function loadLocations() {
    const data = await requestJSON(config.dataset.locationsUrl);
    const locationList = Array.isArray(data.locations) ? data.locations : [];
    locationsById.clear();
    for (const location of locationList) locationsById.set(String(location.id), location);

    if (locationSelect) {
      const previousValue = locationSelect.value;
      locationSelect.replaceChildren();
      locationSelect.appendChild(createText("option", "", "Pilih lokasi COD"));
      locationSelect.firstChild.value = "";
      for (const location of locationList) {
        const option = createText("option", "", `${location.name} — ${location.address || "Tanpa alamat"}`);
        option.value = String(location.id);
        locationSelect.appendChild(option);
      }
      if (locationsById.has(previousValue)) locationSelect.value = previousValue;
      if (!locationList.length) {
        locationSelect.firstChild.textContent = "Belum ada lokasi yang dapat dipilih";
        locationSelect.disabled = true;
        report("Belum ada lokasi COD. Buat lokasi melalui halaman peta COD terlebih dahulu.", "error");
      } else {
        locationSelect.disabled = false;
      }
    }
    refreshMapMarkers();
  }

  function renderSchedules() {
    if (!scheduleList) return;
    scheduleList.replaceChildren();
    if (scheduleCount) scheduleCount.textContent = `${schedules.length} jadwal`;
    if (!schedules.length) {
      scheduleList.appendChild(createText("p", "cod-schedule-muted", "Belum ada jadwal COD pada transaksi ini."));
      return;
    }

    for (const schedule of schedules) {
      const item = createText("article", "cod-schedule-item", "");
      const top = createText("div", "cod-schedule-item-top", "");
      const type = schedule.schedule_type === "pickup" ? "Pengambilan" : "Pengembalian";
      top.append(
        createText("strong", "cod-schedule-item-name", schedule.location_name || "Lokasi COD"),
        createText("span", "cod-schedule-item-type", type)
      );
      item.append(top);
      item.append(createText("p", "", `Waktu: ${formatDateTime(schedule.scheduled_time)}`));
      if (schedule.notes) item.append(createText("p", "", `Catatan: ${schedule.notes}`));

      const actions = createText("div", "cod-schedule-item-actions", "");
      const view = createText("button", "", "Lihat Lokasi");
      view.type = "button";
      view.addEventListener("click", () => {
        if (locationSelect && locationsById.has(String(schedule.cod_location))) {
          locationSelect.value = String(schedule.cod_location);
        }
        focusLocation(schedule.cod_location);
        document.getElementById("schedule-map")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
      actions.append(view);

      if (canEdit && form) {
        const edit = createText("button", "", "Edit");
        edit.type = "button";
        edit.addEventListener("click", () => editSchedule(schedule));
        actions.append(edit);
      }
      if (canDelete && form) {
        const remove = createText("button", "cod-schedule-delete", "Hapus");
        remove.type = "button";
        remove.addEventListener("click", () => deleteSchedule(schedule));
        actions.append(remove);
      }
      item.append(actions);
      scheduleList.append(item);
    }
  }

  async function loadSchedules() {
    const data = await requestJSON(config.dataset.listUrl);
    schedules = Array.isArray(data.schedules) ? data.schedules : [];
    renderSchedules();
  }

  function resetForm() {
    if (!form) return;
    editId = null;
    form.reset();
    if (formHeading) formHeading.textContent = "Tambah Jadwal COD";
    if (submitButton) submitButton.textContent = "Simpan Jadwal";
    if (cancelEdit) cancelEdit.hidden = true;
    report("");
    if (locationSelect) focusLocation(locationSelect.value);
  }

  function editSchedule(schedule) {
    if (!form) return;
    editId = String(schedule.id);
    scheduleType.value = schedule.schedule_type;
    const isReturn = schedule.schedule_type === "return";

    locationLabel.textContent = isReturn
        ? "Lokasi Pengembalian"
        : "Lokasi Pengambilan";

    locationHint.textContent = isReturn
        ? "Pilih lokasi pengembalian barang. Lokasi boleh berbeda dari lokasi pengambilan."
        : "Pilih lokasi pengambilan barang.";
    locationSelect.value = String(schedule.cod_location);
    scheduledTime.value = localInputDate(schedule.scheduled_time);
    notes.value = schedule.notes || "";
    formHeading.textContent = "Edit Jadwal COD";
    submitButton.textContent = "Simpan Perubahan";
    cancelEdit.hidden = false;
    report("");
    focusLocation(schedule.cod_location);
    form.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function deleteSchedule(schedule) {
    const result = await Swal.fire({
        title: "Hapus jadwal ini?",
        text: `Yakin ingin menghapus jadwal ${schedule.schedule_type_label || schedule.schedule_type} di "${schedule.location_name}"?`,
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Ya, Hapus",
        cancelButtonText: "Batal",
        confirmButtonColor: "#a51d20",
        cancelButtonColor: "#718077",
        reverseButtons: true
    });

    if (!result.isConfirmed) return;

    try {
      await requestJSON(config.dataset.deleteUrl.replace("00000000-0000-0000-0000-000000000000", String(schedule.id)), {
        method: "POST", headers: { "X-CSRFToken": csrfToken },
      });
      if (editId === String(schedule.id)) resetForm();
      await loadSchedules();
      await loadLocations();
      report("Jadwal COD berhasil dihapus.", "success");
    } catch (error) {
      report(asError(error), "error");
    }
  }

  if (locationSelect) {
    locationSelect.addEventListener("change", () => focusLocation(locationSelect.value));
  }
  cancelEdit?.addEventListener("click", resetForm);

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (!locationSelect.value || !locationsById.has(locationSelect.value)) {
      report("Pilih lokasi COD dari daftar lokasi yang tersedia.", "error");
      return;
    }
    const url = editId
      ? config.dataset.updateUrl.replace("00000000-0000-0000-0000-000000000000", editId)
      : config.dataset.createUrl;
    submitButton.disabled = true;
    report("Menyimpan jadwal...");
    try {
      await requestJSON(url, { method: "POST", body: new FormData(form), headers: { "X-CSRFToken": csrfToken } });
      resetForm();
      await loadSchedules();
      await loadLocations();
      report("Jadwal COD berhasil disimpan.", "success");
    } catch (error) {
      report(asError(error), "error");
    } finally {
      submitButton.disabled = false;
    }
  });

  initMap();
  // Muat lokasi lebih dulu agar daftar jadwal dan peta memakai ID yang sama.
  (async () => {
    try { await loadLocations(); }
    catch (error) { report(`Gagal mengambil lokasi: ${asError(error)}`, "error"); }
    try { await loadSchedules(); }
    catch (error) {
      if (scheduleCount) scheduleCount.textContent = "Gagal memuat";
      scheduleList?.replaceChildren(createText("p", "cod-schedule-muted", `Gagal mengambil jadwal: ${asError(error)}`));
    }
  })();
})();
