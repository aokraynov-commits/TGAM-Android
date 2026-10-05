"""TGAM Monitor — мониторинг датчика MindWave (TGAM).

Пакет разбит на модули:
    - parser:   парсер протокола TGAM (нейроинтерфейс MindWave)
    - app:      GUI-приложение на tkinter (отображение показателей)

Управление курсором мыши удалено из приложения.
"""

__version__ = "4.2.0"
__all__ = ["TGAMParser", "MindWaveMonitor"]


def __getattr__(name):
    """Ленивый доступ к GUI-классу, чтобы core-модули можно было использовать
    в средах без tkinter (тесты, серверная часть)."""
    if name == "MindWaveMonitor":
        from tgam_monitor.app import MindWaveMonitor

        return MindWaveMonitor
    if name == "TGAMParser":
        from tgam_monitor.parser import TGAMParser

        return TGAMParser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
