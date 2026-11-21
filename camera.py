"""Capture the webcam and detect landmarks without blocking Tkinter."""

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic_ns


PREVIEW_SIZE = (320, 240)
MODEL_PATH = Path(__file__).resolve().with_name("hand_landmarker.task")


@dataclass
class CameraFrame:
    preview: bytes
    landmarks: list
    aspect_ratio: float


class Webcam:
    def __init__(self):
        self._thread = None
        self._stop = Event()
        self._lock = Lock()
        self._latest = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self.poll()
        self._thread = Thread(target=self._capture, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def poll(self):
        """Return and clear the newest frame or camera error."""
        with self._lock:
            update = self._latest
            self._latest = None
        return update

    def _publish(self, update):
        # Keep one frame so a busy UI never builds up a backlog of gestures.
        with self._lock:
            self._latest = update

    def _capture(self):
        capture = None
        try:
            if not MODEL_PATH.is_file():
                raise RuntimeError("Hand model missing. See the download step in README.md.")

            import cv2
            import mediapipe as mp

            if self._stop.is_set():
                return
            capture = cv2.VideoCapture(0)
            if not capture.isOpened():
                raise RuntimeError("Could not open the webcam. Check permissions and other camera apps.")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            vision = mp.tasks.vision
            options = vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
            )
            connections = vision.HandLandmarksConnections.HAND_CONNECTIONS
            last_timestamp = -1
            missed_frames = 0
            with vision.HandLandmarker.create_from_options(options) as detector:
                while not self._stop.is_set():
                    ok, frame = capture.read()
                    if self._stop.is_set():
                        break
                    if not ok or frame is None:
                        missed_frames += 1
                        if missed_frames >= 5:
                            raise RuntimeError("The webcam stopped returning frames.")
                        self._stop.wait(0.05)
                        continue
                    missed_frames = 0

                    # Mirror the feed so cursor movement matches the preview.
                    frame = cv2.flip(frame, 1)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    timestamp = max(last_timestamp + 1, monotonic_ns() // 1_000_000)
                    result = detector.detect_for_video(image, timestamp)
                    last_timestamp = timestamp
                    landmarks = result.hand_landmarks[0] if result.hand_landmarks else []
                    preview = _make_preview(cv2, frame, landmarks, connections)
                    self._publish(CameraFrame(preview, landmarks, frame.shape[1] / frame.shape[0]))
        except Exception as error:
            if not self._stop.is_set():
                message = str(error).partition("\n")[0].strip() or type(error).__name__
                self._publish(message)
        finally:
            if capture is not None:
                capture.release()


def _make_preview(cv2, frame, landmarks, connections):
    height, width = frame.shape[:2]
    scale = min(PREVIEW_SIZE[0] / width, PREVIEW_SIZE[1] / height)
    width, height = round(width * scale), round(height * scale)
    preview = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    if landmarks:
        points = [(round(p.x * (width - 1)), round(p.y * (height - 1))) for p in landmarks]
        for connection in connections:
            cv2.line(preview, points[connection.start], points[connection.end], (0, 255, 0), 1)
        for point in points:
            cv2.circle(preview, point, 2, (0, 0, 255), -1)

    # Tkinter reads PPM directly, so no separate image library is needed.
    ok, encoded = cv2.imencode(".ppm", preview)
    if not ok:
        raise RuntimeError("Could not prepare the webcam preview.")
    return encoded.tobytes()
