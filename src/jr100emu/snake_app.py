"""Minimal pygame app for a classic Snake game."""

from __future__ import annotations

import argparse
import random
from typing import Iterable

from jr100emu.snake_logic import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    SnakeState,
    initial_state,
    set_direction,
    step,
    toggle_pause,
)

WINDOW_TITLE = "Snake"
BACKGROUND = (20, 20, 20)
GRID_LINE = (45, 45, 45)
SNAKE_COLOR = (80, 220, 80)
HEAD_COLOR = (120, 255, 120)
FOOD_COLOR = (230, 70, 70)
TEXT_COLOR = (230, 230, 230)


def _draw(screen, pygame, font, state: SnakeState, cell_size: int, margin: int) -> None:
    board_w = state.width * cell_size
    board_h = state.height * cell_size
    screen.fill(BACKGROUND)

    for x in range(state.width + 1):
        px = margin + x * cell_size
        pygame.draw.line(screen, GRID_LINE, (px, margin), (px, margin + board_h), 1)
    for y in range(state.height + 1):
        py = margin + y * cell_size
        pygame.draw.line(screen, GRID_LINE, (margin, py), (margin + board_w, py), 1)

    for index, (x, y) in enumerate(state.snake):
        rect = pygame.Rect(
            margin + x * cell_size + 1,
            margin + y * cell_size + 1,
            cell_size - 2,
            cell_size - 2,
        )
        color = HEAD_COLOR if index == 0 else SNAKE_COLOR
        pygame.draw.rect(screen, color, rect)

    if state.food is not None:
        fx, fy = state.food
        rect = pygame.Rect(
            margin + fx * cell_size + 2,
            margin + fy * cell_size + 2,
            cell_size - 4,
            cell_size - 4,
        )
        pygame.draw.rect(screen, FOOD_COLOR, rect)

    status = f"Score: {state.score}  Space:Pause  R:Restart  Arrows/WASD:Move"
    status_surface = font.render(status, True, TEXT_COLOR)
    screen.blit(status_surface, (margin, margin + board_h + 10))

    if not state.alive:
        message = "Game Over - Press R to Restart"
        msg_surface = font.render(message, True, TEXT_COLOR)
        msg_rect = msg_surface.get_rect(center=(margin + board_w // 2, margin + board_h // 2))
        screen.blit(msg_surface, msg_rect)
    elif state.paused:
        message = "Paused"
        msg_surface = font.render(message, True, TEXT_COLOR)
        msg_rect = msg_surface.get_rect(center=(margin + board_w // 2, margin + board_h // 2))
        screen.blit(msg_surface, msg_rect)

    pygame.display.flip()


def _run_pygame(width: int, height: int, cell_size: int, tick_ms: int, seed: int | None) -> None:
    import pygame  # type: ignore

    rng = random.Random(seed)
    margin = 16
    info_height = 40
    window_w = width * cell_size + margin * 2
    window_h = height * cell_size + margin * 2 + info_height

    pygame.init()
    screen = pygame.display.set_mode((window_w, window_h))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Courier", 20)

    state = initial_state(width, height, rng)
    queued_direction = state.direction
    last_tick = pygame.time.get_ticks()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    queued_direction = set_direction(state.direction, UP)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    queued_direction = set_direction(state.direction, DOWN)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    queued_direction = set_direction(state.direction, LEFT)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    queued_direction = set_direction(state.direction, RIGHT)
                elif event.key == pygame.K_r:
                    state = initial_state(width, height, rng)
                    queued_direction = state.direction
                    last_tick = pygame.time.get_ticks()
                elif event.key == pygame.K_SPACE and state.alive:
                    state = toggle_pause(state)
                elif event.key == pygame.K_ESCAPE:
                    running = False

        now = pygame.time.get_ticks()
        if now - last_tick >= tick_ms:
            state = SnakeState(
                width=state.width,
                height=state.height,
                snake=state.snake,
                direction=queued_direction,
                food=state.food,
                score=state.score,
                alive=state.alive,
                paused=state.paused,
            )
            state = step(state, rng)
            last_tick = now

        _draw(screen, pygame, font, state, cell_size, margin)
        clock.tick(60)

    pygame.quit()


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Classic Snake")
    parser.add_argument("--width", type=int, default=20, help="Grid width")
    parser.add_argument("--height", type=int, default=20, help="Grid height")
    parser.add_argument("--cell-size", type=int, default=24, help="Cell size in pixels")
    parser.add_argument("--tick-ms", type=int, default=120, help="Tick interval in milliseconds")
    parser.add_argument("--seed", type=int, default=None, help="Seed for deterministic food spawn")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.width < 4 or args.height < 4:
        raise SystemExit("width and height must be >= 4")
    if args.cell_size < 8:
        raise SystemExit("cell-size must be >= 8")
    if args.tick_ms < 30:
        raise SystemExit("tick-ms must be >= 30")

    _run_pygame(
        width=args.width,
        height=args.height,
        cell_size=args.cell_size,
        tick_ms=args.tick_ms,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
