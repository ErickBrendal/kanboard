window.render = function() {
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
        const totalDemandas = filteredData.length;
        const demandasAbertas = filteredData.filter(d => d.status === "Aberta").length;
        const demandasImplementadas = filteredData.filter(d => d.status === "Implementado").length;
        const valorTotal = filteredData.reduce((sum, d) => sum + (d.valor || 0), 0);
        const horasTotais = filteredData.reduce((sum, d) => sum + (d.horas || 0), 0);
        const mediaDiasEmFase = totalDemandas > 0 ? filteredData.reduce((sum, d) => sum + calculateDaysInPhase(d), 0) / totalDemandas : 0;

        document.getElementById("kpi-total-demandas").innerText = totalDemandas;
        document.getElementById("kpi-demandas-abertas").innerText = demandasAbertas;
        document.getElementById("kpi-demandas-implementadas").innerText = demandasImplementadas;
        document.getElementById("kpi-valor-total").innerText = formatCurrency(valorTotal);
        document.getElementById("kpi-horas-totais").innerText = horasTotais.toFixed(0) + "h";
        document.getElementById("kpi-media-dias-fase").innerText = mediaDiasEmFase.toFixed(1);
    }

    // Renderização do Pipeline
    function renderPipeline(filteredData) {
        const pipelineData = {};
        filteredData.forEach(d => {
            pipelineData[d.fase] = (pipelineData[d.fase] || 0) + 1;
        });

        const pipelineStages = [
            "01. Backlog", "02. Refinamento", "03. Análise", "04. Aprovação", "05. Desenvolvimento", "06. Testes", "07. Deploy", "08. Implementado", "09. Cancelado"
        ];

        const totalDemandas = filteredData.length;

        const pipelineHtml = pipelineStages.map(stage => {
            const count = pipelineData[stage] || 0;
            const percentage = totalDemandas > 0 ? (count / totalDemandas) * 100 : 0;
            let stageClass = "";
            if (stage.includes("Implementado")) stageClass = "done";
            else if (stage.includes("Cancelado")) stageClass = "warn";
            else if (stage.includes("Desenvolvimento")) stageClass = "hl";

            return `
                <div class="pstage ${stageClass}">
                    <div class="pnum">${count}</div>
                    <div class="plabel">${stage.replace(/\d{2}\.\s/, "")}</div>
                    <div class="ppct">${percentage.toFixed(1)}%</div>
                </div>
            `;
        }).join("");
        document.getElementById("pipeline-overview").innerHTML = pipelineHtml;
    }

    // Renderização da Tabela de Demandas
    function renderDemandTable(filteredData) {
        const tableBody = document.getElementById("demand-table-body");
        tableBody.innerHTML = "";

        filteredData.forEach(demand => {
            const row = tableBody.insertRow();
            row.innerHTML = `
                <td>${demand.seq}</td>
                <td>${demand.cherwell}</td>
                <td>${demand.rdm}</td>
                <td class="tdtitle"><a href="${demand.url}" target="_blank">${demand.title}</a></td>
                <td>${demand.fase}</td>
                <td>${demand.resp}</td>
                <td>${demand.area}</td>
                <td>${demand.tipo}</td>
                <td><span class="badge b-${getPriorityColor(demand.pri)}">${demand.pri}</span></td>
                <td>${demand.golive || "N/A"}</td>
                <td>${formatCurrency(demand.valor)}</td>
                <td><span class="badge b-${getStatusColor(demand.status)}">${demand.status}</span></td>
            `;
        });
    }

    // Renderização dos Responsáveis
    function renderResponsibles(filteredData) {
        const responsibleCounts = {};
        filteredData.forEach(d => {
            responsibleCounts[d.resp] = (responsibleCounts[d.resp] || 0) + 1;
        });

        const totalDemandas = filteredData.length;

        const responsibleList = Object.entries(responsibleCounts)
            .sort((a, b) => b[1] - a[1])
            .map(([resp, count]) => {
                const percentage = totalDemandas > 0 ? (count / totalDemandas) * 100 : 0;
                const initial = resp.charAt(0).toUpperCase();
                return `
                    <div class="rcard">
                        <div class="ravatar" style="background:hsl(${initial.charCodeAt(0) * 10}, 70%, 50%);">${initial}</div>
                        <div class="rname">${resp}</div>
                        <div class="rtotal">${count} Demandas</div>
                        <div class="rbar-wrap">
                            <div class="rbar" style="width:${percentage}%; background:hsl(${initial.charCodeAt(0) * 10}, 70%, 50%);"></div>
                        </div>
                        <div class="rstat"><span>${percentage.toFixed(1)}%</span><span>${count}</span></div>
                    </div>
                `;
            }).join("");
        document.getElementById("responsible-grid").innerHTML = responsibleList;
    }

    // Renderização das Áreas Solicitantes
    function renderAreas(filteredData) {
        const areaCounts = {};
        filteredData.forEach(d => {
            areaCounts[d.area] = (areaCounts[d.area] || 0) + 1;
        });

        const totalDemandas = filteredData.length;

        const areaList = Object.entries(areaCounts)
            .sort((a, b) => b[1] - a[1])
            .map(([area, count]) => {
                const percentage = totalDemandas > 0 ? (count / totalDemandas) * 100 : 0;
                return `
                    <div class="area-item">
                        <div class="area-name">${area}</div>
                        <div class="area-track">
                            <div class="area-fill" style="width:${percentage}%;"></div>
                        </div>
                        <div class="area-count">${count}</div>
                    </div>
                `;
            }).join("");
        document.getElementById("area-list").innerHTML = areaList;
    }

    // Renderização dos Gráficos (Chart.js)
    function renderCharts(filteredData) {
        // Distribuição por Fase (Bar Chart)
        const faseCounts = {};
        filteredData.forEach(d => {
            faseCounts[d.fase] = (faseCounts[d.fase] || 0) + 1;
        });
        const sortedFases = Object.entries(faseCounts).sort((a, b) => b[1] - a[1]);
        const barChartLabels = sortedFases.map(item => item[0]);
        const barChartData = sortedFases.map(item => item[1]);

        new Chart(document.getElementById("faseBarChart"), {
            type: "bar",
            data: {
                labels: barChartLabels,
                datasets: [{
                    data: barChartData,
                    backgroundColor: "rgba(79, 110, 247, 0.8)",
                    borderColor: "rgba(79, 110, 247, 1)",
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                plugins: {
                    legend: { display: false },
                    title: { display: false }
                },
                scales: {
                    x: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.1)" }, ticks: { color: "#e2e8f0" } },
                    y: { grid: { color: "rgba(255,255,255,0.1)" }, ticks: { color: "#e2e8f0" } }
                }
            }
        });

        // Distribuição por Prioridade (Donut Chart)
        const priCounts = {};
        filteredData.forEach(d => {
            priCounts[d.pri] = (priCounts[d.pri] || 0) + 1;
        });
        const donutChartLabels = Object.keys(priCounts);
        const donutChartData = Object.values(priCounts);
        const donutChartColors = donutChartLabels.map(pri => {
            switch (pri) {
                case "Alta": return "#ef4444";
                case "Média": return "#f59e0b";
                case "Baixa": return "#22c55e";
                default: return "#8892b0";
            }
        });

        new Chart(document.getElementById("prioridadeDonutChart"), {
            type: "doughnut",
            data: {
                labels: donutChartLabels,
                datasets: [{
                    data: donutChartData,
                    backgroundColor: donutChartColors,
                    borderColor: "#0f1117",
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: false }
                }
            }
        });

        // Status Geral (Donut Chart)
        const statusCounts = {};
        filteredData.forEach(d => {
            statusCounts[d.status] = (statusCounts[d.status] || 0) + 1;
        });
        const statusDonutLabels = Object.keys(statusCounts);
        const statusDonutData = Object.values(statusCounts);
        const statusDonutColors = statusDonutLabels.map(status => {
            switch (status) {
                case "Implementado": return "#22c55e";
                case "Aberta": return "#4f6ef7";
                default: return "#8892b0";
            }
        });

        new Chart(document.getElementById("statusDonutChart"), {
            type: "doughnut",
            data: {
                labels: statusDonutLabels,
                datasets: [{
                    data: statusDonutData,
                    backgroundColor: statusDonutColors,
                    borderColor: "#0f1117",
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: false }
                }
            }
        });
    }

    // Função principal de renderização
    const currentData = window.DATA || [];
    const totalDemandas = currentData.length;

    // Filtros
    const filterStatus = document.getElementById("filter-status").value;
    const filterPriority = document.getElementById("filter-priority").value;
    const filterResponsible = document.getElementById("filter-responsible").value;
    const filterArea = document.getElementById("filter-area").value;
    const searchInput = document.getElementById("search-input").value.toLowerCase();

    let filteredData = currentData.filter(demand => {
        const matchesStatus = filterStatus === "all" || demand.status === filterStatus;
        const matchesPriority = filterPriority === "all" || demand.pri === filterPriority;
        const matchesResponsible = filterResponsible === "all" || demand.resp === filterResponsible;
        const matchesArea = filterArea === "all" || demand.area === filterArea;
        const matchesSearch = searchInput === "" || 
                              demand.title.toLowerCase().includes(searchInput) ||
                              demand.description.toLowerCase().includes(searchInput) ||
                              demand.cherwell.toLowerCase().includes(searchInput) ||
                              demand.rdm.toLowerCase().includes(searchInput);
        return matchesStatus && matchesPriority && matchesResponsible && matchesArea && matchesSearch;
    });

    document.getElementById("filter-count").innerText = `${filteredData.length} demandas`;

    renderKPIs(filteredData);
    renderPipeline(filteredData);
    renderDemandTable(filteredData);
    renderResponsibles(filteredData);
    renderAreas(filteredData);
    renderCharts(filteredData);
};

window.populateFilters = function(data) {
    const statuses = [...new Set(data.map(d => d.status))];
    const priorities = [...new Set(data.map(d => d.pri))];
    const responsibles = [...new Set(data.map(d => d.resp))];
    const areas = [...new Set(data.map(d => d.area))];

    const createOptions = (selectId, items) => {
        const select = document.getElementById(selectId);
        select.innerHTML = 
        `<option value="all">Todos</option>`;
        items.sort().forEach(item => {
            if (item && item !== "N/A") {
                const option = document.createElement("option");
                option.value = item;
                option.innerText = item;
                select.appendChild(option);
            }
        });
    };

    createOptions("filter-status", statuses);
    createOptions("filter-priority", priorities);
    createOptions("filter-responsible", responsibles);
    createOptions("filter-area", areas);

    // Ativar abas
    document.querySelectorAll(".tab").forEach(tab => {
        tab.addEventListener("click", function() {
            document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            this.classList.add("active");
            document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
            document.getElementById(this.dataset.page).classList.add("active");
        });
    });

    // Ativar a primeira aba por padrão
    document.querySelector(".tab").click();
};

document.addEventListener("DOMContentLoaded", function() {
    let attempts = 0;
    const maxAttempts = 50; // 5 segundos
    const interval = 100; // 100ms

    function checkDataAndRender() {
        if (window.DATA && window.DATA.length > 0) {
            window.populateFilters(window.DATA);
            window.render();

            // Adicionar event listeners após a renderização inicial
            document.getElementById("filter-status").addEventListener("change", window.render);
            document.getElementById("filter-priority").addEventListener("change", window.render);
            document.getElementById("filter-responsible").addEventListener("change", window.render);
            document.getElementById("filter-area").addEventListener("change", window.render);
            document.getElementById("search-input").addEventListener("keyup", window.render);
        } else if (attempts < maxAttempts) {
            attempts++;
            setTimeout(checkDataAndRender, interval);
        } else {
            console.error("Falha ao carregar os dados do dashboard (window.DATA) após 5 segundos.");
        }
    }

    checkDataAndRender();
});
