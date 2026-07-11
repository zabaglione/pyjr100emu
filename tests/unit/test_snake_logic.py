"""Tests for snake core logic."""

from __future__ import annotations

import random

from jr100emu.snake_logic import (
    DOWN,
    LEFT,
    RIGHT,
    SnakeState,
    UP,
    initial_state,
    set_direction,
    spawn_food,
    step,
)


def test_initial_state_has_valid_food() -> None:
    rng = random.Random(123)
    state = initial_state(10, 10, rng)
    assert len(state.snake) == 3
    assert state.food is not None
    assert state.food not in state.snake


def test_set_direction_rejects_opposite() -> None:
    assert set_direction(RIGHT, LEFT) == RIGHT
    assert set_direction(UP, DOWN) == UP
    assert set_direction(RIGHT, UP) == UP


def test_step_moves_forward_without_growth() -> None:
    rng = random.Random(1)
    state = SnakeState(
        width=8,
        height=8,
        snake=((3, 3), (2, 3), (1, 3)),
        direction=RIGHT,
        food=(0, 0),
        score=0,
        alive=True,
    )
    new_state = step(state, rng)
    assert new_state.alive
    assert new_state.snake == ((4, 3), (3, 3), (2, 3))
    assert new_state.score == 0
    assert new_state.food == (0, 0)


def test_step_grows_and_increments_score() -> None:
    rng = random.Random(2)
    state = SnakeState(
        width=8,
        height=8,
        snake=((3, 3), (2, 3), (1, 3)),
        direction=RIGHT,
        food=(4, 3),
        score=0,
        alive=True,
    )
    new_state = step(state, rng)
    assert new_state.alive
    assert new_state.snake == ((4, 3), (3, 3), (2, 3), (1, 3))
    assert new_state.score == 1
    assert new_state.food not in new_state.snake


def test_step_detects_wall_collision() -> None:
    rng = random.Random(3)
    state = SnakeState(
        width=5,
        height=5,
        snake=((4, 2), (3, 2), (2, 2)),
        direction=RIGHT,
        food=(0, 0),
        score=0,
        alive=True,
    )
    new_state = step(state, rng)
    assert not new_state.alive
    assert new_state.snake == state.snake


def test_step_detects_self_collision() -> None:
    rng = random.Random(4)
    state = SnakeState(
        width=8,
        height=8,
        snake=((4, 4), (4, 5), (3, 5), (3, 4), (3, 3), (4, 3)),
        direction=DOWN,
        food=(0, 0),
        score=0,
        alive=True,
    )
    new_state = step(state, rng)
    assert not new_state.alive


def test_spawn_food_returns_none_on_full_board() -> None:
    rng = random.Random(9)
    snake = tuple((x, y) for y in range(2) for x in range(2))
    assert spawn_food(2, 2, snake, rng) is None
