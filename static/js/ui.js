document.addEventListener("DOMContentLoaded", function () {document.addEventListener("-toggle-icon");
    const toggleText = document.getElementById("theme-toggle-text");
    const refreshButtons = document.querySelectorAll('[data-action="refresh"]');
    const collapseButtons = document.querySelectorAll("[data-collapse-trigger]");

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

    function setCollapseHeight(panel) {
        if (!panel) return;

        if (panel.classList.contains("is-collapsed")) {
            panel.style.maxHeight = "0px";
        } else {
            panel.style.maxHeight = panel.scrollHeight + "px";
        }
    }

    function toggleCollapse(button) {
        const targetSelector = button.getAttribute("data-collapse-trigger");
        if (!targetSelector) return;

        const panel = document.querySelector(targetSelector);
        if (!panel) return;

        panel.classList.toggle("is-collapsed");

        if (panel.classList.contains("is-collapsed")) {
            button.textContent = "Expand";
        } else {
            button.textContent = "Collapse";
        }

        setCollapseHeight(panel);
    }

    function initCollapsePanels() {
        collapseButtons.forEach(function (button) {
            const targetSelector = button.getAttribute("data-collapse-trigger");
            if (!targetSelector) return;

            const panel = document.querySelector(targetSelector);
            if (!panel) return;

            panel.classList.add("is-open");
            setCollapseHeight(panel);

            button.addEventListener("click", function () {
                toggleCollapse(button);
            });
        });

        window.addEventListener("resize", function () {
            document.querySelectorAll(".collapse-panel").forEach(function (panel) {
                setCollapseHeight(panel);
            });
        });
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

    initCollapsePanels();
});
    const root = document.documentElement;
    const toggleButton = document.getElementById("theme-toggle");
