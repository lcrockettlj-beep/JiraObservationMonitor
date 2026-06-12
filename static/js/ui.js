document.addEventListener("DOMContentLoaded", function () {
    const refreshButtons = document.querySelectorAll('[data-action="refresh"]');

    refreshButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            window.location.reload();
        });
    });

    const anchorLinks = document.querySelectorAll(".anchor-nav__link");
    const sections = Array.from(anchorLinks)
        .map(function (link) {
            const href = link.getAttribute("href");
            if (!href || !href.startsWith("#")) {
                return null;
            }
            return document.querySelector(href);
        })
        .filter(Boolean);

    if (!anchorLinks.length || !sections.length) {
        return;
    }

    function setActiveAnchor() {
        let activeId = null;
        const offset = 140;

        sections.forEach(function (section) {
            const rect = section.getBoundingClientRect();
            if (rect.top <= offset && rect.bottom >= offset) {
                activeId = "#" + section.id;
            }
        });

        if (!activeId && sections.length) {
            const firstSection = sections[0];
            if (firstSection) {
                activeId = "#" + firstSection.id;
            }
        }

        anchorLinks.forEach(function (link) {
            if (link.getAttribute("href") === activeId) {
                link.classList.add("is-active");
            } else {
                link.classList.remove("is-active");
            }
        });
    }

    window.addEventListener("scroll", setActiveAnchor, { passive: true });
    setActiveAnchor();
});