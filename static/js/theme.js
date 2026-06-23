
(function () {
    var THEMES = [
        { key: 'dark', label: 'Dark core' },
        { key: 'cyber', label: 'Cyber mode' },
        { key: 'enterprise', label: 'Enterprise mode' },
        { key: 'noc', label: 'NOC mode' },
        { key: 'light', label: 'Light mode' }
    ];

    function normaliseTheme(value) {
        for (var i = 0; i < THEMES.length; i += 1) {
            if (THEMES[i].key === value) return value;
        }
        return 'dark';
    }

    function applyTheme(themeName) {
        var root = document.documentElement;
        var theme = normaliseTheme(themeName);
        if (theme === 'dark') root.removeAttribute('data-theme');
        else root.setAttribute('data-theme', theme);
        try { localStorage.setItem('jom_theme', theme); } catch (e) {}
        return theme;
    }

    function getCurrentTheme() {
        var raw = document.documentElement.getAttribute('data-theme') || 'dark';
        return normaliseTheme(raw);
    }

    function getThemeLabel(themeName) {
        for (var i = 0; i < THEMES.length; i += 1) {
            if (THEMES[i].key === themeName) return THEMES[i].label;
        }
        return 'Dark core';
    }

    function cycleTheme() {
        var current = getCurrentTheme();
        var idx = 0;
        for (var i = 0; i < THEMES.length; i += 1) {
            if (THEMES[i].key === current) { idx = i; break; }
        }
        var next = THEMES[(idx + 1) % THEMES.length].key;
        return applyTheme(next);
    }

    window.JOMTheme = {
        applyStoredTheme: function () {
            try {
                var saved = localStorage.getItem('jom_theme');
                applyTheme(saved || 'dark');
            } catch (e) {
                applyTheme('dark');
            }
        },
        setTheme: function (themeName) {
            return applyTheme(themeName);
        },
        initToggle: function (buttonId) {
            var button = document.getElementById(buttonId || 'theme-toggle');
            if (!button) return;
            function refreshLabel() {
                button.textContent = getThemeLabel(getCurrentTheme());
            }
            button.addEventListener('click', function () {
                cycleTheme();
                refreshLabel();
            });
            refreshLabel();
        }
    };

    window.JOMTheme.applyStoredTheme();
})();
