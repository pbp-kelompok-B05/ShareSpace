document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".cod-map-preview").forEach(element => {
        const latitude = Number(element.dataset.latitude);
        const longitude = Number(element.dataset.longitude);
        const locationName = element.dataset.name || "Lokasi COD";

        if (!Number.isFinite(latitude) ||
            !Number.isFinite(longitude)) {
            return;
        }

        const map = L.map(element, {
            scrollWheelZoom: false,
        }).setView([latitude, longitude], 16);

        // Sama seperti codmap.js utama
        L.maplibreGL({
            style: "https://tiles.openfreemap.org/styles/liberty",
            attribution:
                '&copy; <a href="https://openfreemap.org">OpenFreeMap</a> ' +
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        L.marker([latitude, longitude])
            .addTo(map)
            .bindPopup(locationName);

        // Memastikan peta tampil dengan ukuran benar
        setTimeout(() => map.invalidateSize(), 100);
    });
});