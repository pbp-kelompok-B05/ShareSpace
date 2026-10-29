document.addEventListener("DOMContentLoaded", () => {
    const config = document.getElementById("schedule-config");

    const listUrl = config.dataset.listUrl;
    const createUrl = config.dataset.createUrl;
    const locationsUrl = config.dataset.locationsUrl;

    const scheduleList = document.getElementById("schedule-list");
    const scheduleForm = document.getElementById("schedule-form");
    const scheduleMessage = document.getElementById("schedule-message");
    const locationSelect = document.getElementById("cod-location");

    const csrfToken = scheduleForm.querySelector(
        "[name=csrfmiddlewaretoken]"
    ).value;

    const updateUrlTemplate = config.dataset.updateUrl;
    const deleteUrlTemplate = config.dataset.deleteUrl;

    const submitButton = document.getElementById("schedule-submit-btn");
    const cancelEditButton = document.getElementById("cancel-edit-btn");

    const UUID_PLACEHOLDER =
        "00000000-0000-0000-0000-000000000000";

    let editingId = null;

    function buildScheduleUrl(template, id) {
        return template.replace(UUID_PLACEHOLDER, id);
    }

    // ==========================================
    // 1. MENGAMBIL DAFTAR LOKASI COD
    // ==========================================

    async function loadLocations() {
        try {
            const response = await fetch(locationsUrl);

            if (!response.ok) {
                throw new Error("Gagal mengambil lokasi COD.");
            }

            const data = await response.json();

            locationSelect.innerHTML =
                '<option value="">Pilih lokasi COD</option>';

            data.locations.forEach(location => {
                const option = document.createElement("option");

                option.value = location.id;
                option.textContent =
                    `${location.name} - ${location.address}`;

                locationSelect.appendChild(option);
            });

        } catch (error) {
            scheduleMessage.textContent = error.message;
        }
    }

    // ==========================================
    // 2. MENAMPILKAN JADWAL COD
    // ==========================================

    function editSchedule(schedule) {
        editingId = schedule.id;

        scheduleForm.elements.schedule_type.value =
            schedule.schedule_type;

        scheduleForm.elements.cod_location.value =
            schedule.cod_location;

        const date = new Date(schedule.scheduled_time);

        // Konversi ke waktu lokal untuk input datetime-local
        const localDate = new Date(
            date.getTime() - date.getTimezoneOffset() * 60000
        );

        scheduleForm.elements.scheduled_time.value =
            localDate.toISOString().slice(0, 16);

        scheduleForm.elements.notes.value =
            schedule.notes || "";

        submitButton.textContent = "Simpan Perubahan";
        cancelEditButton.hidden = false;

        scheduleMessage.textContent = "Sedang mengedit jadwal COD.";

        scheduleForm.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    async function deleteSchedule(schedule) {
        const confirmed = confirm(
            `Hapus jadwal ${schedule.schedule_type_label}?`
        );

        if (!confirmed) return;

        const url = buildScheduleUrl(
            deleteUrlTemplate,
            schedule.id
        );

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.message || "Gagal menghapus jadwal."
                );
            }

            if (editingId === schedule.id) {
                resetEditMode();
            }

            scheduleMessage.textContent =
                "Jadwal berhasil dihapus.";

            await loadSchedules();

        } catch (error) {
            scheduleMessage.textContent = error.message;
        }
    }

    async function loadSchedules() {
        scheduleList.textContent = "Memuat jadwal COD...";

        try {
            const response = await fetch(listUrl);

            if (!response.ok) {
                throw new Error("Gagal mengambil jadwal COD.");
            }

            const data = await response.json();

            scheduleList.replaceChildren();

            if (data.schedules.length === 0) {
                scheduleList.textContent =
                    "Belum ada jadwal COD.";
                return;
            }

            data.schedules.forEach(schedule => {
                const card = document.createElement("div");
                card.className = "schedule-card";

                const title = document.createElement("h3");
                title.textContent = schedule.schedule_type_label;

                const location = document.createElement("p");
                location.textContent =
                    `Lokasi: ${schedule.location_name}`;

                const time = document.createElement("p");
                time.textContent =
                    `Waktu: ${new Date(
                        schedule.scheduled_time
                    ).toLocaleString("id-ID")}`;

                const notes = document.createElement("p");
                notes.textContent =
                    `Catatan: ${schedule.notes || "-"}`;

                const actions = document.createElement("div");
                actions.className = "schedule-actions";

                const editButton = document.createElement("button");
                editButton.type = "button";
                editButton.textContent = "Edit";

                editButton.addEventListener("click", () => {
                    editSchedule(schedule);
                });

                const deleteButton = document.createElement("button");
                deleteButton.type = "button";
                deleteButton.textContent = "Hapus";

                deleteButton.addEventListener("click", () => {
                    deleteSchedule(schedule);
                });
                

                actions.append(editButton, deleteButton);

                card.append(title, location, time, notes, actions);
                scheduleList.appendChild(card);
            });

        } catch (error) {
            scheduleList.textContent = error.message;
        }
    }

    // ==========================================
    // 3. MENYIMPAN JADWAL COD
    // ==========================================

    function resetEditMode() {
        editingId = null;

        scheduleForm.reset();

        submitButton.textContent = "Simpan Jadwal";
        cancelEditButton.hidden = true;
    }

    cancelEditButton.addEventListener("click", () => {
        resetEditMode();
        scheduleMessage.textContent = "";
    });

    scheduleForm.addEventListener("submit", async event => {
        event.preventDefault();

        const submitButton = scheduleForm.querySelector(
            'button[type="submit"]'
        );

        submitButton.disabled = true;
        scheduleMessage.textContent = "Menyimpan jadwal...";

        try {
            const url = editingId
                ? buildScheduleUrl(updateUrlTemplate, editingId)
                : createUrl;

            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken
                },
                body: new FormData(scheduleForm)
            });

            const data = await response.json();

            if (!response.ok) {
                const errors = data.errors
                    ? Object.values(data.errors)
                        .flat()
                        .map(error => error.message)
                        .join(" ")
                    : data.message;

                throw new Error(
                    errors || "Gagal menyimpan jadwal."
                );
            }

            scheduleMessage.textContent =
                "Jadwal COD berhasil disimpan.";

            // scheduleForm.reset();
            resetEditMode();

            await loadSchedules();

        } catch (error) {
            scheduleMessage.textContent = error.message;
        } finally {
            submitButton.disabled = false;
        }
    });

    // ==========================================
    // 4. INISIALISASI
    // ==========================================

    loadLocations();
    loadSchedules();
});