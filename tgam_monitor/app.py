"""GUI-приложение мониторинга MindWave (tkinter).

Отвечает только за интерфейс и ввод/вывод последовательного порта:
парсинг протокола вынесен в :mod:`tgam_monitor.parser`,
логика движения мыши — в :mod:`tgam_monitor.mouse`.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import messagebox

from tgam_monitor import mouse
from tgam_monitor.parser import TGAMParser

logger = logging.getLogger(__name__)

POLL_INTERVAL_MS = 50


class SerialReader:
    """Чтение байтов из COM-порта в отдельном потоке.

    :param on_byte: вызывается для каждого прочитанного байта
        (в потоке чтения!).
    """

    def __init__(self, port: str, baudrate: int, on_byte) -> None:
        self._port = port
        self._baudrate = baudrate
        self._on_byte = on_byte
        self._connection: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def is_open(self) -> bool:
        return bool(self._connection and self._connection.is_open)

    def open(self) -> None:
        """Открыть порт и запустить поток чтения."""
        self._connection = serial.Serial(self._port, self._baudrate, timeout=1)
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._running = False
        if self._connection:
            self._connection.close()
        self._connection = None
        self._thread = None

    def _read_loop(self) -> None:
        while self._running and self._connection and self._connection.is_open:
            try:
                byte = self._connection.read(1)
                if byte:
                    self._on_byte(byte[0])
            except Exception as exc:  # прерывание связи — выходим из цикла
                logger.error("Ошибка чтения: %s", exc)
                break


class MindWaveMonitor(tk.Tk):
    """Окно приложения: настройки порта, показатели, управление курсором."""

    def __init__(self):
        super().__init__()
        self.title("MindWave Mouse Controller (Simple)")
        self.geometry("450x300")
        self.resizable(False, False)

        # --- настройки ---
        self.port_var = tk.StringVar(value="COM5")
        self.baudrate = 9600
        self.continuous_mode = tk.BooleanVar(value=False)
        self.speed = mouse.DEFAULT_SPEED
        self.threshold_medium = 50
        self.threshold_high = 70

        # --- состояние ---
        self.data_queue: "queue.Queue[dict]" = queue.Queue()
        self.parser = TGAMParser(callback=self.on_packet_received)
        self.last_attention = 0
        self.last_meditation = 0
        self.packet_count = 0
        self.running = False
        self._reader: Optional[SerialReader] = None

        self.create_widgets()
        self.poll_queue()

    # ------------------------------------------------------------- виджеты
    def create_widgets(self) -> None:
        tk.Label(self, text="COM-порт:").pack(pady=5)
        tk.Entry(self, textvariable=self.port_var, width=10).pack()

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Подключиться", command=self.connect).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(btn_frame, text="Отключиться", command=self.disconnect).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(btn_frame, text="Список портов", command=self.list_ports).pack(
            side=tk.LEFT, padx=5
        )

        self.status_label = tk.Label(self, text="Не подключено", fg="red")
        self.status_label.pack()

        tk.Checkbutton(
            self,
            text="Непрерывное управление (внимание по Y, медитация по X)",
            variable=self.continuous_mode,
        ).pack(pady=5)

        val_frame = tk.Frame(self)
        val_frame.pack(pady=10)
        tk.Label(val_frame, text="Внимание:").grid(row=0, column=0, sticky="w")
        self.attention_label = tk.Label(
            val_frame, text="--", font=("Arial", 14), width=5
        )
        self.attention_label.grid(row=0, column=1)

        tk.Label(val_frame, text="Медитация:").grid(row=1, column=0, sticky="w")
        self.meditation_label = tk.Label(
            val_frame, text="--", font=("Arial", 14), width=5
        )
        self.meditation_label.grid(row=1, column=1)

        self.packet_label = tk.Label(self, text="Пакетов: 0")
        self.packet_label.pack()

        self.indicator = tk.Canvas(self, width=50, height=50, bg="gray")
        self.indicator.pack(pady=10)

        tk.Label(
            self,
            text="Дискретный режим: 0-25 вверх, 26-50 вниз, 51-75 влево, 76-100 вправо",
        ).pack()

    # --------------------------------------------------------- действия UI
    def list_ports(self) -> None:
        ports = serial.tools.list_ports.comports()
        msg = "\n".join(f"{p.device} - {p.description}" for p in ports) or "Нет портов"
        messagebox.showinfo("Порты", msg)

    def connect(self) -> None:
        port = self.port_var.get()
        reader = SerialReader(port, self.baudrate, self.parser.feed)
        try:
            reader.open()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть порт {port}: {e}")
            return

        self._reader = reader
        self.running = True
        self.status_label.config(text=f"Подключено к {port}", fg="green")
        self.packet_count = 0
        self.packet_label.config(text="Пакетов: 0")

    def disconnect(self) -> None:
        self.running = False
        if self._reader:
            self._reader.close()
            self._reader = None
        self.status_label.config(text="Не подключено", fg="red")
        self.attention_label.config(text="--")
        self.meditation_label.config(text="--")
        self.indicator.config(bg="gray")
        with self.data_queue.mutex:
            self.data_queue.queue.clear()

    # ------------------------------------------------------- приём данных
    def on_packet_received(self, data: dict) -> None:
        """Callback от парсера, вызывается в потоке чтения."""
        self.data_queue.put(data)

    def poll_queue(self) -> None:
        """Обработка очереди в главном потоке (tkinter-безопасно)."""
        try:
            while True:
                data = self.data_queue.get_nowait()
                self.packet_count += 1
                self.packet_label.config(text=f"Пакетов: {self.packet_count}")

                if "attention" in data:
                    self.last_attention = data["attention"]
                    self.attention_label.config(text=str(self.last_attention))
                if "meditation" in data:
                    self.last_meditation = data["meditation"]
                    self.meditation_label.config(text=str(self.last_meditation))

                # Двигаем мышь при каждом пакете
                if self.running:
                    self.move_mouse()

                self.update_indicator()
        except queue.Empty:
            pass

        self.after(POLL_INTERVAL_MS, self.poll_queue)

    # ------------------------------------------------------ движение мыши
    def move_mouse(self) -> None:
        if self.continuous_mode.get():
            mouse.move_continuous(
                self.last_attention, self.last_meditation, self.speed
            )
        else:
            mouse.move_discrete(self.last_attention)

    def update_indicator(self) -> None:
        color = mouse.indicator_color(
            self.last_attention,
            self.last_meditation,
            running=self.running,
            continuous=self.continuous_mode.get(),
            threshold_medium=self.threshold_medium,
            threshold_high=self.threshold_high,
        )
        self.indicator.config(bg=color)


def main() -> None:
    """Точка входа: настройка логирования и запуск приложения."""
    logging.basicConfig(level=logging.ERROR)  # показывать только ошибки
    app = MindWaveMonitor()
    app.mainloop()
