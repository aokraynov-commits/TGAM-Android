"""
MindWave TGAM Data Reader (упрощённый парсинг)
Основан на оригинальном коде Arduino: ищем 0x04 и 0x05 в payload.
"""

import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import queue
import pyautogui
import logging

# Отключаем лишние предупреждения или перенаправляем в файл
logging.basicConfig(level=logging.ERROR)  # показывать только ошибки
logger = logging.getLogger(__name__)


class TGAMSimpleParser:
    """
    Упрощённый парсер: только ищет байты 0x04 (Attention) и 0x05 (Meditation)
    и читает следующий байт как значение. Остальное игнорирует.
    """
    def __init__(self, callback=None):
        self.callback = callback
        self.buffer = bytearray()
        self.state = 'SYNC'
        self.payload_length = 0
        self.payload = bytearray()
        self.generated_checksum = 0
        self.checksum = 0

    def feed(self, data):
        if isinstance(data, int):
            data = bytes([data])
        for byte in data:
            self._parse_byte(byte)

    def _parse_byte(self, byte):
        if self.state == 'SYNC':
            if byte == 0xAA:
                self.state = 'SYNC2'
        elif self.state == 'SYNC2':
            if byte == 0xAA:
                self.state = 'LENGTH'
            else:
                self.state = 'SYNC'
        elif self.state == 'LENGTH':
            self.payload_length = byte
            if self.payload_length > 169:
                self.state = 'SYNC'
            else:
                self.payload = bytearray()
                self.generated_checksum = 0
                self.state = 'PAYLOAD'
        elif self.state == 'PAYLOAD':
            self.payload.append(byte)
            self.generated_checksum += byte
            if len(self.payload) >= self.payload_length:
                self.state = 'CHECKSUM'
        elif self.state == 'CHECKSUM':
            self.checksum = byte
            self._finalize_packet()
            self.state = 'SYNC'
        else:
            self.state = 'SYNC'

    def _finalize_packet(self):
        computed = (255 - self.generated_checksum) & 0xFF
        if computed != self.checksum:
            return

        # Упрощённый разбор: ищем 0x04 и 0x05
        attention = None
        meditation = None
        i = 0
        length = len(self.payload)
        while i < length - 1:  # нужно минимум 2 байта: код и значение
            if self.payload[i] == 0x04:
                attention = self.payload[i+1]
                i += 2
            elif self.payload[i] == 0x05:
                meditation = self.payload[i+1]
                i += 2
            else:
                i += 1  # пропускаем неизвестный байт

        # Если нашли что-то, вызываем callback
        if attention is not None or meditation is not None:
            data = {}
            if attention is not None:
                data['attention'] = attention
            if meditation is not None:
                data['meditation'] = meditation
            if self.callback:
                self.callback(data)

        # Для отладки можно раскомментировать:
        # print(f"Payload: {self.payload.hex()} -> attention={attention}, meditation={meditation}")


class MindWaveMonitor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MindWave Mouse Controller (Simple)")
        self.geometry("450x300")
        self.resizable(False, False)

        self.port_var = tk.StringVar(value="COM5")
        self.baudrate = 9600
        self.continuous_mode = tk.BooleanVar(value=False)
        self.speed = 5
        self.threshold_medium = 50
        self.threshold_high = 70

        self.data_queue = queue.Queue()
        self.parser = TGAMSimpleParser(callback=self.on_packet_received)

        self.last_attention = 0
        self.last_meditation = 0
        self.packet_count = 0

        self.serial_connection = None
        self.running = False
        self.serial_thread = None

        self.create_widgets()
        self.poll_queue()

    def create_widgets(self):
        tk.Label(self, text="COM-порт:").pack(pady=5)
        tk.Entry(self, textvariable=self.port_var, width=10).pack()

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Подключиться", command=self.connect).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Отключиться", command=self.disconnect).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Список портов", command=self.list_ports).pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(self, text="Не подключено", fg="red")
        self.status_label.pack()

        tk.Checkbutton(self, text="Непрерывное управление (внимание по Y, медитация по X)",
                       variable=self.continuous_mode).pack(pady=5)

        val_frame = tk.Frame(self)
        val_frame.pack(pady=10)
        tk.Label(val_frame, text="Внимание:").grid(row=0, column=0, sticky='w')
        self.attention_label = tk.Label(val_frame, text="--", font=('Arial', 14), width=5)
        self.attention_label.grid(row=0, column=1)

        tk.Label(val_frame, text="Медитация:").grid(row=1, column=0, sticky='w')
        self.meditation_label = tk.Label(val_frame, text="--", font=('Arial', 14), width=5)
        self.meditation_label.grid(row=1, column=1)

        self.packet_label = tk.Label(self, text="Пакетов: 0")
        self.packet_label.pack()

        self.indicator = tk.Canvas(self, width=50, height=50, bg='gray')
        self.indicator.pack(pady=10)

        tk.Label(self, text="Дискретный режим: 0-25 вверх, 26-50 вниз, 51-75 влево, 76-100 вправо").pack()

    def list_ports(self):
        ports = serial.tools.list_ports.comports()
        msg = "\n".join([f"{p.device} - {p.description}" for p in ports]) or "Нет портов"
        messagebox.showinfo("Порты", msg)

    def connect(self):
        port = self.port_var.get()
        try:
            self.serial_connection = serial.Serial(port, self.baudrate, timeout=1)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть порт {port}: {e}")
            return

        self.running = True
        self.status_label.config(text=f"Подключено к {port}", fg="green")
        self.packet_count = 0
        self.packet_label.config(text="Пакетов: 0")

        self.serial_thread = threading.Thread(target=self.read_serial, daemon=True)
        self.serial_thread.start()

    def disconnect(self):
        self.running = False
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
        self.status_label.config(text="Не подключено", fg="red")
        self.attention_label.config(text="--")
        self.meditation_label.config(text="--")
        self.indicator.config(bg="gray")
        with self.data_queue.mutex:
            self.data_queue.queue.clear()

    def read_serial(self):
        while self.running and self.serial_connection and self.serial_connection.is_open:
            try:
                byte = self.serial_connection.read(1)
                if byte:
                    self.parser.feed(byte[0])
            except Exception as e:
                logger.error(f"Ошибка чтения: {e}")
                break

    def on_packet_received(self, data):
        """Callback от парсера, вызывается в потоке чтения."""
        self.data_queue.put(data)

    def poll_queue(self):
        """Обработка очереди в главном потоке."""
        try:
            while True:
                data = self.data_queue.get_nowait()
                self.packet_count += 1
                self.packet_label.config(text=f"Пакетов: {self.packet_count}")

                if 'attention' in data:
                    self.last_attention = data['attention']
                    self.attention_label.config(text=str(self.last_attention))
                if 'meditation' in data:
                    self.last_meditation = data['meditation']
                    self.meditation_label.config(text=str(self.last_meditation))

                # Двигаем мышь при каждом пакете
                if self.running:
                    self.move_mouse()

                self.update_indicator()
        except queue.Empty:
            pass

        self.after(50, self.poll_queue)

    def move_mouse(self):
        if self.continuous_mode.get():
            self.move_mouse_continuous()
        else:
            self.move_mouse_discrete()

    def move_mouse_discrete(self):
        att = self.last_attention
        if att < 25:
            pyautogui.moveRel(0, -10)
        elif att < 50:
            pyautogui.moveRel(0, 10)
        elif att < 75:
            pyautogui.moveRel(-10, 0)
        else:
            pyautogui.moveRel(10, 0)

    def move_mouse_continuous(self):
        att = self.last_attention
        med = self.last_meditation
        delta_y = (att - 50) * self.speed / 10
        delta_x = (med - 50) * self.speed / 10
        step_x = int(max(-10, min(10, delta_x)))
        step_y = int(max(-10, min(10, delta_y)))
        if step_x != 0 or step_y != 0:
            pyautogui.moveRel(step_x, step_y)

    def update_indicator(self):
        if not self.running:
            self.indicator.config(bg='gray')
            return
        if self.continuous_mode.get():
            if self.last_attention > 50 and self.last_meditation > 50:
                self.indicator.config(bg='green')
            else:
                self.indicator.config(bg='gray')
        else:
            if self.last_attention > self.threshold_high:
                self.indicator.config(bg='green')
            elif self.last_attention > self.threshold_medium:
                self.indicator.config(bg='yellow')
            else:
                self.indicator.config(bg='gray')


if __name__ == "__main__":
    app = MindWaveMonitor()
    app.mainloop()