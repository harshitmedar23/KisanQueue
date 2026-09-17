function initialiseCentreMap() {
    const mapElement = document.getElementById('centreMap');
    if (!mapElement || !window.L || !Array.isArray(window.centres)) return;

    const validCentres = window.centres.filter((centre) => Number(centre.lat) && Number(centre.lng));
    mapElement.classList.add('map-panel-ready');
    const map = L.map(mapElement, { scrollWheelZoom: false }).setView(
        [validCentres[0]?.lat || 20.5937, validCentres[0]?.lng || 78.9629],
        validCentres.length ? 11 : 5
    );
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
    const markerBounds = [];
    const markers = [];
    validCentres.forEach((centre) => {
        const centreName = window.translateText ? window.translateText(centre.name) : centre.name;
        const centreLocation = window.translateText ? window.translateText(centre.location) : centre.location;
        markerBounds.push([centre.lat, centre.lng]);
        const marker = L.marker([centre.lat, centre.lng])
        .addTo(map)
        .bindPopup(`<strong>${centreName}</strong><br>${centreLocation}`);
        markers.push(marker);
    });
    if (markerBounds.length > 1) map.fitBounds(markerBounds, { padding: [28, 28] });

    const label = document.getElementById('selectedCentreLabel');
    const switchButtons = document.querySelectorAll('.centre-switch');
    const selectCentre = (index) => {
        const centre = validCentres[index];
        if (!centre || !markers[index]) return;
        map.setView([centre.lat, centre.lng], 13, { animate: true });
        markers[index].openPopup();
        if (label) label.textContent = centre.name;
        switchButtons.forEach((button, buttonIndex) => button.classList.toggle('active', buttonIndex === index));
    };
    switchButtons.forEach((button) => button.addEventListener('click', () => {
        selectCentre(Number(button.dataset.centreIndex));
    }));
    if (validCentres.length) selectCentre(0);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialiseCentreMap);
} else {
    initialiseCentreMap();
}
