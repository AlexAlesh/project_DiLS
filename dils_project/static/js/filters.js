/**
 * DiLS — работа с фильтрами (Tom Select + AJAX)
 */

(function () {
    'use strict';

    // ============================================================
    // 1. Автозаполнение из URL
    // ============================================================

    function initFilterPrefill() {
        const form = document.getElementById('dils-filters-form');
        if (!form) return;

        const params = new URLSearchParams(window.location.search);

        form.querySelectorAll('[data-filter-key]').forEach(input => {
            const key = input.dataset.filterKey;
            const part = input.dataset.filterPart;
            const isMulti = input.hasAttribute('multiple');

            let paramName = key;
            if (part) {
                paramName = key + '_' + part;
            }

            if (input.tagName === 'SELECT' && !isMulti) {
                let value = params.get(paramName);
                if (value === null && input.dataset.defaultValue) {
                    value = input.dataset.defaultValue;
                }
                if (value !== null) input.value = value;
            } else if (!isMulti) {
                const value = params.get(paramName);
                if (value !== null) input.value = value;
            }
        });
    }

    // ============================================================
    // 2. Инициализация Tom Select (с галочками и кнопкой очистки)
    // ============================================================

    function initTomSelect() {
        const selects = document.querySelectorAll('.dils-multi-select');
        const params = new URLSearchParams(window.location.search);

        selects.forEach(el => {
            const ts = new TomSelect(el, {
                // Включаем все нужные плагины:
                // checkbox_options — галочки в выпадающем списке
                // remove_button    — крестик на каждой выбранной плашке
                // clear_button     — общая кнопка сброса "×" в поле ввода
                plugins: ['checkbox_options', 'remove_button', 'clear_button'],
                placeholder: el.name === 'manager' && el.dataset.defaultValue ? '' : 'Все',
                allowEmptyOption: true,
                maxItems: null,
                hideSelected: false, // Не скрывать выбранные из списка, чтобы галочки были видны
                closeAfterSelect: false, // Не закрывать список после выбора (удобно для мультивыбора)
                onChange: function (values) {
                    if (el.name === 'transport_company') {
                        updateDriversByTC(values);
                    }
                }
            });

            // Восстанавливаем выбранные из URL
            const selectedValues = params.getAll(el.name);
            if (selectedValues.length > 0) {
                ts.setValue(selectedValues);
            } else if (el.dataset.defaultValue) {
                ts.setValue(el.dataset.defaultValue);
            }
        });

        // Первичная загрузка водителей, если ТК уже выбрано
        const tcSelect = document.querySelector('select[name="transport_company"]');
        if (tcSelect && tcSelect.tomselect) {
            const selectedTCs = tcSelect.tomselect.getValue();
            if (selectedTCs.length > 0) {
                updateDriversByTC(selectedTCs);
            }
        }
    }

    // ============================================================
    // 3. Связка: ТК -> Водители
    // ============================================================

    function updateDriversByTC(tcValues) {
        const driverSelect = document.querySelector('select[name="driver"]');
        if (!driverSelect || !driverSelect.tomselect) return;

        const driverTs = driverSelect.tomselect;

        // Запоминаем, что было выбрано (чтобы попытаться сохранить выбор)
        const prevSelected = driverTs.getValue();

        driverTs.clearOptions();
        driverTs.clear();

        if (!tcValues || tcValues.length === 0) {
            return;
        }

        const params = new URLSearchParams();
        const valuesArray = Array.isArray(tcValues) ? tcValues : [tcValues];
        valuesArray.forEach(v => params.append('transport_company', v));

        fetch('/ajax/selects/drivers/?' + params.toString())
            .then(r => r.json())
            .then(data => {
                data.results.forEach(item => {
                    driverTs.addOption({ value: item.id, text: item.text });
                });

                // Пытаемся восстановить ранее выбранные значения, если они есть в новом списке
                const availableIds = data.results.map(r => String(r.id));
                const stillAvailable = prevSelected.filter(id => availableIds.includes(String(id)));
                if (stillAvailable.length > 0) {
                    driverTs.setValue(stillAvailable);
                }

                driverTs.refreshOptions(false);
            })
            .catch(err => console.error('Ошибка загрузки водителей:', err));
    }

    // ============================================================
    // 4. Сохранение настроек (без изменений)
    // ============================================================

    function getCsrfToken() {
        if (window.DiLS && window.DiLS.getCsrfToken) return window.DiLS.getCsrfToken();
        const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    function collectCheckedValues(modalRoot, field) {
        const values = [];
        (modalRoot || document).querySelectorAll(
            '[data-pref-field="' + field + '"][data-pref-key]'
        ).forEach(input => {
            if (input.checked) values.push(input.dataset.prefKey);
        });
        return values;
    }

    function savePreferences(page, field, values) {
        return fetch('/ajax/preferences/save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ page, field, values }),
        }).then(async r => await r.json());
    }

    function initPrefSaveButtons() {
        document.querySelectorAll('[data-pref-save]').forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                const page = btn.dataset.prefPage;
                const field = btn.dataset.prefField;
                if (!page || !field) return;

                const modalEl = btn.closest('.modal');
                const values = collectCheckedValues(modalEl, field);

                btn.disabled = true;
                savePreferences(page, field, values)
                    .then(data => {
                        if (data.error) alert('Ошибка: ' + data.error);
                        else window.location.reload();
                    })
                    .catch(() => alert('Ошибка сети'))
                    .finally(() => { btn.disabled = false; });
            });
        });
    }

    // ============================================================
    // Запуск
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        initFilterPrefill();
        initTomSelect();
        initPrefSaveButtons();
    });
})();