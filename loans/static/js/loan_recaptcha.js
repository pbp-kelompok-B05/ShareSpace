// Google reCAPTCHA pada form pengajuan
const loanRecaptchaContainer = document.getElementById("loan-recaptcha");
const loanRecaptchaDialog = document.getElementById("loan-modal");
const loanRecaptchaForm = document.getElementById("loan-form");
let loanRecaptchaWidgetId = null;

// Tampilkan reCAPTCHA ketika modal dibuka
function renderLoanRecaptcha() {
    if (!loanRecaptchaContainer || !loanRecaptchaDialog.open || !window.grecaptcha || loanRecaptchaWidgetId !== null) return;

    loanRecaptchaWidgetId = window.grecaptcha.render(loanRecaptchaContainer, {
        sitekey: loanRecaptchaContainer.dataset.sitekey,
        theme: document.documentElement.classList.contains("dark") ? "dark" : "light",
        size: window.innerWidth < 420 ? "compact" : "normal"
    });
}

window.onLoanRecaptchaLoaded = renderLoanRecaptcha;

// Reset token ketika gagal atau modal ditutup
function resetLoanRecaptcha() {
    if (loanRecaptchaWidgetId !== null && window.grecaptcha) {
        window.grecaptcha.reset(loanRecaptchaWidgetId);
    }
}
window.resetLoanRecaptcha = resetLoanRecaptcha;

if (loanRecaptchaDialog) {
    loanRecaptchaDialog.addEventListener("close", resetLoanRecaptcha);
}

const loanRecaptchaOpenButton = document.getElementById("open-loan-modal");
if (loanRecaptchaOpenButton) {
    loanRecaptchaOpenButton.addEventListener("click", renderLoanRecaptcha);
}

// Cegah submit jika reCAPTCHA belum selesai
if (loanRecaptchaForm) {
    loanRecaptchaForm.addEventListener("submit", (event) => {
        const token = loanRecaptchaWidgetId !== null && window.grecaptcha
            ? window.grecaptcha.getResponse(loanRecaptchaWidgetId) : "";

        if (token) return;

        event.preventDefault();
        event.stopImmediatePropagation();

        const message = document.getElementById("loan-message");
        if (message) {
            message.textContent = window.grecaptcha
                ? "Selesaikan verifikasi reCAPTCHA terlebih dahulu."
                : "reCAPTCHA belum termuat. Periksa koneksi internet.";
            message.dataset.level = "error";
        }
    }, true);
}