/**
 * DiLS — автоформат гос. номера.
 *
 * Применяется к любому <input data-plate-input>.
 * Правила (те же, что и format_plate_number() в core/models.py):
 * - Убираем пробелы
 * - Латиницу → кириллицу (A→А, B→В, E→Е, K→К, M→М, H→Н, O→О, P→Р,
 *   C→С, T→Т, Y→У, X→Х)
 * - Формат: Б 123 ББ 456
 * - Если паттерн не полный — оставляем как есть (не мешаем пользователю
 *   вводить посимвольно)
 */

(function () {
    'use strict';

    const LATIN_TO_CYRILLIC = {
        'A': 'А', 'B': 'В', 'E': 'Е', 'K': 'К', 'M': 'М',
        'H': 'Н', 'O': 'О', 'P': 'Р', 'C': 'С', 'T': 'Т',
        'Y': 'У', 'X': 'Х',
    };

    function normalize(value) {
        if (!value) return '';
        return value
            .split('')
            .map(ch => {
                const upper = ch.toUpperCase();
                return LATIN_TO_CYRILLIC[upper] || upper;
            })
            .join('')
            .replace(/\s+/g, '');
    }

    function formatPlate(value) {
        const cleaned = normalize(value);
        const match = cleaned.match(/^([А-Я])(\d{3})([А-Я]{2})(\d{2,3})$/);
        if (match) {
            return match[1] + ' ' + match[2] + ' ' + match[3] + ' ' + match[4];
        }
        // Мягкий формат на лету, пока пользователь печатает:
        // группируем по 1 / 3 / 2 / 2-3
        const m = cleaned.match(/^([А-Я])(\d{0,3})([А-Я]{0,2})(\d{0,3})$/);
        if (m) {
            const parts = [m[1], m[2], m[3], m[4]].filter(Boolean);
            return parts.join(' ');
        }
        return cleaned;
    }

    function applyFormat(input) {
        // Сохраняем позицию курсора после форматирования
        const start = input.selectionStart || 0;
        const beforeLength = input.value.length;

        const formatted = formatPlate(input.value);
        if (formatted !== input.value) {
            input.value = formatted;
            const diff = formatted.length - beforeLength;
            try {
                input.setSelectionRange(start + diff, start + diff);
            } catch (e) {
                // ignore
            }
        }
    }

    function initPlateInputs() {
        document.querySelectorAll('[data-plate-input]').forEach(input => {
            // Форматируем текущее значение при загрузке
            if (input.value) {
                const formatted = formatPlate(input.value);
                if (formatted !== input.value) {
                    input.value = formatted;
                }
            }

            input.addEventListener('input', function () {
                applyFormat(input);
            });

            // При потере фокуса — финальный формат
            input.addEventListener('blur', function () {
                const formatted = formatPlate(input.value);
                if (formatted !== input.value) {
                    input.value = formatted;
                }
            });
        });
    }

    // Экспорт для использования из других скриптов
    window.DiLSPlate = { formatPlate, normalize };

    document.addEventListener('DOMContentLoaded', initPlateInputs);
})();