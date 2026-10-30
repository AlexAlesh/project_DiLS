/**
 * DiLS — основной скрипт страницы.
 */

(function () {
    'use strict';

    function getCsrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
        const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    function getJSON(url, params) {
        const query = new URLSearchParams(params || {}).toString();
        return fetch(url + (query ? '?' + query : ''), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        }).then(r => r.json());
    }

    function postForm(url, data) {
        const body = new FormData();
        for (const [k, v] of Object.entries(data)) {
            if (v !== undefined && v !== null) body.append(k, v);
        }
        return fetch(url, {
            method: 'POST',
            body: body,
            headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
        }).then(r => r.json());
    }

    // ============================================================
    // 1. Модалки создания справочников
    // ============================================================

    function initLookupCreateButtons() {
        document.querySelectorAll('[data-lookup-create]').forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                try {
                    const kind = btn.dataset.kind;
                    const nameInput = btn.dataset.nameInput ? document.querySelector(btn.dataset.nameInput) : null;
                    const phoneInput = btn.dataset.phoneInput ? document.querySelector(btn.dataset.phoneInput) : null;
                    const tcSource = btn.dataset.tcSource ? document.querySelector(btn.dataset.tcSource) : null;
                    const brandInput = btn.dataset.brandInput ? document.querySelector(btn.dataset.brandInput) : null;
                    const vtypeInput = btn.dataset.vehicleTypeInput ? document.querySelector(btn.dataset.vehicleTypeInput) : null;
                    const targetSelect = btn.dataset.targetSelect ? document.querySelector(btn.dataset.targetSelect) : null;
                    const modalClose = btn.dataset.modalClose ? document.querySelector(btn.dataset.modalClose) : null;

                    if (!nameInput) { alert('Не найдено поле наименования'); return; }
                    const name = nameInput.value.trim();
                    if (!name) { nameInput.focus(); return; }

                    const payload = { name };
                    if (phoneInput) payload.phone = phoneInput.value.trim();

                    if (kind === 'drivers' || kind === 'vehicles') {
                        if (!tcSource || !tcSource.value) { alert('Сначала выберите транспортную компанию в форме'); return; }
                        payload.transport_company = tcSource.value;
                    }

                    if (kind === 'vehicles') {
                        if (!brandInput || !brandInput.value) { alert('Выберите марку'); return; }
                        if (!vtypeInput || !vtypeInput.value) { alert('Выберите тип авто'); return; }
                        payload.brand = brandInput.value;
                        payload.vehicle_type = vtypeInput.value;
                    }

                    btn.disabled = true;
                    postForm('/ajax/create/' + kind + '/', payload)
                        .then(data => {
                            if (data.error) { alert('Ошибка: ' + data.error); return; }
                            if (targetSelect) {
                                if (targetSelect.tomselect) {
                                    targetSelect.tomselect.addOption({ value: data.id, text: data.text });
                                    targetSelect.tomselect.setValue(data.id);
                                } else {
                                    const opt = new Option(data.text, data.id, true, true);
                                    targetSelect.add(opt);
                                    targetSelect.value = String(data.id);
                                    targetSelect.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            }
                            if (modalClose) {
                                const bsModal = bootstrap.Modal.getInstance(modalClose);
                                if (bsModal) bsModal.hide();
                            }
                            nameInput.value = '';
                            if (phoneInput) phoneInput.value = '';
                        })
                        .catch(err => { console.error(err); alert('Ошибка сети'); })
                        .finally(() => { btn.disabled = false; });
                } catch (err) {
                    console.error('Ошибка в модалке:', err);
                }
            });
        });
    }

    // ============================================================
    // 2. Зависимые селекты в форме
    // ============================================================

    function initFormTomSelects() {
        if (typeof TomSelect === 'undefined') return;
        try {
            const selectors = ['id_transport_company', 'id_driver', 'id_vehicle', 'id_payment_type'];
            selectors.forEach(id => {
                const el = document.getElementById(id);
                if (el && !el.tomselect) {
                    new TomSelect(el, {
                        plugins: ['clear_button'],
                        placeholder: '— выберите —',
                        allowEmptyOption: true,
                    });
                }
            });
        } catch (e) {
            console.error('Ошибка TomSelect:', e);
        }
    }

    function syncDependentSelects() {
        try {
            const tcSelect = document.getElementById('id_transport_company');
            const driverSelect = document.getElementById('id_driver');
            const vehicleSelect = document.getElementById('id_vehicle');
            if (!tcSelect) return;

            const tcId = tcSelect.value;
            const clearSelect = (sel) => {
                if (sel && sel.tomselect) {
                    sel.tomselect.clearOptions();
                    sel.tomselect.clear();
                }
            };

            if (!tcId) {
                clearSelect(driverSelect);
                clearSelect(vehicleSelect);
                return;
            }

            const params = { transport_company: tcId };
            Promise.all([
                getJSON('/ajax/selects/drivers/', params),
                getJSON('/ajax/selects/vehicles/', params)
            ]).then(([drivers, vehicles]) => {
                const fill = (sel, items) => {
                    if (sel && sel.tomselect) {
                        items.forEach(it => sel.tomselect.addOption({ value: it.id, text: it.text }));
                        sel.tomselect.refreshOptions(false);
                    }
                };
                fill(driverSelect, drivers.results || []);
                fill(vehicleSelect, vehicles.results || []);
            });
        } catch (e) {
            console.error('Ошибка зависимых селектов:', e);
        }
    }

    function initLogistDependentSelects() {
        try {
            const form = document.querySelector('form[data-form-role="logist"]');
            if (!form) return;
            const tcSelect = document.getElementById('id_transport_company');
            if (!tcSelect) return;

            tcSelect.addEventListener('change', syncDependentSelects);
            if (tcSelect.value) syncDependentSelects();
        } catch (e) {
            console.error('Ошибка initLogistDependentSelects:', e);
        }
    }

    // ============================================================
    // 3. Модалка "Новая машина"
    // ============================================================

    function initVehicleCreateModal() {
        try {
            const modal = document.getElementById('createVehicleModal');
            if (!modal) return;
            modal.addEventListener('show.bs.modal', function () {
                const load = (selId, kind) => {
                    const sel = document.getElementById(selId);
                    if (!sel) return;
                    sel.innerHTML = '<option value="">— загрузка… —</option>';
                    getJSON('/ajax/search/' + kind + '/').then(data => {
                        sel.innerHTML = '<option value="">— выберите —</option>';
                        (data.results || []).forEach(it => sel.add(new Option(it.text, it.id)));
                    });
                };
                load('createVehicleBrand', 'brands');
                load('createVehicleType', 'vehicle-types');
            });
        } catch (e) {
            console.error('Ошибка модалки машины:', e);
        }
    }

    // ============================================================
    // 4. Графики
    // ============================================================

    function initChartToggles() {
        try {
            document.querySelectorAll('[data-chart-toggle]').forEach(btn => {
                btn.addEventListener('click', function () {
                    const target = document.getElementById(btn.dataset.chartToggle);
                    if (!target) return;
                    const hidden = target.classList.toggle('d-none');
                    btn.textContent = hidden ? 'показать' : 'скрыть';
                });
            });
        } catch (e) {}
    }

    // ============================================================
    // 5. Скрытие/показ сводки и фильтров
    // ============================================================

    function initVisibilityToggles() {
        try {
            const btnDash = document.getElementById('btn-toggle-dashboards');
            if (btnDash) {
                const isHidden = document.documentElement.classList.contains('dils-hide-dashboards');
                if (!isHidden) btnDash.classList.add('active');

                btnDash.addEventListener('click', function () {
                    const hidden = document.documentElement.classList.toggle('dils-hide-dashboards');
                    try { localStorage.setItem('dils_dashboards_hidden', hidden ? 'true' : 'false'); } catch(e){}
                    btnDash.classList.toggle('active', !hidden);
                });
            }

            const btnFilter = document.getElementById('btn-toggle-filters');
            if (btnFilter) {
                const isHidden = document.documentElement.classList.contains('dils-hide-filters');
                if (!isHidden) btnFilter.classList.add('active');

                btnFilter.addEventListener('click', function () {
                    const hidden = document.documentElement.classList.toggle('dils-hide-filters');
                    try { localStorage.setItem('dils_filters_hidden', hidden ? 'true' : 'false'); } catch(e){}
                    btnFilter.classList.toggle('active', !hidden);
                });
            }
        } catch (e) {
            console.error('Ошибка кнопок видимости:', e);
        }
    }

    // ============================================================
    // 6. Сайдбар
    // ============================================================

    function initSidebarToggle() {
        try {
            const btn = document.getElementById('btn-toggle-sidebar');
            if (!btn) return;
            btn.addEventListener('click', function () {
                const hidden = document.documentElement.classList.toggle('dils-hide-sidebar');
                try { localStorage.setItem('dils_sidebar_hidden', hidden ? 'true' : 'false'); } catch(e){}
            });
        } catch (e) {}
    }

    // ============================================================
    // 7. Двойной клик по карточке
    // ============================================================

    function initCardDoubleClick() {
        try {
            document.querySelectorAll('.trip-card[data-href]').forEach(card => {
                card.style.cursor = 'pointer';
                card.title = "Двойной клик для просмотра деталей";
                card.addEventListener('dblclick', function (e) {
                    if (e.target.closest('a, button, input, select, textarea, form')) return;
                    window.location.href = card.dataset.href;
                });
            });
        } catch (e) {}
    }

    // ============================================================
    // 8. Сохранение позиции скролла
    // ============================================================

    function initScrollRestoration() {
        try {
            const key = 'dils_scroll_' + window.location.pathname + window.location.search;
            const savedPos = sessionStorage.getItem(key);
            if (savedPos) {
                setTimeout(() => { window.scrollTo(0, parseInt(savedPos, 10)); }, 100);
            }
            window.addEventListener('scroll', function() {
                sessionStorage.setItem(key, window.scrollY);
            });
        } catch (e) {}
    }

    // ============================================================
    // 9. Подгрузка адресов заказчика
    // ============================================================

    function initCustomerAddresses() {
        const customerSelect = document.getElementById('id_customer');
        const deliveryInfo = document.getElementById('id_delivery_info');
        const container = document.getElementById('customer-addresses-container');
        const list = document.getElementById('customer-addresses-list');

        if (!customerSelect || !deliveryInfo || !container || !list) return;

        function loadAddresses(customerId) {
            if (!customerId) {
                container.classList.add('d-none');
                return;
            }

            fetch(`/ajax/customer/${customerId}/addresses/`)
                .then(r => r.json())
                .then(data => {
                    list.innerHTML = '';
                    if (data.addresses && data.addresses.length > 0) {
                        data.addresses.forEach(addr => {
                            const btn = document.createElement('button');
                            btn.type = 'button';
                            btn.className = 'btn btn-sm btn-light border text-start text-truncate';
                            btn.style.maxWidth = '100%';
                            btn.style.fontSize = '12px';
                            btn.innerHTML = `<i class="bi bi-geo-alt text-danger me-1"></i> ${addr}`;
                            btn.title = addr;
                            btn.addEventListener('click', function() {
                                deliveryInfo.value = addr;
                            });
                            list.appendChild(btn);
                        });
                        container.classList.remove('d-none');
                    } else {
                        container.classList.add('d-none');
                    }
                })
                .catch(err => {
                    console.error('Error loading addresses:', err);
                    container.classList.add('d-none');
                });
        }

        customerSelect.addEventListener('change', function() {
            loadAddresses(this.value);
        });

        if (customerSelect.value) {
            loadAddresses(customerSelect.value);
        }
    }

    // ============================================================
    // Запуск
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        initLookupCreateButtons();
        initFormTomSelects();
        initLogistDependentSelects();
        initVehicleCreateModal();
        initChartToggles();
        initVisibilityToggles();
        initSidebarToggle();
        initCardDoubleClick();
        initScrollRestoration();
        initCustomerAddresses(); // Подключаем адреса
    });

    window.DiLS = { getCsrfToken, getJSON, postForm };
})();