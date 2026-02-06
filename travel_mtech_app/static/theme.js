document.addEventListener("DOMContentLoaded", function () {

    const toggle = document.getElementById("themeToggle");

    if (!toggle) return;

    toggle.addEventListener("change", () => {
        if (toggle.checked) {
            document.body.style.background = "#1b1b1b";
            document.body.style.color = "#fff";
        } else {
            document.body.style.background = "";
            document.body.style.color = "";
        }
    });
});
