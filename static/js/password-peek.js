// Toggle tampilkan/sembunyikan password saat tombol mata diklik.
// Ramah keyboard (Tab + Space/Enter) dan screen reader dengan aria-pressed dan aria-label dinamis.
document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
        var targetId = button.getAttribute("data-password-toggle");
        var input = document.getElementById(targetId);
        if (!input) return;

        var isCurrentlyPassword = input.type === "password";
        input.type = isCurrentlyPassword ? "text" : "password";

        var isVisible = !isCurrentlyPassword;
        button.setAttribute("aria-pressed", isVisible ? "true" : "false");

        var labelPrefix = isVisible ? "Sembunyikan" : "Tampilkan";
        var fieldLabel = (button.getAttribute("data-field-label") || "kata sandi").toLowerCase();
        button.setAttribute("aria-label", labelPrefix + " " + fieldLabel);
    });
});
