"""Live joystick monitor for calibrating the JR-100 gamepad mapping."""

from __future__ import annotations

import sys
import time


def monitor(poll_interval: float = 0.05) -> int:
    """Poll pygame joysticks and print their state until ESC or Ctrl+C.

    Returns the exit code that should be forwarded by the CLI.
    """

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

        joysticks = []
        for index in range(pygame.joystick.get_count()):
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
            joysticks.append(joystick)

        print("JR-100 joystick monitor")
        print("Press ESC or close the window to exit.\n")

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            lines: list[str] = []
            for joystick in joysticks:
                lines.append(f"Joystick {joystick.get_id()} - {joystick.get_name()}")
                axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]
                lines.append("  Axes : " + " ".join(f"{value:+.2f}" for value in axes))
                hats = [joystick.get_hat(i) for i in range(joystick.get_numhats())]
                if hats:
                    lines.append("  Hats : " + " ".join(str(value) for value in hats))
                buttons = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
                lines.append("  Buttons: " + " ".join(str(value) for value in buttons))

            # Clear and print status
            print("\033[2J\033[H" + "\n".join(lines), end="", flush=True)
            time.sleep(poll_interval)

        return 0
    finally:
        pygame.joystick.quit()
        pygame.quit()


def main() -> None:
    raise SystemExit(monitor())


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
