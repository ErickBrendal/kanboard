window.render = function() {
    console.log("render() called.");
    console.log("window.DATA inside render():", window.DATA);
    console.log("Element kpi-total-demandas inside render():", document.getElementById("kpi-total-demandas"));

    // Funções auxiliares
    function formatCurrency(value) {
        return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
    }

    function formatDate(timestamp) {
        if (!timestamp) return "N/A";
        const date = new Date(timestamp * 1000);
        return date.toLocaleDateString("pt-BR");
    }

    function calculateDaysInPhase(task) {
        if (!task.date_creation) return 0;
        const now = Math.floor(Date.now() / 1000);
        return Math.floor((now - task.date_creation) / (60 * 60 * 24));
    }

    function getPriorityColor(priority) {
        switch (priority) {
            case "Alta": return "red";
            case "Média": return "yellow";
            case "Baixa": return "green";
            default: return "muted";
        }
    }

    function getStatusColor(status) {
        switch (status) {
            case "Implementado": return "green";
            case "Aberta": return "blue";
            default: return "muted";
        }
    }

    function getAreaColor(area) {
        const colors = ["b-01", "b-02", "b-03", "b-04", "b-05", "b-06", "b-07", "b-08", "b-09", "b-10", "b-11"];
        let hash = 0;
        for (let i = 0; i < area.length; i++) {
            hash = area.charCodeAt(i) + ((hash << 5) - hash);
        }
        return colors[Math.abs(hash) % colors.length];
    }

    // Renderização dos KPIs
    function renderKPIs(filteredData) {
        console.log("renderKPIs() called with data:", filteredData);
        const totalDemandas = filteredData.length;
        const demandasAbertas = filteredData.filter(d => d.status === "Aberta").length;
        const demandasImplementadas = filteredData.filter(d => d.status === "Implementado").length;
        const valorTotal = filteredData.reduce((sum, d) => sum + (d.valor || 0), 0);
        const horasTotais = filteredData.reduce((sum, d) => sum + (d.horas || 0), 0);
        const mediaDiasEmFase = totalDemandas > 0 ? filteredData.reduce((sum, d) => sum + calculateDaysInPhase(d), 0) / totalDemandas : 0;

        const kpiTotalDemandasElement = document.getElementById("kpi-total-demandas");
        if (kpiTotalDemandasElement) {
            kpiTotalDemandasElement.innerText = totalDemandas;
        } else {
            console.error("Elemento kpi-total-demandas não encontrado.");
        }

        // Apenas para o test_index.html, o restante será implementado no index.html completo
        // document.getElementById("kpi-demandas-abertas").innerText = demandasAbertas;
        // document.getElementById("kpi-demandas-implementadas").innerText = demandasImplementadas;
        // document.getElementById("kpi-valor-total").innerText = formatCurrency(valorTotal);
        // document.getElementById("kpi-horas-totais").innerText = horasTotais.toFixed(0) + "h";
        // document.getElementById("kpi-media-dias-fase").innerText = mediaDiasEmFase.toFixed(1);
    }

    // Função principal de renderização
    const currentData = window.DATA || [];

    // Filtros (simplificados para o teste)
    const filterStatus = "all";
    const filterPriority = "all";
    const filterResponsible = "all";
    const filterArea = "all";
    const searchInput = "";

    let filteredData = currentData.filter(demand => {
        const matchesStatus = filterStatus === "all" || demand.status === filterStatus;
        const matchesPriority = filterPriority === "all" || demand.pri === filterPriority;
        const matchesResponsible = filterResponsible === "all" || demand.resp === filterResponsible;
        const matchesArea = filterArea === "all" || demand.area === filterArea;
        const matchesSearch = searchInput === "" || 
                              demand.title.toLowerCase().includes(searchInput) ||
                              demand.description.toLowerCase().includes(searchInput) ||
                              (demand.cherwell && demand.cherwell.toLowerCase().includes(searchInput)) ||
                              (demand.rdm && demand.rdm.toLowerCase().includes(searchInput));
        return matchesStatus && matchesPriority && matchesResponsible && matchesArea && matchesSearch;
    });

    // document.getElementById("filter-count").innerText = `${filteredData.length} demandas`;

    renderKPIs(filteredData);
    // As outras funções de renderização serão chamadas no index.html completo
    // renderPipeline(filteredData);
    // renderDemandTable(filteredData);
    // renderResponsibles(filteredData);
    // renderAreas(filteredData);
    // renderCharts(filteredData);
};

window.populateFilters = function(data) {
    console.log("populateFilters() called with data:", data);
    // Nenhuma lógica de filtro real para o teste mínimo
};

document.addEventListener("DOMContentLoaded", function() {
    console.log("DOMContentLoaded fired.");
    let attempts = 0;
    const maxAttempts = 50; // 5 segundos
    const interval = 100; // 100ms

    function checkDataAndRender() {
        console.log(`Attempt ${attempts + 1}/${maxAttempts}: Checking window.DATA...`);
        if (window.DATA && window.DATA.length > 0) {
            console.log("window.DATA found. Populating filters and rendering.");
            window.populateFilters(window.DATA);
            window.render();

            // Adicionar event listeners após a renderização inicial (apenas para o index.html completo)
            // document.getElementById("filter-status").addEventListener("change", window.render);
            // document.getElementById("filter-priority").addEventListener("change", window.render);
            // document.getElementById("filter-responsible").addEventListener("change", window.render);
            // document.getElementById("filter-area").addEventListener("change", window.render);
            // document.getElementById("search-input").addEventListener("keyup", window.render);
        } else if (attempts < maxAttempts) {
            attempts++;
            setTimeout(checkDataAndRender, interval);
        } else {
            console.error("Falha ao carregar os dados do dashboard (window.DATA) após 5 segundos.");
        }
    }

    checkDataAndRender();
});
