"""Live joystick monitor for calibrating the JR-100 gamepad mapping."""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Dict


def _instance_id(joystick: object) -> int:
    getter = getattr(joystick, "get_instance_id", None)
    if callable(getter):
        return int(getter())
    fallback = getattr(joystick, "get_id", None)
    if callable(fallback):
        return int(fallback())
    return id(joystick)


def monitor(
    poll_interval: float = 0.05,
    *,
    device_index: int | None = None,
    name_filter: str | None = None,
) -> int:
    """Poll pygame joysticks and print their state until ESC or Ctrl+C.

    Returns the exit code that should be forwarded by the CLI.
    """

    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    try:
        import pygame  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency missing
        print("pygame is required for joystick monitoring", file=sys.stderr)
        return 1

    pygame.init()
    try:
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            print("No joysticks detected. Connect a device and re-run.")
            return 2

        joysticks: Dict[int, object] = {}

        def should_use(index: int, joystick: object) -> bool:
            if device_index is not None and index != device_index:
                return False
            if name_filter is not None and name_filter.lower() not in joystick.get_name().lower():
                return False
            return True

        def register(index: int) -> None:
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
            if not should_use(index, joystick):
                try:
                    joystick.quit()
                except AttributeError:
                    pass
                return
            instance_id = _instance_id(joystick)
            if instance_id in joysticks:
                try:
                    joystick.quit()
                except AttributeError:
                    pass
                return
            joysticks[instance_id] = joystick

        for index in range(pygame.joystick.get_count()):
            register(index)

        print("JR-100 joystick monitor")
        print("Press ESC or close the window to exit.\n")

        clock = pygame.time.Clock()

        running = True
        while running:
            pygame.event.pump()
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == getattr(pygame, "JOYDEVICEADDED", None):
                    register(int(getattr(event, "device_index", -1)))
                elif event.type == getattr(pygame, "JOYDEVICEREMOVED", None):
                    instance_id = int(getattr(event, "instance_id", getattr(event, "which", -1)))
                    joysticks.pop(instance_id, None)

            lines: list[str] = []
            if not joysticks:
                lines.append("No joysticks selected")
            for instance_id, joystick in joysticks.items():
                device_id = getattr(joystick, "get_id", None)
                if callable(device_id):
                    device_repr = device_id()
                else:
                    device_repr = instance_id
                lines.append(
                    f"Joystick instance={instance_id} device={device_repr} name={joystick.get_name()}"
                )
                axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]
                lines.append("  Axes : " + " ".join(f"{value:+.2f}" for value in axes))
                hats = [joystick.get_hat(i) for i in range(joystick.get_numhats())]
                if hats:
                    lines.append("  Hats : " + " ".join(str(value) for value in hats))
                buttons = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
                lines.append("  Buttons: " + " ".join(str(value) for value in buttons))

            # Clear and print status
            print("\033[2J\033[H" + "\n".join(lines), end="", flush=True)
            clock.tick(1.0 / poll_interval if poll_interval > 0 else 60)

        return 0
    finally:
        pygame.joystick.quit()
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="JR-100 joystick monitor")
    parser.add_argument("--index", type=int, default=None, help="pygame デバイスインデックスで絞り込み")
    parser.add_argument("--name", type=str, default=None, help="名前に含まれる文字列で絞り込み")
    parser.add_argument("--poll", type=float, default=0.05, help="ポーリング間隔秒")
    args = parser.parse_args()
    raise SystemExit(
        monitor(
            poll_interval=args.poll,
            device_index=args.index,
            name_filter=args.name,
        )
    )


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
