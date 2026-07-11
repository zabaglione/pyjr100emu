"""Core logic for a classic grid-based Snake game."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Optional

Coord = tuple[int, int]
Direction = tuple[int, int]

UP: Direction = (0, -1)
DOWN: Direction = (0, 1)
LEFT: Direction = (-1, 0)
RIGHT: Direction = (1, 0)


@dataclass(frozen=True)
class SnakeState:
    width: int
    height: int
    snake: tuple[Coord, ...]
    direction: Direction
    food: Optional[Coord]
    score: int
    alive: bool
    paused: bool = False


def _is_opposite(a: Direction, b: Direction) -> bool:
    return a[0] == -b[0] and a[1] == -b[1]


def set_direction(current: Direction, requested: Direction) -> Direction:
    if _is_opposite(current, requested):
        return current
    return requested


def spawn_food(
    width: int,
    height: int,
    snake: tuple[Coord, ...],
    rng: random.Random,
) -> Optional[Coord]:
    occupied = set(snake)
    free_cells = [
        (x, y)
        for y in range(height)
        for x in range(width)
        if (x, y) not in occupied
    ]
    if not free_cells:
        return None
    return free_cells[rng.randrange(len(free_cells))]


def initial_state(width: int, height: int, rng: random.Random) -> SnakeState:
    if width < 4 or height < 4:
        raise ValueError("Board size must be at least 4x4")

    cx = width // 2
    cy = height // 2
    snake = ((cx, cy), (cx - 1, cy), (cx - 2, cy))
    food = spawn_food(width, height, snake, rng)
    return SnakeState(
        width=width,
        height=height,
        snake=snake,
        direction=RIGHT,
        food=food,
        score=0,
        alive=True,
    )


def toggle_pause(state: SnakeState) -> SnakeState:
    return SnakeState(
        width=state.width,
        height=state.height,
        snake=state.snake,
        direction=state.direction,
        food=state.food,
        score=state.score,
        alive=state.alive,
        paused=not state.paused,
    )


def step(state: SnakeState, rng: random.Random) -> SnakeState:
    if not state.alive or state.paused:
        return state

    head_x, head_y = state.snake[0]
    dx, dy = state.direction
    next_head = (head_x + dx, head_y + dy)

    if not (0 <= next_head[0] < state.width and 0 <= next_head[1] < state.height):
        return SnakeState(
            width=state.width,
            height=state.height,
            snake=state.snake,
            direction=state.direction,
            food=state.food,
            score=state.score,
            alive=False,
            paused=state.paused,
        )

    eats_food = state.food is not None and next_head == state.food
    body_for_collision = state.snake if eats_food else state.snake[:-1]
    if next_head in body_for_collision:
        return SnakeState(
            width=state.width,
            height=state.height,
            snake=state.snake,
            direction=state.direction,
            food=state.food,
            score=state.score,
            alive=False,
            paused=state.paused,
        )

    if eats_food:
        new_snake = (next_head,) + state.snake
        new_score = state.score + 1
        new_food = spawn_food(state.width, state.height, new_snake, rng)
    else:
        new_snake = (next_head,) + state.snake[:-1]
        new_score = state.score
        new_food = state.food

    return SnakeState(
        width=state.width,
        height=state.height,
        snake=new_snake,
        direction=state.direction,
        food=new_food,
        score=new_score,
        alive=True,
        paused=state.paused,
    )
