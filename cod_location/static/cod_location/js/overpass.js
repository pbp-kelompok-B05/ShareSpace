const OverpassAPI = (() => {
    async function search({
        latitude,
        longitude,
        radius = 1000,
        category = "all",
        keyword = "",
    }) {
        const url = new URL(
            document.getElementById("cod-config").dataset.overpassUrl,
            window.location.origin
        );
        url.searchParams.set("lat", latitude);
        url.searchParams.set("lon", longitude);
        url.searchParams.set("radius", radius);
        url.searchParams.set("category", category);
        url.searchParams.set("keyword", keyword.trim());

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 30000);

        try {
            const response = await fetch(url, { signal: controller.signal });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "Pencarian gagal.");
            }
            return data.places;
        } finally {
            clearTimeout(timeout);
        }
    }

    return { search };
})();