"""Run the GestureFlow AI desktop application."""

import tkinter as tk
from time import monotonic

from camera import PREVIEW_SIZE, Webcam
from controls import GestureControls, emergency_key_down
from gestures import Gesture, classify


class GestureFlowApp:
    def __init__(self, root):
        self.root = root
        self.camera = Webcam()
        self.controls = GestureControls()
        self.camera_ready = False
        self.stopping = False

        root.title("GestureFlow AI")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F8>", self._emergency_stop)

        self.camera_status = tk.StringVar(value="Camera: Stopped")
        self.gesture_status = tk.StringVar(value=f"Gesture: {Gesture.NO_HAND.value}")
        self.control_status = tk.StringVar(value="Gesture control: Disabled")
        self.action_status = tk.StringVar(value="Last action: None")
        self.test_mode = tk.BooleanVar(value=False)

        panel = tk.Frame(root, padx=10, pady=10)
        panel.pack(fill="both")

        buttons = tk.Frame(panel)
        buttons.pack(pady=(0, 6))
        self.start_button = tk.Button(buttons, text="Start Camera", width=22, command=self.start_camera)
        self.stop_button = tk.Button(buttons, text="Stop Camera", width=22, command=self.stop_camera)
        self.enable_button = tk.Button(
            buttons, text="Enable Gesture Control", width=22, command=self.enable_controls
        )
        self.disable_button = tk.Button(
            buttons, text="Disable Gesture Control", width=22, command=self.disable_controls
        )
        for index, button in enumerate((
            self.start_button, self.stop_button, self.enable_button, self.disable_button
        )):
            button.grid(row=index // 2, column=index % 2, padx=2, pady=2)

        width, height = PREVIEW_SIZE
        self.blank_image = tk.PhotoImage(master=root, width=width, height=height)
        self.preview_image = self.blank_image
        self.preview = tk.Label(
            panel, image=self.preview_image, width=width, height=height, relief=tk.SUNKEN
        )
        self.preview.pack()

        for status in (self.camera_status, self.gesture_status, self.control_status):
            tk.Label(panel, textvariable=status, wraplength=width, justify="left").pack(anchor="w")
        tk.Checkbutton(
            panel, text="Test mode (show actions only)", variable=self.test_mode, command=self._change_mode
        ).pack(anchor="w")
        tk.Label(
            panel, textvariable=self.action_status, wraplength=width, justify="left"
        ).pack(anchor="w")

        footer = tk.Frame(panel)
        footer.pack(fill="x", pady=(5, 0))
        tk.Label(footer, text="F8  Emergency stop").pack(side="left")
        tk.Button(footer, text="Exit", command=self.close).pack(side="right")

        self._refresh_buttons()
        self._timer = root.after(15, self._update)

    def _refresh_buttons(self):
        running = self.camera.running
        can_enable = running and self.camera_ready and not self.controls.enabled
        self.start_button.config(state=tk.NORMAL if not running and not self.stopping else tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL if running and not self.stopping else tk.DISABLED)
        self.enable_button.config(state=tk.NORMAL if can_enable else tk.DISABLED)
        self.disable_button.config(state=tk.NORMAL if self.controls.enabled else tk.DISABLED)

    def start_camera(self):
        self.camera.start()
        self.camera_status.set("Camera: Starting...")
        self._refresh_buttons()

    def stop_camera(self):
        self.camera.stop()
        self.stopping = True
        self.camera_status.set("Camera: Stopping...")
        self._clear_preview()
        self.disable_controls()

    def enable_controls(self):
        if not self.camera_ready or not self.camera.running:
            return
        try:
            self.controls.enable(self.test_mode.get())
        except Exception as error:
            self._show_action(f"Could not enable controls ({error})")
            return
        mode = "Enabled (test mode)" if self.test_mode.get() else "Enabled"
        self.control_status.set(f"Gesture control: {mode}")
        self._show_action("None")
        self._refresh_buttons()

    def disable_controls(self):
        self.controls.disable()
        self.control_status.set("Gesture control: Disabled")
        self._refresh_buttons()

    def _change_mode(self):
        self.disable_controls()
        self._show_action("None")

    def _show_action(self, action):
        label = "Last test action" if self.test_mode.get() else "Last action"
        self.action_status.set(f"{label}: {action}")

    def _emergency_stop(self, event=None):
        if self.controls.enabled:
            self.disable_controls()
            self._show_action("Emergency stop (F8)")
        return "break"

    def _clear_preview(self):
        self.camera_ready = False
        self.preview.configure(image=self.blank_image)
        self.preview_image = self.blank_image
        self.gesture_status.set(f"Gesture: {Gesture.NO_HAND.value}")

    def _update(self):
        # Check the shortcut before processing another frame or issuing input.
        if self.controls.enabled and emergency_key_down():
            self._emergency_stop()

        update = self.camera.poll()
        if self.stopping:
            if not self.camera.running:
                self.stopping = False
                self.camera_status.set("Camera: Stopped")
        elif isinstance(update, str):
            self._clear_preview()
            self.disable_controls()
            self.camera_status.set(f"Camera error: {update}")
        elif update is not None:
            self._show_frame(update)

        self._refresh_buttons()
        self._timer = self.root.after(15, self._update)

    def _show_frame(self, frame):
        image = tk.PhotoImage(master=self.root, data=frame.preview, format="ppm")
        self.preview.configure(image=image)
        self.preview_image = image  # Tkinter needs a Python reference to keep the image visible.
        if not self.camera_ready:
            self.camera_ready = True
            self.camera_status.set("Camera: Running")

        gesture = classify(frame.landmarks, frame.aspect_ratio)
        self.gesture_status.set(f"Gesture: {gesture.value}")
        try:
            action = self.controls.update(gesture, frame.landmarks)
        except Exception as error:
            self.disable_controls()
            self._show_action(f"Could not send input ({error})")
            return
        if action is not None:
            self._show_action(action)
            if not self.controls.enabled:
                self.control_status.set("Gesture control: Disabled")

    def close(self):
        self.root.after_cancel(self._timer)
        self.controls.disable()
        self.camera.stop()
        self.root.withdraw()
        self._finish_close(monotonic() + 2.0)

    def _finish_close(self, deadline):
        # Give the worker time to release the webcam. A stuck driver can
        # still be closed by the OS when the process exits.
        if self.camera.running and monotonic() < deadline:
            self.root.after(30, self._finish_close, deadline)
        else:
            self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    app = GestureFlowApp(window)
    window.mainloop()
