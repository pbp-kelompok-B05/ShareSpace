/**
 * Handler Google Identity Services (GSI) untuk tombol masuk/daftar Google.
 * Menghindari inline script dan onclick handler sesuai panduan design system ShareSpace.
 */

(function () {
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + "=")) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function triggerGoogleSignIn() {
        if (window.google && google.accounts && google.accounts.id) {
            google.accounts.id.prompt();
        } else {
            alert("Sedang memuat Google Sign-In, silakan coba beberapa detik lagi.");
        }
    }

    // Callback global untuk Google GSI data-callback
    window.handleGoogleLogin = function (response) {
        if (!response || !response.credential) return;

        const googleBtn = document.getElementById("btn-google-signin");
        const endpoint = googleBtn ? googleBtn.dataset.endpoint : "/auth/google/";
        const defaultRedirect = googleBtn ? (googleBtn.dataset.defaultRedirect || "/") : "/";

        fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({ credential: response.credential }),
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    window.location.href = data.redirect_url || defaultRedirect;
                } else {
                    alert(data.message || "Gagal masuk dengan Google.");
                }
            })
            .catch(e => {
                console.error("Gagal melakukan autentikasi Google:", e);
                alert("Terjadi kendala jaringan saat menghubungi server.");
            });
    };

    document.addEventListener("DOMContentLoaded", function () {
        const signinBtn = document.getElementById("btn-google-signin");
        if (signinBtn) {
            signinBtn.addEventListener("click", function (e) {
                e.preventDefault();
                triggerGoogleSignIn();
            });
        }

        const unconfiguredBtn = document.getElementById("btn-google-unconfigured");
        if (unconfiguredBtn) {
            unconfiguredBtn.addEventListener("click", function (e) {
                e.preventDefault();
                alert("Google Client ID belum dikonfigurasi pada file .env.");
            });
        }
    });
})();

