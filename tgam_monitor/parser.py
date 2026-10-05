"""Парсер протокола NeuroSky TGAM (MindWave).

Основан на оригинальном коде Arduino: из payload извлекаются значения
Attention (код 0x04) и Meditation (код 0x05), остальное игнорируется.

Реализован конечный автомат приёма пакетов:
    SYNC -> SYNC2 -> LENGTH -> PAYLOAD -> CHECKSUM
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

SYNC_BYTE = 0xAA
MAX_PAYLOAD_LENGTH = 169

CODE_ATTENTION = 0x04
CODE_MEDITATION = 0x05


class TGAMParser:
    """Парсер байтового потока TGAM в структурированные данные.

    :param callback: вызывается для каждого корректного пакета со словарём
        ``{'attention': int, 'meditation': int}`` (ключи добавляются только
        если соответствующее значение найдено в payload).
    """

    def __init__(self, callback: Optional[Callable[[Dict[str, int]], None]] = None):
        self.callback = callback
        self.state = "SYNC"
        self.payload_length = 0
        self.payload = bytearray()
        self.generated_checksum = 0
        self.checksum = 0

    # ------------------------------------------------------------------ API
    def feed(self, data) -> None:
        """Скармливать парсеру байты (int или последовательность байт)."""
        if isinstance(data, int):
            data = bytes([data])
        for byte in data:
            self._parse_byte(byte)

    # ------------------------------------------------------- конечный автомат
    def _parse_byte(self, byte: int) -> None:
        if self.state == "SYNC":
            if byte == SYNC_BYTE:
                self.state = "SYNC2"
        elif self.state == "SYNC2":
            if byte == SYNC_BYTE:
                self.state = "LENGTH"
            else:
                self.state = "SYNC"
        elif self.state == "LENGTH":
            self.payload_length = byte
            if self.payload_length > MAX_PAYLOAD_LENGTH:
                self.state = "SYNC"
            else:
                self.payload = bytearray()
                self.generated_checksum = 0
                self.state = "PAYLOAD"
        elif self.state == "PAYLOAD":
            self.payload.append(byte)
            self.generated_checksum += byte
            if len(self.payload) >= self.payload_length:
                self.state = "CHECKSUM"
        elif self.state == "CHECKSUM":
            self.checksum = byte
            self._finalize_packet()
            self.state = "SYNC"
        else:  # pragma: no cover - защитная ветка
            self.state = "SYNC"

    # -------------------------------------------------------------- пакет
    def _finalize_packet(self) -> None:
        computed = (255 - self.generated_checksum) & 0xFF
        if computed != self.checksum:
            return

        values = self._extract_values(self.payload)
        if values and self.callback is not None:
            self.callback(values)

    @staticmethod
    def _extract_values(payload: bytearray) -> Dict[str, int]:
        """Упрощённый разбор payload: ищем коды 0x04/0x05 и следующие байты."""
        attention: Optional[int] = None
        meditation: Optional[int] = None

        i = 0
        length = len(payload)
        while i < length - 1:  # нужно минимум 2 байта: код и значение
            code = payload[i]
            if code == CODE_ATTENTION:
                attention = payload[i + 1]
                i += 2
            elif code == CODE_MEDITATION:
                meditation = payload[i + 1]
                i += 2
            else:
                i += 1  # пропускаем неизвестный байт

        data: Dict[str, int] = {}
        if attention is not None:
            data["attention"] = attention
        if meditation is not None:
            data["meditation"] = meditation
        return data
