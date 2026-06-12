document.addEventListener("DOMContentLoaded", function () {
    const refreshButtons = document.querySelectorAll('[data-action="refresh"]');

    refreshButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            window.location.reload();
        });
    });
});