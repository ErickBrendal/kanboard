window.render = function() {
    console.log("render() called. window.DATA:", window.DATA);
    const currentData = window.DATA || [];
    const totalDemandas = currentData.length;
    document.getElementById("kpi-total-demandas").innerText = totalDemandas;
};

window.populateFilters = function(data) {
    console.log("populateFilters() called with data:", data);
    // Nenhuma lógica de filtro real para o teste mínimo
};

document.addEventListener("DOMContentLoaded", function() {
    let attempts = 0;
    const maxAttempts = 50; // 5 segundos
    const interval = 100; // 100ms

    function checkDataAndRender() {
        if (window.DATA && window.DATA.length > 0) {
            console.log("window.DATA found. Populating filters and rendering.");
            window.populateFilters(window.DATA);
            window.render();
        } else if (attempts < maxAttempts) {
            attempts++;
            console.log(`Attempt ${attempts}/${maxAttempts}: window.DATA not yet available. Retrying...`);
            setTimeout(checkDataAndRender, interval);
        } else {
            console.error("Falha ao carregar os dados do dashboard (window.DATA) após 5 segundos.");
        }
    }

    checkDataAndRender();
});
