document.addEventListener("DOMContentLoaded", function () {document.addEventListener("DOMContentLoaded", function    const root = document.documentElement;
    const toggleButton = document.getElementById("theme-toggle");
    const toggleIcon = document.getElementById("theme-toggle-icon");
    const toggleText = document.getElementById("theme-toggle-text");
    const refreshButtons = document.querySelectorAll('[data-action="refresh"]');
    const collapseButtons = document.querySelectorAll("[data-collapse-target]");

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

    function updateToggleUi(theme) {
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

    function setTheme(theme) {
        root.setAttribute("data-theme", theme);
        localStorage.setItem("jom-theme", theme);
        updateToggleUi(theme);
    }

    function toggleTheme() {
        const current = root.getAttribute("data-theme") || getPreferredTheme();
        const next = current === "dark" ? "light" : "dark";
        setTheme(next);
    }

    function setCollapseState(button, collapsed) {
        const targetId = button.getAttribute("data-collapse-target");
        const target = document.getElementById(targetId);
        const icon = button.querySelector(".collapse-button__icon");
        const text = button.querySelector(".collapse-button__text");

        if (!target) {
            return;
        }

        if (collapsed) {
            target.classList.add("is-collapsed");
            button.setAttribute("aria-expanded", "false");
            if (icon) icon.textContent = "+";
            if (text) text.textContent = "Expand";
        } else {
            target.classList.remove("is-collapsed");
            button.setAttribute("aria-expanded", "true");
            if (icon) icon.textContent = "−";
            if (text) text.textContent = "Collapse";
        }
    }

    setTheme(getPreferredTheme());

    if (toggleButton) {
        toggleButton.addEventListener("click", toggleTheme);
    }

    if (window.matchMedia) {
        const mediaQuery = window.matchMedia("(prefers-color-scheme: light)");
        if (typeof mediaQuery.addEventListener === "function") {
            mediaQuery.addEventListener("change", function () {
                const saved = localStorage.getItem("jom-theme");
                if (saved !== "dark" && saved !== "light") {
                    setTheme(getPreferredTheme());
                }
            });
        }
    }

    refreshButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            window.location.reload();
        });
    });

    collapseButtons.forEach(function (button) {
        const targetId = button.getAttribute("data-collapse-target");
        const saved = localStorage.getItem("jom-collapse-" + targetId);
        const shouldCollapse = saved === "collapsed";

        setCollapseState(button, shouldCollapse);

        button.addEventListener("click", function () {
            const expanded = button.getAttribute("aria-expanded") === "true";
            const nextCollapsed = expanded;

            setCollapseState(button, nextCollapsed);
            localStorage.setItem(
                "jom-collapse-" + targetId,
                nextCollapsed ? "collapsed" : "expanded"
            );
        });
    });
});
