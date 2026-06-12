document.addEventListener("DOMContentLoaded", function () {
    const root = document.documentElement;
    const toggleButton = document.getElementById("theme-toggle");
    const toggleIcon = document.getElementById("theme-toggle-icon");
    const toggleText = document.getElementById("theme-toggle-text");
    const refreshButtons = document.querySelectorAll('[data-action="refresh"]');

    function getPreferredTheme() {
        const saved = localStorage.getItem("jom-theme");
        if (saved === "dark" || saved === "light") {
            return saved;
        }

        if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
            return "light";
        }

        return "dark";
    }

    function setTheme(theme) {
        root.setAttribute("data-theme", theme);
        localStorage.setItem("jom-theme", theme);

        if (!toggleButton || !toggleIcon || !toggleText) {
            return;
        }

        if (theme === "light") {
            toggleIcon.textContent = "🌞";
            toggleText.textContent = "Light mode";
            toggleButton.setAttribute("aria-label", "Switch to dark mode");
        } else {
            toggleIcon.textContent = "🌙";
            toggleText.textContent = "Dark mode";
            toggleButton.setAttribute("aria-label", "Switch to light mode");
        }
    }

    function toggleTheme() {
        const current = root.getAttribute("data-theme") || "dark";
        const next = current === "dark" ? "light" : "dark";
        setTheme(next);
    }

    setTheme(getPreferredTheme());

    if (toggleButton) {
        toggleButton.addEventListener("click", toggleTheme);
    }

    refreshButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            window.location.reload();
        });
    });
});