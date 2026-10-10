if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
        navigator.serviceWorker
            .register("/static/serviceworker.js")
            .then(function (registration) {
                console.log("IponPM service worker registered:", registration.scope);
            })
            .catch(function (error) {
                console.error("Service worker registration failed:", error);
            });
    });
}