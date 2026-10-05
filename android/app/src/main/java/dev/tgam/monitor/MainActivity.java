package dev.tgam.monitor;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

import dev.tgam.parser.TGamParser;

/**
 * Точка входа Android-приложения: показывает Attention / Meditation датчика
 * MindWave (TGAM). Управление мышью отсутствует (удалено из обоих скриптов).
 *
 * Байты потока подаются в {@link #feed(byte[])} — например, из
 * UsbSerialPort#read(...) библиотеки usb-serial-for-android в рабочем потоке.
 */
public class MainActivity extends Activity {

    private TextView attentionView;
    private TextView meditationView;
    private int packetCount = 0;

    private final TGamParser parser = new TGamParser((attention, meditation) ->
            runOnUiThread(() -> onPacket(attention, meditation)));

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        attentionView = findViewById(R.id.attention_value);
        meditationView = findViewById(R.id.meditation_value);

        // Пример привязки USB-устройства (реализация чтения — на стороне
        // usb-serial-for-android): UsbManager manager =
        //         (UsbManager) getSystemService(Context.USB_SERVICE);
    }

    /** Вызывать из потока чтения порта для каждого прочитанного блока байт. */
    public void feed(byte[] data) {
        parser.feed(data);
    }

    private void onPacket(Integer attention, Integer meditation) {
        packetCount++;
        if (attention != null) {
            attentionView.setText(String.valueOf(attention));
        }
        if (meditation != null) {
            meditationView.setText(String.valueOf(meditation));
        }
    }
}
