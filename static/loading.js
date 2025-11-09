document.addEventListener("DOMContentLoaded", function() {
    const loader = document.getElementById("loading-screen");
    if (loader) {
        setTimeout(() => {
            loader.style.display = "none";
        }, 500); // полсекунды для плавности
    }
});
