const loanModal = document.getElementById("loan-modal");
const loanForm = document.getElementById("loan-form");
const loanMessage = document.getElementById("loan-message");

// Show and close modal
document.getElementById("open-loan-modal").onclick = () => modal.showModal();
document.getElementById("close-loan-modal").onclick = () => modal.close();

// Submit loan
form.onsubmit = async (event) => {
    event.preventDefault();
    message.textContent = "Mengirim pengajuan...";

    try {
        const response = await fetch(form.action, {method: "POST", body: new FormData(form)});
        const data = await response.json();

        if (!response.ok) {
            loanMessage.textContent = data.message;
            return;
        }

        window.location.href = data.detail_url;

    } catch (error) {
        loanMessage.textContent = "Gagal mengirim pengajuan.";
        console.error(error);
    }
};
