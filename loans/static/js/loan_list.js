const loanList = document.getElementById("loan-list");
const statusFilter = document.getElementById("status-filter");

async function loadLoans() {
    loanList.textContent = "Memuat transaksi...";
    const params = new URLSearchParams({status: statusFilter.value});

    try {
        const response = await fetch(`${loanList.dataset.url}?${params}`);

        if (!response.ok) { throw new Error("Gagal mengambil data transaksi."); }

        const data = await response.json();
        loanList.replaceChildren();

        if (data.loans.length === 0) {
            loanList.textContent = "Belum ada transaksi.";
            return;
        }

        data.loans.forEach(loan => {
            const card = document.createElement("article");
            const title = document.createElement("h3");
            const status = document.createElement("p");
            const dates = document.createElement("p");

            title.textContent = loan.item_name;
            status.textContent = loan.status_label;
            dates.textContent = `${loan.start_date} - ${loan.due_date}`;

            card.append(title, status, dates);
            loanList.appendChild(card);
        });

    } catch (error) {
        loanList.textContent = "Terdapat kesalahan dalam memuat transaksi.";
        console.error(error);
    }
}

statusFilter.addEventListener("change", loadLoans);
loadLoans();
