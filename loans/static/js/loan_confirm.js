// Dialog konfirmasi transaksi
const loanConfirmDialog = document.getElementById("loan-confirm-dialog");
let loanConfirmResolve = null;

function closeLoanConfirm(accepted) {
    const resolve = loanConfirmResolve;
    loanConfirmResolve = null;
    if (loanConfirmDialog && loanConfirmDialog.open) loanConfirmDialog.close();
    if (resolve) resolve(accepted);
}

if (loanConfirmDialog) {
    document.getElementById("loan-confirm-accept").onclick = () => closeLoanConfirm(true);
    document.getElementById("loan-confirm-cancel").onclick = () => closeLoanConfirm(false);

    loanConfirmDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeLoanConfirm(false);
    });

    loanConfirmDialog.onclick = (event) => {
        if (event.target === loanConfirmDialog) closeLoanConfirm(false);
    };
}

function askLoanConfirm(options) {
    if (!loanConfirmDialog || loanConfirmDialog.open) {
        return Promise.resolve(false);
    }

    document.getElementById("loan-confirm-title").textContent = options.title || "Konfirmasi Tindakan";
    document.getElementById("loan-confirm-message").textContent = options.message || "Yakin ingin melanjutkan?";

    const button = document.getElementById("loan-confirm-accept");

    button.textContent = options.confirmLabel || "Lanjutkan";
    button.classList.toggle("loan-confirm-danger", Boolean(options.danger));
    button.classList.toggle("loan-confirm-primary", !options.danger);
    
    return new Promise((resolve) => {
        loanConfirmResolve = resolve;
        loanConfirmDialog.showModal();
        document.getElementById("loan-confirm-cancel").focus();
    });
}