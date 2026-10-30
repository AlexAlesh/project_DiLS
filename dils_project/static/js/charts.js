/**
 * DiLS — графики отчётов на Chart.js.
 *
 * Подключается только на странице /reports/.
 *
 * Chart.js подгружается динамически (CDN) при первом запуске, чтобы
 * не тащить его в base.html для всех страниц.
 *
 * Источник данных — контейнер #dils-charts-container с data-атрибутами:
 *   data-cash, data-cashless, data-total, data-count
 */

(function () {
    'use strict';

    const CHART_CDN = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';

    // ============================================================
    // Загрузка Chart.js по требованию
    // ============================================================

    function ensureChartJs() {
        return new Promise((resolve, reject) => {
            if (window.Chart) return resolve(window.Chart);

            const existing = document.querySelector('script[data-chartjs]');
            if (existing) {
                existing.addEventListener('load', () => resolve(window.Chart));
                existing.addEventListener('error', reject);
                return;
            }

            const s = document.createElement('script');
            s.src = CHART_CDN;
            s.async = true;
            s.dataset.chartjs = '1';
            s.onload = () => resolve(window.Chart);
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    // ============================================================
    // Парсинг чисел из data-атрибутов
    // ============================================================

    function toNumber(value) {
        if (!value) return 0;
        const cleaned = String(value).replace(/\s+/g, '').replace(',', '.');
        const n = parseFloat(cleaned);
        return isFinite(n) ? n : 0;
    }

    function formatMoneyShort(value) {
        const n = toNumber(value);
        if (n >= 1e6) return (n / 1e6).toFixed(2) + ' млн ₽';
        if (n >= 1e3) return (n / 1e3).toFixed(1) + ' тыс ₽';
        return n.toFixed(2) + ' ₽';
    }

    // ============================================================
    // График: распределение по типу оплаты
    // ============================================================

    function renderPaymentChart(container) {
        const canvas = document.getElementById('chart-payment-type');
        if (!canvas) return;

        const cash = toNumber(container.dataset.cash);
        const cashless = toNumber(container.dataset.cashless);

        const emptyEl = container.querySelector('[data-chart-empty]');

        if (cash === 0 && cashless === 0) {
            canvas.classList.add('d-none');
            if (emptyEl) emptyEl.classList.remove('d-none');
            return;
        }

        ensureChartJs().then(Chart => {
            if (canvas._dilsChart) canvas._dilsChart.destroy();

            canvas._dilsChart = new Chart(canvas.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: ['Наличные', 'Безналичные'],
                    datasets: [{
                        data: [cash, cashless],
                        backgroundColor: [
                            'rgba(25, 135, 84, 0.85)',
                            'rgba(13, 110, 253, 0.85)',
                        ],
                        borderColor: [
                            'rgba(25, 135, 84, 1)',
                            'rgba(13, 110, 253, 1)',
                        ],
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    return ctx.label + ': ' +
                                        formatMoneyShort(ctx.parsed);
                                },
                            },
                        },
                    },
                    cutout: '55%',
                },
            });
        }).catch(err => {
            console.error('Chart.js load failed', err);
        });
    }

    // ============================================================
    // Запуск
    // ============================================================

    function init() {
        const container = document.getElementById('dils-charts-container');
        if (!container) return;

        renderPaymentChart(container);

        // Перерисовка при возврате видимости (на случай скрытой карточки)
        document.querySelectorAll('[data-chart-toggle]').forEach(btn => {
            btn.addEventListener('click', function () {
                // Chart.js плохо рендерится, если canvas был hidden при init.
                // После показа — перерисовываем.
                setTimeout(() => renderPaymentChart(container), 50);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', init);
})();