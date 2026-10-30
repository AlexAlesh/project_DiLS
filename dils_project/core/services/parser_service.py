"""
Сервис парсинга «Информация по доставке».

Отдельный модуль под будущий парсер. Сейчас — заглушка.

Идея:
- На вход — свободный текст (например, скопированный из заявки).
- На выход — структурированные данные:
    {
        'loading_address': str,
        'unloading_address': str,
        'cargo': str,
        'weight_kg': Decimal | None,
        'volume_m3': Decimal | None,
        'contact_phone': str,
    }

Пока возвращает пустой результат — чтобы Trip.delivery_info
оставался текстом, как есть.
"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class ParsedDeliveryInfo:
    """Результат парсинга информации по доставке."""
    raw: str = ""
    loading_address: str = ""
    unloading_address: str = ""
    cargo: str = ""
    weight_kg: Decimal | None = None
    volume_m3: Decimal | None = None
    contact_phone: str = ""
    extra: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not any([
            self.loading_address, self.unloading_address,
            self.cargo, self.weight_kg, self.volume_m3,
            self.contact_phone,
        ])


def parse_delivery_info(raw_text: str) -> ParsedDeliveryInfo:
    """
    Точка входа парсера.

    Пока — заглушка. В будущем здесь будет:
    - NLP / regex-разбор адресов
    - нормализация телефонов
    - вытаскивание веса и объёма

    :param raw_text: свободный текст из формы
    :return: ParsedDeliveryInfo
    """
    if not raw_text:
        return ParsedDeliveryInfo()

    return ParsedDeliveryInfo(raw=raw_text)