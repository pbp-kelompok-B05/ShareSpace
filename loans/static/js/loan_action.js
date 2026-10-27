const loanModal = document.getElementById("loan-modal");
const loanForm = document.getElementById("loan-form");
const loanMessage = document.getElementById("loan-message");
const cancelForm = document.getElementById("cancel-form");
const cancelMessage = document.getElementById("cancel-message");

// Show and close modal
if (loanModal) {
    document.getElementById("open-loan-modal").onclick = () => loanModal.showModal();
    document.getElementById("close-loan-modal").onclick = () => loanModal.close();
}

// Submit loan
async function submitLoanForm(form, message, action) {
    message.textContent = "Memproses permintaan...";

    try {
        const response = await fetch(form.action, {method: "POST", body: new FormData(form)});

        if (response.redirected) {
            window.location.href = response.url;
            return;
        }

        const data = await response.json();

        if (!response.ok) {
            if (data.errors) {
                message.textContent = Object.values(data.errors).flat().map(error => error.message).join("\n");
            } else {
                message.textContent = data.message || "Permintaan gagal.";
            }
            return;
        }

        if (action === "create") {
            window.location.href = data.detail_url;
        } else {
            window.location.reload();
        }

    } catch (error) {
        message.textContent = "Terjadi kesalahan.";
        console.error(error);
    }
}

// Create / Update
if (loanForm) {
    loanForm.onsubmit = async (event) => {
        event.preventDefault();
        await submitLoanForm(loanForm, loanMessage, loanForm.dataset.mode);
    };
}

// Cancel
if (cancelForm) {
    cancelForm.onsubmit = async (event) => {
        event.preventDefault();

        if (!confirm("Apakah Anda yakin ingin membatalkan pengajuan ini?")) {
            return;
        }

        await submitLoanForm(cancelForm, cancelMessage, "cancel");
    };
}
