// Tahan klik pada tombol mata untuk menampilkan password, lepas klik untuk menyembunyikannya lagi.
// Tombol memakai atribut data-password-peek yang berisi id input password.
function showPassword(button) {
    document.getElementById(button.dataset.passwordPeek).type = "text";
}

function hidePassword(button) {
    document.getElementById(button.dataset.passwordPeek).type = "password";
}

document.querySelectorAll("[data-password-peek]").forEach(function (button) {
    button.addEventListener("pointerdown", function () {
        showPassword(button);
    });
    button.addEventListener("pointerup", function () {
        hidePassword(button);
    });
    button.addEventListener("pointerleave", function () {
        hidePassword(button);
    });
    button.addEventListener("pointercancel", function () {
        hidePassword(button);
    });
});

