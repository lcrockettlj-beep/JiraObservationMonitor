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
        if (theme === 'dark') {
            root.removeAttribute('data-theme');
        } else {
            root.setAttribute('data-theme', theme);
        }
        try { localStorage.setItem('jom_theme', theme); } catch (e) {}
        return theme;
    }

    function getCurrentTheme() {
        return normaliseTheme(document.documentElement.getAttribute('data-theme') || 'dark');
    }

    function bindSelector(selectEl) {
        if (!selectEl) return;
        selectEl.value = getCurrentTheme();
        selectEl.addEventListener('change', function () {
            applyTheme(selectEl.value);
        });
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
        initToggle: function (elementId) {
            var el = document.getElementById(elementId || 'theme-toggle');
            if (!el) return;
            if (el.tagName === 'SELECT') {
                bindSelector(el);
                return;
            }
        }
    };

    window.JOMTheme.applyStoredTheme();
})();