
document.addEventListener("DOMContentLoaded", () => {
    const config = document.getElementById("cod-config");
    const listUrl = config.dataset.listUrl;
    const createUrl = config.dataset.createUrl;

    const listElement = document.getElementById("location-list");
    const searchInput = document.getElementById("location-search");
    const formPanel = document.getElementById("location-form-panel");
    const form = document.getElementById("location-form");
    const formTitle = document.getElementById("form-title");
    const message = document.getElementById("form-message");

    let locations = [];
    let editingId = null;
    let selectedMarker = null;
    const markers = L.layerGroup();

    const map = L.map("cod-map").setView(
        [-6.3653, 106.8315], 14
    );

    // L.tileLayer(
    //     "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    //     {
    //         attribution: '&copy; OpenStreetMap contributors',
    //         maxZoom: 19
    //     }
    //     "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    // {
    //     attribution:
    //         '&copy; OpenStreetMap contributors &copy; CARTO',
    //     subdomains: "abcd",
    //     maxZoom: 19
    // }
        // "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        // {
        //     attribution: "Tiles &copy; Esri",
        //     maxZoom: 19
        // }
        // "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        // {
        //     attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
        //     subdomains: "abcd",
        //     maxZoom: 20,
        // }
        

    // ).addTo(map);

    L.maplibreGL({
        style: "https://tiles.openfreemap.org/styles/liberty",
        attribution:
            '&copy; <a href="https://openfreemap.org">OpenFreeMap</a> ' +
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    markers.addTo(map);

    const csrfToken = document.querySelector(
        "[name=csrfmiddlewaretoken]"
    ).value;

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char]));
    }

    function showForm(location = null) {
        form.reset();
        message.textContent = "";

        editingId = location ? location.id : null;

        formTitle.textContent = location
            ? "Edit Lokasi COD"
            : "Tambah Lokasi COD";

        if (location) {
            form.elements.name.value = location.name;
            form.elements.address.value = location.address;
            form.elements.latitude.value = Number(location.latitude).toFixed(6);
            form.elements.longitude.value = Number(location.longitude).toFixed(6);
            form.elements.notes.value = location.notes;

            map.setView(
                [location.latitude, location.longitude], 16
            );
        }

        formPanel.hidden = false;

        setTimeout(() => map.invalidateSize(), 100);
    }

    function hideForm() {
        formPanel.hidden = true;
        editingId = null;
        form.reset();

        if (selectedMarker) {
            map.removeLayer(selectedMarker);
            selectedMarker = null;
        }
    }

    map.on("click", event => {
        if (formPanel.hidden) return;

        const { lat, lng } = event.latlng;

        form.elements.latitude.value = lat.toFixed(6);
        form.elements.longitude.value = lng.toFixed(6);

        if (selectedMarker) {
            map.removeLayer(selectedMarker);
        }

        selectedMarker = L.marker([lat, lng])
            .addTo(map)
            .bindPopup("Lokasi COD yang dipilih")
            .openPopup();
    });

    function renderLocations() {
        const keyword = searchInput.value.toLowerCase();

        const filtered = locations.filter(location =>
            location.name.toLowerCase().includes(keyword) ||
            location.address.toLowerCase().includes(keyword)
        );

        listElement.innerHTML = "";

        if (filtered.length === 0) {
            listElement.textContent = "Tidak ada lokasi COD.";
            return;
        }

        filtered.forEach(location => {
            const card = document.createElement("div");
            card.className = "location-card";

            card.innerHTML = `
                <h4>${escapeHTML(location.name)}</h4>
                <p>${escapeHTML(location.address)}</p>
                <div class="location-actions">
                    <button type="button" class="view-btn">
                        Lihat
                    </button>
                    <button type="button" class="edit-btn">
                        Edit
                    </button>
                    <button type="button" class="delete-btn">
                        Hapus
                    </button>
                </div>
            `;

            card.querySelector(".view-btn").onclick = () => {
                map.setView(
                    [location.latitude, location.longitude], 17
                );
            };

            card.querySelector(".edit-btn").onclick = () => {
                showForm(location);
            };

            card.querySelector(".delete-btn").onclick = () => {
                deleteLocation(location);
            };

            listElement.appendChild(card);
        });
    }

    function renderMarkers() {
        markers.clearLayers();

        locations.forEach(location => {
            L.marker([
                location.latitude,
                location.longitude
            ])
            .bindPopup(
                `<b>${escapeHTML(location.name)}</b><br>` +
                escapeHTML(location.address)
            )
            .addTo(markers);
        });
    }

    async function loadLocations() {
        try {
            const response = await fetch(listUrl);
            if (!response.ok) {
                throw new Error("Gagal mengambil data lokasi.");
            }

            const data = await response.json();
            locations = data.locations;

            renderLocations();
            renderMarkers();
        } catch (error) {
            listElement.textContent = error.message;
        }
    }

    async function deleteLocation(location) {
        const result = await Swal.fire({
            title: "Hapus lokasi ini?",
            text: `Yakin ingin menghapus lokasi "${location.name}"?`,
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Ya, Hapus",
            cancelButtonText: "Batal",
            confirmButtonColor: "#a51d20",
            cancelButtonColor: "#718077",
            background: "#ffffff",
            color: "#20372d",
            reverseButtons: true,
            customClass: {
                popup: "cod-confirm-popup"
            }
        });

        if (!result.isConfirmed) return;

        try {
            const response = await fetch(
                `${listUrl}${location.id}/delete/`,
                {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken
                    }
                }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "Gagal menghapus.");
            }

            await loadLocations();
        } catch (error) {
            alert(error.message);
        }
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();

        const url = editingId
            ? `${listUrl}${editingId}/update/`
            : createUrl;

        message.textContent = "Menyimpan lokasi...";

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken
                },
                body: new FormData(form)
            });

            const data = await response.json();

            if (!response.ok) {
                const errors = data.errors
                    ? Object.values(data.errors)
                        .flat()
                        .map(error => error.message)
                        .join(" ")
                    : data.message;

                throw new Error(errors || "Gagal menyimpan.");
            }

            hideForm();
            await loadLocations();
        } catch (error) {
            message.textContent = error.message;
        }
    });

    document.getElementById("add-location-btn")
        .addEventListener("click", () => showForm());

    document.getElementById("cancel-location-btn")
        .addEventListener("click", hideForm);

    searchInput.addEventListener("input", renderLocations);

    
    // ==========================================
    // OVERPASS API - REKOMENDASI LOKASI
    // ==========================================

    const overpassMarkers = L.layerGroup().addTo(map);

    const overpassButton =
        document.getElementById("overpass-search-btn");

    const overpassStatus =
        document.getElementById("overpass-status");

    const overpassResults =
        document.getElementById("overpass-results");

    function selectRecommendedLocation(place) {
        showForm();

        form.elements.name.value = place.name;
        form.elements.address.value = place.address;
        form.elements.latitude.value = Number(place.latitude).toFixed(6);
        form.elements.longitude.value = Number(place.longitude).toFixed(6);

        if (selectedMarker) {
            map.removeLayer(selectedMarker);
        }

        selectedMarker = L.marker([
            place.latitude,
            place.longitude
        ]).addTo(map);

        map.setView([
            place.latitude,
            place.longitude
        ], 17);

        formPanel.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    overpassButton.addEventListener("click", async () => {
        const category =
            document.getElementById("overpass-category").value;

        const radius = Number(
            document.getElementById("overpass-radius").value
        );

        const keyword =
            document.getElementById("overpass-keyword").value;

        const center = map.getCenter();

        overpassButton.disabled = true;
        overpassStatus.textContent = "Mencari lokasi publik...";
        overpassResults.replaceChildren();
        overpassMarkers.clearLayers();

        try {
            const places = await OverpassAPI.search({
                latitude: center.lat,
                longitude: center.lng,
                radius,
                category,
                keyword
            });

            overpassStatus.textContent =
                `${places.length} lokasi ditemukan.`;

            places.forEach(place => {
                const marker = L.marker([
                    place.latitude,
                    place.longitude
                ]).addTo(overpassMarkers);

                marker.bindPopup(
                    `<strong>${escapeHTML(place.name)}</strong>`
                );

                const card = document.createElement("div");
                card.className = "overpass-result";

                const name = document.createElement("h4");
                name.textContent = place.name;

                const address = document.createElement("p");
                address.textContent = place.address;

                const button = document.createElement("button");
                button.type = "button";
                button.className = "btn-primary";
                button.textContent = "Pilih Lokasi";

                button.addEventListener("click", () => {
                    selectRecommendedLocation(place);
                });

                card.append(name, address, button);
                overpassResults.appendChild(card);
            });

        } catch (error) {
            overpassStatus.textContent =
                error.name === "AbortError"
                    ? "Pencarian terlalu lama. Coba lagi."
                    : error.message;
        } finally {
            overpassButton.disabled = false;
        }
    });


    loadLocations();
});
