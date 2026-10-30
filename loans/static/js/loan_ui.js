// Perubahan UI tanpa mengubah handler Loans yang sudah ada
const loanUIForm = document.getElementById("loan-form");
const loanUIFlash = sessionStorage.getItem("loan-ui-success");

if (loanUIFlash) {
    sessionStorage.removeItem("loan-ui-success");
    if (window.ShareSpace && window.ShareSpace.toast) window.ShareSpace.toast(loanUIFlash, "success");
}

// Link pengajuan pada detail barang membuka modal, bukan GET ke endpoint create
if (loanUIForm) {
    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[href]");

        if (!link || link.getAttribute("href") !== loanUIForm.getAttribute("action")) {
            return;
        }

        event.preventDefault();
        const button = document.getElementById("open-loan-modal");
        if (button) {
            button.click();
        }
    });
}

// Konfirmasi aksi dari daftar transaksi
if (document.getElementById("loan-list") && typeof submitLoanAction === "function") {
    window.submitLoanAction = async (url, confirmation) => {
        const danger = /batal|tolak/i.test(confirmation);
        const accepted = await askLoanConfirm({
            title: "Konfirmasi Transaksi", message: confirmation,
            confirmLabel: danger ? "Ya, Lanjutkan" : "Konfirmasi", danger: danger
        });

        if (!accepted) {
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
            const text = data.message || "Permintaan gagal.";

            loanMessage.textContent = text;
            if (window.ShareSpace && window.ShareSpace.toast) {
                window.ShareSpace.toast(text, response.ok ? "success" : "error");
            }

            if (response.ok) {
                await loadLoans();
            }
            
        } catch (error) {
            loanMessage.textContent = "Terjadi kesalahan koneksi.";

            if (window.ShareSpace && window.ShareSpace.toast) {
                window.ShareSpace.toast(loanMessage.textContent, "error");
            }

            console.error(error);
        }
    };
}

// Ganti konfirmasi bawaan browser pada halaman detail transaksi
const loanUIActions = {
    "cancel-form": ["Batalkan Pengajuan", "Pengajuan yang dibatalkan tidak dapat dilanjutkan.", true],
    "approve-form": ["Setujui Pengajuan", "Pengajuan lain untuk barang ini akan otomatis ditolak.", false],
    "reject-form": ["Tolak Pengajuan", "Pengajuan peminjam ini akan ditolak.", true],
    "borrowed-form": ["Konfirmasi Penyerahan", "Pastikan barang sudah diserahkan kepada peminjam.", false],
    "return-form": ["Ajukan Pengembalian", "Pastikan barang sudah dikembalikan kepada pemilik.", false],
    "complete-form": ["Konfirmasi Pengembalian", "Pastikan barang sudah diterima kembali dari peminjam.", false]
};

for (const [formId, options] of Object.entries(loanUIActions)) {
    const form = document.getElementById(formId);

    if (!form) {
        continue;
    }
    
    form.onsubmit = async (event) => {
        event.preventDefault();
        const accepted = await askLoanConfirm({title: options[0], message: options[1], confirmLabel: options[0], danger: options[2]});

        if (!accepted) {
            return;
        }

        const button = form.querySelector('button[type="submit"]');
        const message = document.getElementById(formId.replace("-form", "-message"));

        if (button) {
            button.disabled = true;
        }

        if (message) {
            message.textContent = "Memproses permintaan...";
        }

        try {
            const response = await fetch(form.action, {method: "POST", body: new FormData(form)});

            if (response.redirected) {
                window.location.href = response.url;
                return;
            }

            const data = await response.json();
            const text = data.message || "Permintaan gagal.";

            if (!response.ok) {
                if (message) message.textContent = text;
                if (window.ShareSpace && window.ShareSpace.toast) window.ShareSpace.toast(text, "error");
                return;
            }

            sessionStorage.setItem("loan-ui-success", text);
            window.location.reload();

        } catch (error) {
            if (message) {
                message.textContent = "Terjadi kesalahan koneksi.";
            }

            if (window.ShareSpace && window.ShareSpace.toast) {
                window.ShareSpace.toast("Terjadi kesalahan koneksi.", "error");
            }

            console.error(error);
            
        } finally {
            if (button) button.disabled = false;
        }
    };
}