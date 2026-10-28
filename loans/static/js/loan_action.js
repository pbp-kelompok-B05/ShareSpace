const loanModal = document.getElementById("loan-modal");
const loanForm = document.getElementById("loan-form");
const loanMessage = document.getElementById("loan-message");
const cancelForm = document.getElementById("cancel-form");
const cancelMessage = document.getElementById("cancel-message");
const approveForm = document.getElementById("approve-form");
const approveMessage = document.getElementById("approve-message");
const rejectForm = document.getElementById("reject-form");
const rejectMessage = document.getElementById("reject-message");
const borrowedForm = document.getElementById("borrowed-form");
const borrowedMessage = document.getElementById("borrowed-message");
const returnForm = document.getElementById("return-form");
const returnMessage = document.getElementById("return-message");
const completeForm = document.getElementById("complete-form");
const completeMessage = document.getElementById("complete-message");

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

// Approve
if (approveForm) {
    approveForm.onsubmit = async (event) => {
        event.preventDefault();

        if (!confirm("Apakah Anda yakin ingin menyetujui pengajuan ini?")) {
            return;
        }

        await submitLoanForm(approveForm, approveMessage, "approve");
    };
}

// Reject
if (rejectForm) {
    rejectForm.onsubmit = async (event) => {
        event.preventDefault();

        if (!confirm("Apakah Anda yakin ingin menolak pengajuan ini?")) {
            return;
        }

        await submitLoanForm(rejectForm, rejectMessage, "reject");
    };
}

// Mark as borrowed
if (borrowedForm) {
    borrowedForm.onsubmit = async (event) => {
        event.preventDefault();

        if (!confirm("Apakah barang sudah diserahkan kepada peminjam?")) {
            return;
        }

        await submitLoanForm(borrowedForm, borrowedMessage, "borrowed");
    };
}

// Request return
if (returnForm) {
    returnForm.onsubmit = async (event) => {
        event.preventDefault();

        if (!confirm("Apakah barang sudah dikembalikan kepada pemilik?")) {
            return;
        }

        await submitLoanForm(returnForm, returnMessage, "return");
    };
}

// Complete
if (completeForm) {
    completeForm.onsubmit = async (event) => {
        event.preventDefault();

        if (!confirm("Apakah barang sudah diterima kembali?")) {
            return;
        }

        await submitLoanForm(completeForm, completeMessage, "complete");
    };
}
