package dev.tgam.parser;

/**
 * Копия логики Python-скрипта tgam_monitor для Android.
 *
 * Управляет только приёмом данных NeuroSky TGAM (MindWave): конечный автомат
 * пакетов SYNC -> SYNC2 -> LENGTH -> PAYLOAD -> CHECKSUM и извлечение
 * Attention (0x04) / Meditation (0x05).
 *
 * Управление мышью намеренно НЕ портировано — на Android оно не имеет смысла
 * и удалено из обоих скриптов.
 */
public final class TGamParser {

    public static final int SYNC_BYTE = 0xAA;
    public static final int MAX_PAYLOAD_LENGTH = 169;
    public static final int CODE_ATTENTION = 0x04;
    public static final int CODE_MEDITATION = 0x05;

    /** Состояния конечного автомата (совпадают с Python-версией). */
    private enum State { SYNC, SYNC2, LENGTH, PAYLOAD, CHECKSUM }

    /** Приём структурированного пакета (значения могут отсутствовать). */
    public interface PacketListener {
        /**
         * @param attention  значение Attention или {@code null}, если не найдено
         * @param meditation значение Meditation или {@code null}, если не найдено
         */
        void onPacket(Integer attention, Integer meditation);
    }

    private final PacketListener listener;

    private State state = State.SYNC;
    private int payloadLength = 0;
    private final byte[] payload = new byte[MAX_PAYLOAD_LENGTH];
    private int payloadSize = 0;
    private int generatedChecksum = 0;
    private int checksum = 0;

    public TGamParser() {
        this(null);
    }

    public TGamParser(PacketListener listener) {
        this.listener = listener;
    }

    /** Сброс автомата в исходное состояние. */
    public void reset() {
        state = State.SYNC;
        payloadLength = 0;
        payloadSize = 0;
        generatedChecksum = 0;
        checksum = 0;
    }

    /** Скармливать парсеру байты потока (аналог feed(data)). */
    public void feed(byte[] data) {
        if (data == null) {
            return;
        }
        for (byte b : data) {
            parseByte(b & 0xFF);
        }
    }

    /** Скармливать парсеру один байт (аналог feed(int)). */
    public void feed(int unsignedByte) {
        parseByte(unsignedByte & 0xFF);
    }

    // ------------------------------------------------ конечный автомат
    private void parseByte(int byteValue) {
        switch (state) {
            case SYNC:
                if (byteValue == SYNC_BYTE) {
                    state = State.SYNC2;
                }
                break;

            case SYNC2:
                state = (byteValue == SYNC_BYTE) ? State.LENGTH : State.SYNC;
                break;

            case LENGTH:
                payloadLength = byteValue;
                if (payloadLength > MAX_PAYLOAD_LENGTH) {
                    state = State.SYNC;
                } else {
                    // len == 0 допустим: автомат сразу ждёт контрольную сумму
                    state = (payloadLength == 0) ? State.CHECKSUM : State.PAYLOAD;
                    payloadSize = 0;
                    generatedChecksum = 0;
                }
                break;

            case PAYLOAD:
                payload[payloadSize++] = (byte) byteValue;
                generatedChecksum += byteValue;
                if (payloadSize >= payloadLength) {
                    state = State.CHECKSUM;
                }
                break;

            case CHECKSUM:
                checksum = byteValue;
                finalizePacket();
                state = State.SYNC;
                break;

            default:
                state = State.SYNC;
                break;
        }
    }

    // ------------------------------------------------------------ пакет
    private void finalizePacket() {
        int computed = (~generatedChecksum) & 0xFF; // 255 - sum, по модулю 256
        if (computed != checksum) {
            return;
        }
        Integer attention = null;
        Integer meditation = null;

        // Упрощённый разбор payload: ищем коды 0x04/0x05 и следующие байты.
        // Байт длины блока (как в Python-версии) не пропускается — он просто
        // не совпадает с кодами значений.
        int i = 0;
        while (i < payloadSize - 1) {
            int code = payload[i] & 0xFF;
            if (code == CODE_ATTENTION) {
                attention = payload[i + 1] & 0xFF;
                i += 2;
            } else if (code == CODE_MEDITATION) {
                meditation = payload[i + 1] & 0xFF;
                i += 2;
            } else {
                i += 1; // пропускаем неизвестный байт
            }
        }

        if ((attention != null || meditation != null) && listener != null) {
            listener.onPacket(attention, meditation);
        }
    }
}
