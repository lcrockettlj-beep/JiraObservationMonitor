(function () {
    function normalizeTheme(value) {
        if (value === 'light') { return 'light'; }
        if (value === 'future-estate') { return 'future-estate'; }
        return 'dark';
    }
    function applyTheme(theme) {
        var root = document.documentElement;
        var normalized = normalizeTheme(theme);
        if (normalized === 'dark') {
            root.removeAttribute('data-theme');
        } else {
            root.setAttribute('data-theme', normalized);
        }
        try { localStorage.setItem('jom_theme', normalized); } catch (e) {}
        return normalized;
    }
    window.JOMTheme = {
        applyStoredTheme: function () {
            try {
                var savedTheme = localStorage.getItem('jom_theme');
                applyTheme(savedTheme || 'dark');
            } catch (e) {
                applyTheme('dark');
            }
        },
        setTheme: function (themeName) {
            return applyTheme(themeName);
        },
        initToggle: function (buttonId) {
            var root = document.documentElement;
            var button = document.getElementById(buttonId || 'theme-toggle');
            if (!button) { return; }
            function applyLabel() {
                var current = normalizeTheme(root.getAttribute('data-theme') || 'dark');
                button.textContent = current === 'light' ? 'Dark mode' : 'Light mode';
            }
            button.addEventListener('click', function () {
                var current = normalizeTheme(root.getAttribute('data-theme') || 'dark');
                applyTheme(current === 'light' ? 'dark' : 'light');
                applyLabel();
            });
            applyLabel();
        }
    };
    window.JOMTheme.applyStoredTheme();
})();
