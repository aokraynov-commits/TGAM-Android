package dev.tgam.parser;

import java.io.ByteArrayOutputStream;

/**
 * Self-test парсера (запуск: javac + java, без JUnit).
 * Проверяет те же свойства, что pytest-тесты Python-версии.
 */
public class TGamParserTest {

    private static int passed = 0;
    private static int failed = 0;

    public static void main(String[] args) {
        testValidPacketWithBothValues();
        testValidAttentionOnlyPacket();
        testBadChecksumIsIgnored();
        testResyncAfterGarbage();
        testTooLongPayloadIsRejected();
        testEmptyPayloadNoCallback();
        testMultiplePacketsInStream();

        System.out.println("PASSED=" + passed + " FAILED=" + failed);
        if (failed > 0) {
            System.exit(1);
        }
    }

    // ---------------------------------------------------------- утилиты
    /**
     * Строит корректный пакет: AA AA len payload... checksum.
     * ВНИМАНИЕ: байты передаются как есть (Python-совместимый разбор),
     * поэтому значения должны быть <= 127 (знайные байты Java!).
     */
    private static byte[] rawPacket(int... payloadBytes) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(TGamParser.SYNC_BYTE);
        out.write(TGamParser.SYNC_BYTE);
        out.write(payloadBytes.length);
        int sum = 0;
        for (int b : payloadBytes) {
            out.write(b);
            sum += b;
        }
        out.write((~sum) & 0xFF);
        return out.toByteArray();
    }

    /**
     * Блок данных TGAM: код, длина, valueLen байт значения (little-endian).
     * Attention/Meditation имеют длину 1 — разбор Python-версии читает
     * следующий байт после кода именно поэтому.
     */
    private static int[] block(int code, int value) {
        return new int[]{code, 0x01, value};
    }

    /** Пакет из блоков (payload собирается конкатенацией). */
    private static byte[] packet(int[]... blocks) {
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        for (int[] b : blocks) {
            for (int v : b) {
                body.write(v);
            }
        }
        // toByteArray() возвращает byte[] -> конвертируем в int[] для rawPacket
        byte[] bytes = body.toByteArray();
        int[] asInts = new int[bytes.length];
        for (int i = 0; i < bytes.length; i++) {
            asInts[i] = bytes[i] & 0xFF;
        }
        return rawPacket(asInts);
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(String.format("%02X ", b));
        }
        return sb.toString().trim();
    }

    /** Парсер, собирающий все вызовы onPacket в строку-лог. */
    private static final class Recorder implements TGamParser.PacketListener {
        final StringBuilder log = new StringBuilder();

        @Override
        public void onPacket(Integer attention, Integer meditation) {
            log.append("A=").append(attention).append(",M=").append(meditation).append(";");
        }
    }

    private static void check(String name, boolean condition) {
        if (condition) {
            passed++;
            System.out.println("ok   " + name);
        } else {
            failed++;
            System.out.println("FAIL " + name);
        }
    }

    // ------------------------------------------------------------ тесты
    private static void testValidPacketWithBothValues() {
        Recorder r = new Recorder();
        TGamParser p = new TGamParser(r);
        // блоки: EEG 0x02 (2 байта), Attention=80, Meditation=30
        p.feed(packet(new int[]{0x02, 0x02, 0x00, 0x80}, block(0x04, 80), block(0x05, 30)));
        check("valid packet -> A=80 M=30", r.log.toString().equals("A=80,M=30;"));
    }

    private static void testValidAttentionOnlyPacket() {
        Recorder r = new Recorder();
        TGamParser p = new TGamParser(r);
        p.feed(packet(block(0x04, 55)));
        check("attention only -> M=null", r.log.toString().equals("A=55,M=null;"));
    }

    private static void testBadChecksumIsIgnored() {
        Recorder r = new Recorder();
        TGamParser p = new TGamParser(r);
        byte[] bad = packet(block(0x04, 55));
        bad[bad.length - 1] ^= 0x55; // портим контрольную сумму
        p.feed(bad);
        check("bad checksum ignored", r.log.length() == 0);
    }

    private static void testResyncAfterGarbage() {
        Recorder r = new Recorder();
        TGamParser p = new TGamParser(r);
        p.feed(new byte[]{0x01, 0x02, 0x03, (byte) 0xAA, 0x77}); // мусор + одиночный SYNC
        p.feed(packet(block(0x04, 42)));                          // валидный пакет после мусора
        check("resync after garbage", r.log.toString().equals("A=42,M=null;"));
    }

    private static void testTooLongPayloadIsRejected() {
        Recorder r = new Recorder();
        TGamParser p = new TGamParser(r);
        p.feed(new byte[]{(byte) 0xAA, (byte) 0xAA, (byte) 200}); // длина > 169
        p.feed(packet(block(0x04, 10)));
        check("length>169 rejected, next packet parsed", r.log.toString().equals("A=10,M=null;"));
    }

    private static void testEmptyPayloadNoCallback() {
        Recorder r = new Recorder();
        TGamParser p = new TGamParser(r);
        p.feed(packet()); // len=0, пустой payload, корректная чексумма
        check("empty payload -> no callback", r.log.length() == 0);
    }

    private static void testMultiplePacketsInStream() {
        Recorder r = new Recorder();
        TGamParser p = new TGamParser(r);
        p.feed(packet(block(0x04, 10)));
        p.feed(packet(block(0x05, 20)));
        p.feed(packet(block(0x04, 100), block(0x05, 90)));
        check("stream of packets",
                r.log.toString().equals("A=10,M=null;A=null,M=20;A=100,M=90;"));
    }
}
