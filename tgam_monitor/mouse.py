"""Стратегии управления курсором мыши по значениям внимания/медитации.

Вынесено из GUI-класса, чтобы логику можно было тестировать без tkinter
и pyautogui (движение инжектируется через параметр ``mover``).
"""

from __future__ import annotations

from typing import Callable, Tuple

# mover(dx, dy) — функция относительного перемещения курсора
Mover = Callable[[int, int], None]

#: Границы дискретных зон внимания (включительно): до 25 / до 50 / до 75 / выше
DISCRETE_BOUNDARIES = (25, 50, 75)
DISCRETE_STEP = 10

#: Диапазон нейтрального значения для непрерывного режима
CONTINUOUS_CENTER = 50
#: Максимальный шаг смещения в непрерывном режиме
CONTINUOUS_MAX_STEP = 10
#: Скорость перемещения по умолчанию
DEFAULT_SPEED = 5


def default_mover(dx: int, dy: int) -> None:
    """Перемещение курсора через pyautogui (используется приложением)."""
    import pyautogui

    pyautogui.moveRel(dx, dy)


def discrete_direction(attention: int) -> Tuple[int, int]:
    """Возвращает вектор смещения по зоне внимания.

    0-25 вверх, 26-50 вниз, 51-75 влево, 76-100 вправо.
    """
    if attention < DISCRETE_BOUNDARIES[0]:
        return (0, -DISCRETE_STEP)
    if attention < DISCRETE_BOUNDARIES[1]:
        return (0, DISCRETE_STEP)
    if attention < DISCRETE_BOUNDARIES[2]:
        return (-DISCRETE_STEP, 0)
    return (DISCRETE_STEP, 0)


def continuous_delta(
    attention: int, meditation: int, speed: int
) -> Tuple[int, int]:
    """Возвращает (dx, dy) для непрерывного режима с ограничением шага."""
    delta_y = (attention - CONTINUOUS_CENTER) * speed / 10
    delta_x = (meditation - CONTINUOUS_CENTER) * speed / 10
    dx = int(max(-CONTINUOUS_MAX_STEP, min(CONTINUOUS_MAX_STEP, delta_x)))
    dy = int(max(-CONTINUOUS_MAX_STEP, min(CONTINUOUS_MAX_STEP, delta_y)))
    return dx, dy


def move_discrete(attention: int, mover: Mover = default_mover) -> None:
    """Дискретный режим: одно перемещение по текущему значению внимания."""
    dx, dy = discrete_direction(attention)
    mover(dx, dy)


def move_continuous(
    attention: int,
    meditation: int,
    speed: int,
    mover: Mover = default_mover,
) -> None:
    """Непрерывный режим: внимание по Y, медитация по X."""
    dx, dy = continuous_delta(attention, meditation, speed)
    if dx != 0 or dy != 0:
        mover(dx, dy)


def indicator_color(
    attention: int,
    meditation: int,
    *,
    running: bool,
    continuous: bool,
    threshold_medium: int = 50,
    threshold_high: int = 70,
) -> str:
    """Цвет индикатора состояния: gray / yellow / green."""
    if not running:
        return "gray"
    if continuous:
        if attention > CONTINUOUS_CENTER and meditation > CONTINUOUS_CENTER:
            return "green"
        return "gray"
    if attention > threshold_high:
        return "green"
    if attention > threshold_medium:
        return "yellow"
    return "gray"
