/**
 * Script AJAX untuk Halaman Profil Pengguna ShareSpace.
 * Mengikuti pola Tutorial 05 (Web Interactivity with JavaScript) dan proyek individual.
 * 
 * Bertanggung jawab memuat dan memperbarui data reputasi pengguna,
 * Trust Score, katalog barang, serta ulasan komunitas secara asinkronus (AJAX)
 * dengan state management (loading, error, empty, grid), sanitasi XSS (escapeHtml),
 * serta pembatalan request berulang via AbortController.
 */

document.addEventListener("DOMContentLoaded", () => {
    initProfileReputation();
});

// Dukungan HTMX swap jika profil dimuat ulang sebagian
document.addEventListener("htmx:afterSwap", (e) => {
    if (e.target && e.target.querySelector && e.target.querySelector("#profile-reputation-container")) {
        initProfileReputation();
    }
});

function initProfileReputation() {
    const container = document.getElementById("profile-reputation-container");
    if (!container) return;

    const endpoint = container.dataset.reputationEndpoint;
    if (!endpoint) return;

    // Elemen DOM State sesuai Tutorial 05
    const loadingState = document.getElementById("loading");
    const errorState = document.getElementById("error");
    const emptyState = document.getElementById("empty");
    const gridContainer = document.getElementById("grid");
    const reviewsItemsList = document.getElementById("reviews-items-list");

    const refreshButton = document.getElementById("btn-refresh-reputation");
    const refreshSpinner = document.getElementById("reputation-loading-spinner");

    let reviewsAbortController = null;

    // Menyembunyikan/Menampilkan section halaman
    function displayPageSection({ showLoading = false, showError = false, showEmpty = false, showGrid = false }) {
        if (loadingState) loadingState.classList.toggle('hide', !showLoading);
        if (errorState) errorState.classList.toggle('hide', !showError);
        if (emptyState) emptyState.classList.toggle('hide', !showEmpty);
        if (gridContainer) gridContainer.classList.toggle('hide', !showGrid);
    }

    // Mengubah karakter khusus HTML menjadi entity agar ditampilkan sebagai teks (XSS Prevention)
    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    // Fungsi pembantu render bintang rating
    function renderStars(rating) {
        let stars = "";
        for (let i = 1; i <= 5; i++) {
            stars += (i <= rating) ? "★" : "☆";
        }
        return stars;
    }

    // Membuat elemen card review
    function buildReviewCardElement(review) {
        const liElement = document.createElement("li");
        const safeName = escapeHtml(review.reviewer_name);
        const safeInitial = escapeHtml(review.reviewer_initial);
        const safeRole = escapeHtml(review.reviewer_role_display);
        const safeItem = escapeHtml(review.item_name);
        const safeComment = escapeHtml(review.comment || "Pengguna tidak menyertakan komentar tertulis.");
        const safeTime = escapeHtml(review.relative_time);
        const stars = renderStars(review.rating);

        const transactionHtml = safeItem
            ? `<span class="card-meta block text-xs">Transaksi: <span class="font-medium text-ink">${safeItem}</span></span>`
            : "";

        liElement.innerHTML = `
            <article class="card card-interactive border border-solid border-line p-5 transition-all"
                     style="background-color: var(--surface-soft); border: 1px solid var(--line); border-radius: 16px;">
                <div class="flex flex-col gap-3">
                    <div class="flex flex-wrap items-start justify-between gap-3">
                        <div class="flex items-center gap-3">
                            <div class="grid h-10 w-10 shrink-0 place-items-center rounded-full font-heading text-sm font-bold shadow-sm"
                                 style="background-color: var(--surface); color: var(--green); border: 1px solid var(--line);">
                                ${safeInitial}
                            </div>
                            <div>
                                <div class="flex flex-wrap items-center gap-2">
                                    <span class="font-heading font-bold text-ink">${safeName}</span>
                                    <span class="badge badge-category text-[11px] font-semibold">${safeRole}</span>
                                </div>
                                ${transactionHtml}
                            </div>
                        </div>
                        <div class="flex flex-col items-end gap-1">
                            <div class="flex items-center gap-1.5" title="${review.rating} dari 5 bintang">
                                <span class="review-stars text-base font-bold" style="color: var(--amber); letter-spacing: 2px;" aria-hidden="true">${stars}</span>
                                <span class="font-heading text-xs font-bold text-ink/75">${review.rating}.0</span>
                            </div>
                            <span class="card-meta text-xs">${safeTime}</span>
                        </div>
                    </div>
                    <div class="rounded-xl p-3 md:p-4" style="background-color: var(--surface); border: 1px solid var(--line);">
                        <p class="m-0 text-sm leading-relaxed text-ink/90 italic">“${safeComment}”</p>
                    </div>
                </div>
            </article>
        `;
        return liElement;
    }

    // Memperbarui Sidebar dan Banner Statistik Aktivitas
    function updateSidebarAndBanner(data) {
        // Sidebar Trust Score
        const trustScoreBadge = document.getElementById("trust-score-badge");
        if (trustScoreBadge) {
            trustScoreBadge.textContent = data.average_rating !== null
                ? `★ ${data.average_rating.toFixed(1)} / 5.0`
                : "★ – / 5.0";
        }

        const trustScoreValue = document.getElementById("trust-score-sidebar-value");
        if (trustScoreValue) {
            trustScoreValue.textContent = data.trust_score !== null ? `${data.trust_score}%` : "–";
        }

        const trustLevelBadge = document.getElementById("trust-level-badge");
        if (trustLevelBadge) {
            trustLevelBadge.textContent = data.trust_level;
            trustLevelBadge.className = data.trust_score !== null ? "badge badge-verified" : "badge";
        }

        const trustScoreDesc = document.getElementById("trust-score-description");
        if (trustScoreDesc) {
            trustScoreDesc.textContent = data.trust_description;
        }

        const sidebarCompleted = document.getElementById("sidebar-completed-loans");
        if (sidebarCompleted) sidebarCompleted.textContent = data.completed_loans_count;

        const sidebarReviews = document.getElementById("sidebar-reviews-count");
        if (sidebarReviews) sidebarReviews.textContent = data.reviews_count;

        // Banner Statistik Aktivitas
        const bannerTrustScore = document.getElementById("banner-trust-score");
        if (bannerTrustScore) {
            bannerTrustScore.textContent = data.trust_score !== null ? `${data.trust_score}%` : "–";
        }

        const bannerTrustLevel = document.getElementById("banner-trust-level");
        if (bannerTrustLevel) {
            bannerTrustLevel.textContent = data.trust_level;
            bannerTrustLevel.className = data.trust_score !== null ? "badge badge-verified text-xs" : "badge text-xs";
        }

        const bannerItems = document.getElementById("banner-items-count");
        if (bannerItems) bannerItems.textContent = `${data.owned_items_count} Barang`;

        const bannerBorrowed = document.getElementById("banner-borrowed-count");
        if (bannerBorrowed) bannerBorrowed.textContent = `${data.borrowed_loans_count} Kali`;

        const bannerCompleted = document.getElementById("banner-completed-count");
        if (bannerCompleted) bannerCompleted.textContent = `${data.completed_loans_count} Selesai`;
    }

    // Fetch data ulasan dan reputasi menggunakan Fetch API & AbortController
    async function fetchReviews() {
        if (reviewsAbortController) reviewsAbortController.abort();
        reviewsAbortController = new AbortController();

        try {
            displayPageSection({ showLoading: true });
            if (refreshSpinner) refreshSpinner.classList.remove("hidden");
            if (refreshButton) refreshButton.setAttribute("disabled", "true");

            const response = await fetch(endpoint, {
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                signal: reviewsAbortController.signal,
            });

            if (!response.ok) throw new Error("Failed to fetch data");
            const data = await response.json();

            // Perbarui sidebar dan banner metrik
            updateSidebarAndBanner(data);

            // Perbarui judul ulasan dan rata-rata rating
            const reviewsHeading = document.getElementById("reviews-heading");
            if (reviewsHeading) {
                reviewsHeading.textContent = `Ulasan Komunitas (${data.reviews_count})`;
            }

            const reviewsAverage = document.getElementById("reviews-average-rating");
            if (reviewsAverage) {
                reviewsAverage.textContent = data.average_rating !== null
                    ? `${data.average_rating.toFixed(1)} Rata-rata`
                    : "– Rata-rata";
            }

            // Tampilkan empty state atau grid cards
            if (!data.reviews || data.reviews.length === 0) {
                displayPageSection({ showEmpty: true });
            } else {
                if (reviewsItemsList) {
                    reviewsItemsList.innerHTML = "";
                    data.reviews.forEach((review) => {
                        reviewsItemsList.appendChild(buildReviewCardElement(review));
                    });
                }
                displayPageSection({ showGrid: true });
            }
        } catch (e) {
            if (e.name === "AbortError") return;
            console.error("Gagal memuat ulasan:", e);
            displayPageSection({ showError: true });
        } finally {
            if (refreshSpinner) refreshSpinner.classList.add("hidden");
            if (refreshButton) refreshButton.removeAttribute("disabled");
        }
    }

    // Pasang event listener pada tombol reload/refresh
    if (refreshButton) {
        refreshButton.addEventListener("click", (e) => {
            e.preventDefault();
            fetchReviews();
        });
    }

    // Jalankan AJAX untuk sinkronisasi data terkini
    fetchReviews();
}
