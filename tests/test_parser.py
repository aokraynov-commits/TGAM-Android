"""Тесты парсера протокола TGAM."""

import pytest

from tgam_monitor.parser import TGAMParser


def make_packet(payload: bytes) -> bytes:
    """Собрать корректный пакет TGAM: 0xAA 0xAA len payload checksum."""
    checksum = (255 - sum(payload)) & 0xFF
    return bytes([0xAA, 0xAA, len(payload)]) + payload + bytes([checksum])


def collect_packets(stream: bytes):
    packets = []
    parser = TGAMParser(callback=packets.append)
    parser.feed(stream)
    return packets


def test_valid_attention_meditation_packet():
    payload = bytes([0x04, 80, 0x05, 30])
    (data,) = collect_packets(make_packet(payload))
    assert data == {"attention": 80, "meditation": 30}


def test_only_attention():
    payload = bytes([0x04, 55])
    (data,) = collect_packets(make_packet(payload))
    assert data == {"attention": 55}


def test_only_meditation():
    payload = bytes([0x05, 44])
    (data,) = collect_packets(make_packet(payload))
    assert data == {"meditation": 44}


def test_bad_checksum_is_ignored():
    packet = bytearray(make_packet(bytes([0x04, 80])))
    packet[-1] ^= 0xFF  # испорченный checksum
    assert collect_packets(bytes(packet)) == []


def test_payload_with_unknown_prefix_bytes():
    # типичный пакет TGAM: 0x80 raw eeg, 0x83 EEG power, затем attention/meditation
    payload = bytes([0x02, 0x80, 0x02, 0x01, 0x04, 66, 0x05, 22])
    (data,) = collect_packets(make_packet(payload))
    assert data == {"attention": 66, "meditation": 22}


def test_garbage_before_sync_is_skipped():
    stream = bytes([0x01, 0x02, 0xAA, 0x03]) + make_packet(bytes([0x04, 70]))
    (data,) = collect_packets(stream)
    assert data == {"attention": 70}


def test_too_long_payload_resyncs():
    bad_header = bytes([0xAA, 0xAA, 200])  # длина > 169 — отбрасываем
    stream = bad_header + make_packet(bytes([0x04, 12]))
    (data,) = collect_packets(stream)
    assert data == {"attention": 12}


def test_feed_accepts_int_and_bytes():
    received = []
    parser = TGAMParser(callback=received.append)
    packet = make_packet(bytes([0x04, 90]))
    for b in packet[:-1]:
        parser.feed(b)          # по байту как int
    parser.feed(packet[-1:])    # финальный байт как bytes
    assert received == [{"attention": 90}]


def test_no_callback_does_not_crash():
    parser = TGAMParser()
    parser.feed(make_packet(bytes([0x04, 10])))  # не должно быть исключения


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
