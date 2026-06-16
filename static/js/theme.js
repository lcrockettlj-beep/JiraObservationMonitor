(function () {
    window.JOMTheme = {
        applyStoredTheme: function () {
            try {
                var savedTheme = localStorage.getItem("jom_theme");
                if (savedTheme === "light") {
                    document.documentElement.setAttribute("data-theme", "light");
                } else {
                    document.documentElement.removeAttribute("data-theme");
                }
            } catch (e) {}
        },
        initToggle: function (buttonId) {
            var root = document.documentElement;
            var button = document.getElementById(buttonId || "theme-toggle");
            if (!button) { return; }
            function applyLabel() {
                var isLight = root.getAttribute("data-theme") === "light";
                button.textContent = isLight ? "Dark mode" : "Light mode";
            }
            button.addEventListener("click", function () {
                var isLight = root.getAttribute("data-theme") === "light";
                if (isLight) {
                    root.removeAttribute("data-theme");
                    try { localStorage.setItem("jom_theme", "dark"); } catch (e) {}
                } else {
                    root.setAttribute("data-theme", "light");
                    try { localStorage.setItem("jom_theme", "light"); } catch (e) {}
                }
                applyLabel();
            });
            applyLabel();
        }
    };
    window.JOMTheme.applyStoredTheme();
})();
