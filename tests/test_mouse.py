"""Тесты логики управления курсором (без pyautogui — через инжектор mover)."""

import pytest

from tgam_monitor import mouse


@pytest.fixture
def moves():
    """Список-аккумулятор вызовов mover(dx, dy)."""
    return []


@pytest.fixture
def mover(moves):
    def _mover(dx, dy):
        moves.append((dx, dy))
    return _mover


# ------------------------------------------------------------- дискретный
@pytest.mark.parametrize(
    "attention, expected",
    [
        (0, (0, -10)),     # 0-25   вверх
        (24, (0, -10)),
        (25, (0, 10)),     # 26-50  вниз
        (50, (-10, 0)),    # 51-75  влево
        (74, (-10, 0)),
        (75, (10, 0)),     # 76-100 вправо
        (100, (10, 0)),
    ],
)
def test_discrete_direction(attention, expected):
    assert mouse.discrete_direction(attention) == expected


def test_move_discrete_calls_mover(mover, moves):
    mouse.move_discrete(80, mover=mover)
    assert moves == [(10, 0)]


# ------------------------------------------------------------ непрерывный
def test_continuous_center_no_move(mover, moves):
    mouse.move_continuous(50, 50, speed=5, mover=mover)
    assert moves == []


def test_continuous_high_values_move_right_down(mover, moves):
    # att=100 -> dy=(100-50)*5/10=25 -> clamped 10 ; med=100 -> dx=10
    mouse.move_continuous(100, 100, speed=5, mover=mover)
    assert moves == [(10, 10)]


def test_continuous_low_values_move_left_up(mover, moves):
    mouse.move_continuous(0, 0, speed=5, mover=mover)
    assert moves == [(-10, -10)]


def test_continuous_small_delta_truncates_to_zero(mover, moves):
    # att=51 -> dy=0.5 -> int 0; med=51 -> dx=0 => движения нет
    mouse.move_continuous(51, 51, speed=5, mover=mover)
    assert moves == []


# ------------------------------------------------------------------ индикатор
def test_indicator_gray_when_not_running():
    assert mouse.indicator_color(100, 100, running=False, continuous=False) == "gray"


def test_indicator_discrete_levels():
    assert mouse.indicator_color(80, 0, running=True, continuous=False) == "green"
    assert mouse.indicator_color(60, 0, running=True, continuous=False) == "yellow"
    assert mouse.indicator_color(30, 0, running=True, continuous=False) == "gray"


def test_indicator_continuous_mode():
    assert mouse.indicator_color(60, 60, running=True, continuous=True) == "green"
    assert mouse.indicator_color(60, 40, running=True, continuous=True) == "gray"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
