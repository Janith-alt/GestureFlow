"""Turn a steady gesture into one action, with optional dry-run output."""

import ctypes
import sys
from time import monotonic

from gestures import Gesture


POSE_HOLD = 0.12
FIST_HOLD = 0.40
ACTION_COOLDOWN = 0.45
SCROLL_COOLDOWN = 0.08
SCROLL_DISTANCE = 0.035

KEY_ACTIONS = {
    Gesture.PINCH: ("Left click", None),
    Gesture.PALM: ("Play or pause media", "playpause"),
    Gesture.THUMBS_UP: ("Volume up", "volumeup"),
    Gesture.THUMBS_DOWN: ("Volume down", "volumedown"),
}


def emergency_key_down():
    # Windows can read F8 even when another app has keyboard focus.
    return sys.platform == "win32" and bool(ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x8000)


class GestureControls:
    def __init__(self):
        self.disable()

    def enable(self, test_mode):
        self.disable()
        if not test_mode:
            import pyautogui

            pyautogui.PAUSE = 0  # Keep the per-frame mouse movement responsive.
            self._screen_size = pyautogui.size()
            self._input = pyautogui

        self._candidate = self._stable = Gesture.NO_HAND
        self._candidate_since = 0.0
        self._action_sent = False
        self._next_action = self._next_scroll = 0.0
        self._cursor = self._scroll_y = None
        self.enabled = True

    def disable(self):
        self.enabled = False
        self._input = None

    def update(self, gesture, landmarks):
        """Return the action taken or simulated on this frame, if any."""
        if not self.enabled:
            return None

        now = monotonic()
        if gesture != self._candidate:
            self._candidate = gesture
            self._candidate_since = now
            self._cursor = self._scroll_y = None

        # Require a short hold so passing through a pose does not fire it.
        hold = FIST_HOLD if gesture is Gesture.FIST else POSE_HOLD
        if now - self._candidate_since < hold:
            return None
        if gesture != self._stable:
            self._stable = gesture
            self._action_sent = False

        if gesture is Gesture.FIST:
            self.disable()
            return "Paused by closed fist"

        try:
            if gesture is Gesture.POINT:
                if self._input is not None:
                    self._move_cursor(landmarks[8])
                return "Move cursor"
            if gesture is Gesture.SCROLL:
                y = (landmarks[8].y + landmarks[12].y) / 2
                return self._scroll(y, now)
            if gesture in KEY_ACTIONS and not self._action_sent and now >= self._next_action:
                action, key = KEY_ACTIONS[gesture]
                if self._input is not None:
                    if key is None:
                        self._input.click(button="left")
                    else:
                        self._input.press(key)
                # A held pose fires once. A different steady pose rearms it.
                self._action_sent = True
                self._next_action = now + ACTION_COOLDOWN
                return action
        except Exception as error:
            if self._input is not None and isinstance(error, self._input.FailSafeException):
                self.disable()
                return "Emergency stop (mouse corner)"
            raise

        return None

    def _move_cursor(self, tip):
        if self._cursor is None:
            self._cursor = self._input.position()

        # Map the central 76% of the frame to the screen, leaving the
        # PyAutoGUI fail-safe corners reachable with the physical mouse.
        target = []
        for value, extent in zip((tip.x, tip.y), self._screen_size):
            fraction = max(0.0, min(1.0, (value - 0.12) / 0.76))
            target.append(3 + fraction * (extent - 7))

        # Blend each frame with the previous position to dampen jitter.
        self._cursor = tuple(old + 0.32 * (new - old) for old, new in zip(self._cursor, target))
        self._input.moveTo(round(self._cursor[0]), round(self._cursor[1]))

    def _scroll(self, y, now):
        if self._scroll_y is None:
            self._scroll_y = y
            return None

        delta = self._scroll_y - y
        if abs(delta) < SCROLL_DISTANCE or now < self._next_scroll:
            return None
        if self._input is not None:
            # PyAutoGUI forwards raw Windows wheel units (120 per notch).
            step = 120 if sys.platform == "win32" else 1
            self._input.scroll(step if delta > 0 else -step)
        self._scroll_y = y
        self._next_scroll = now + SCROLL_COOLDOWN
        return "Scroll up" if delta > 0 else "Scroll down"
