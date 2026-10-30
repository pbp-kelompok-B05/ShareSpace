const loanList = document.getElementById("loan-list");
const statusFilters = document.querySelectorAll(".loan-filter");
const loanMessage = document.getElementById("loan-message");
const csrfForm = document.getElementById("loan-csrf-form");

let selectedStatus = "";

// Format date
function formatLoanDate(value) {
    const [year, month, day] = value.split("-").map(Number);

    return new Date(year, month - 1, day).toLocaleDateString("id-ID", {day: "numeric", month: "short", year: "numeric"});
}

// Send loan
async function submitLoanAction(url, confirmation) {
    if (!confirm(confirmation)) {
        return;
    }

    loanMessage.textContent = "Memproses permintaan...";

    try {
        const response = await fetch(url, {method: "POST", body: new FormData(csrfForm)});

        if (response.redirected) {
            window.location.href = response.url;
            return;
        }

        const data = await response.json();

        if (!response.ok) {
            loanMessage.textContent = data.message || "Permintaan gagal.";
            return;
        }

        loanMessage.textContent = data.message || "Berhasil.";
        await loadLoans();

    } catch (error) {
        loanMessage.textContent = "Terjadi kesalahan.";
        console.error(error);
    }
}

// Create action button
function makeLoanButton(text, className, url, confirmation) {
    const button = document.createElement("button");

    button.type = "button";
    button.className = "loan-action " + className;
    button.textContent = text;

    button.onclick = async () => {
        button.disabled = true;
        await submitLoanAction(url, confirmation);
        button.disabled = false;
    };

    return button;
}

// Load loan list
async function loadLoans() {
    loanList.textContent = "Memuat transaksi...";

    try {
        const url = loanList.dataset.url + "?status=" + encodeURIComponent(selectedStatus);
        const response = await fetch(url);

        if (response.redirected) {
            window.location.href = response.url;
            return;
        }

        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            loanList.textContent = "Gagal memuat transaksi (HTTP " + response.status + "). Periksa log server Django.";
            return;
        }

        const data = await response.json();

        if (!response.ok) {
            loanList.textContent = data.error || "Gagal memuat transaksi.";
            return;
        }

        loanList.innerHTML = "";

        if (data.loans.length === 0) {
            loanList.textContent = "Belum ada transaksi.";
            return;
        }

        for (const loan of data.loans) {
            const card = document.createElement("article");
            card.className = "loan-card";

            // Item image
            const imageBox = document.createElement("div");
            imageBox.className = "loan-item-image";

            if (loan.image_url) {
                const image = document.createElement("img");

                image.src = loan.image_url;
                image.alt = loan.item_name;

                image.onerror = () => {
                    image.remove();
                };

                imageBox.appendChild(image);
            }

            // Card information
            const content = document.createElement("div");
            content.className = "loan-card-body";

            const meta = document.createElement("div");
            meta.className = "loan-card-meta";

            const status = document.createElement("span");
            status.className = "loan-status status-" + loan.status;
            status.textContent = loan.status_label;

            const id = document.createElement("span");
            id.className = "loan-transaction-id";
            id.textContent = "#TRX-" + loan.id.slice(0, 8).toUpperCase();

            meta.appendChild(status);
            meta.appendChild(id);

            const name = document.createElement("h2");
            name.textContent = loan.item_name;

            const summary = document.createElement("p");

            let dateInfo = "Rencana Pinjam: " + formatLoanDate(loan.start_date) + " - " + formatLoanDate(loan.due_date);

            if (loan.status === "borrowed") {
                dateInfo = "Batas Kembali: " + formatLoanDate(loan.due_date);
            } else if (loan.status === "completed") {
                dateInfo = "Periode: " + formatLoanDate(loan.start_date) + " - " + formatLoanDate(loan.due_date);
            }

            summary.textContent = loan.person_label + ": " + loan.person_name + " | " + dateInfo;

            content.appendChild(meta);
            content.appendChild(name);
            content.appendChild(summary);

            // Return information
            if (loan.return_requested) {
                const returnInfo = document.createElement("p");
                returnInfo.className = "loan-return-note";

                if (loanList.dataset.role === "borrower") {
                    returnInfo.textContent = "Menunggu konfirmasi pengembalian dari pemilik.";
                } else {
                    returnInfo.textContent = "Peminjam telah mengajukan pengembalian.";
                }

                content.appendChild(returnInfo);
            }

            // Action buttons
            const actions = document.createElement("div");
            actions.className = "loan-card-actions";

            const isBorrower = loanList.dataset.role === "borrower";

            // Cancel
            if (isBorrower && loan.cancel_url) {
                actions.appendChild(makeLoanButton(
                    "Batalkan Permintaan",
                    "loan-action-danger",
                    loan.cancel_url,
                    "Yakin ingin membatalkan pengajuan ini?"
                ));
            }

            // Request return
            if (isBorrower && loan.return_url) {
                actions.appendChild(makeLoanButton(
                    "Kembalikan Barang",
                    "loan-action-primary",
                    loan.return_url,
                    "Apakah barang sudah dikembalikan kepada pemilik?"
                ));
            }

            // Approve
            if (!isBorrower && loan.approve_url) {
                actions.appendChild(makeLoanButton(
                    "Setujui",
                    "loan-action-primary",
                    loan.approve_url,
                    "Yakin ingin menyetujui pengajuan ini?"
                ));
            }

            // Reject
            if (!isBorrower && loan.reject_url) {
                actions.appendChild(makeLoanButton(
                    "Tolak",
                    "loan-action-danger",
                    loan.reject_url,
                    "Yakin ingin menolak pengajuan ini?"
                ));
            }

            // Mark as borrowed
            if (!isBorrower && loan.borrowed_url) {
                actions.appendChild(makeLoanButton(
                    "Barang Diserahkan",
                    "loan-action-primary",
                    loan.borrowed_url,
                    "Apakah barang sudah diserahkan kepada peminjam?"
                ));
            }

            // Complete
            if (!isBorrower && loan.complete_url) {
                actions.appendChild(makeLoanButton(
                    "Konfirmasi Kembali",
                    "loan-action-primary",
                    loan.complete_url,
                    "Apakah barang sudah diterima kembali?"
                ));
            }

            // Contact owner or borrower
            if (loan.contact_url) {
                const contactLink = document.createElement("a");

                contactLink.href = loan.contact_url;
                contactLink.className = "loan-action loan-action-secondary";
                contactLink.textContent = isBorrower ? "Hubungi Pemilik" : "Hubungi Peminjam";

                actions.appendChild(contactLink);
            }

            // Detail
            const detailLink = document.createElement("a");

            detailLink.href = loan.detail_url;
            detailLink.className = "loan-action loan-action-secondary";
            detailLink.textContent = "Rincian";

            actions.appendChild(detailLink);

            // Add card to loan list
            card.appendChild(imageBox);
            card.appendChild(content);
            card.appendChild(actions);

            loanList.appendChild(card);
        }

    } catch (error) {
        loanList.textContent = "Terjadi kesalahan saat memuat transaksi.";
        console.error(error);
    }
}

// Filter loan status
statusFilters.forEach(button => {
    button.onclick = () => {
        selectedStatus = button.dataset.status;

        statusFilters.forEach(filter => {
            filter.classList.remove("active");
            filter.setAttribute("aria-pressed", "false");
        });

        button.classList.add("active");
        button.setAttribute("aria-pressed", "true");

        loadLoans();
    };
});

loadLoans();