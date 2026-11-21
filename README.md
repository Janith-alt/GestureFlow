# GestureFlow AI

GestureFlow AI is a small Tkinter app that turns hand gestures from one webcam into mouse and media controls. It is set up for 64-bit Python 3.12 on Windows.

## Run in VS Code

For a fresh checkout, run these commands in PowerShell.

```powershell
git clone https://github.com/Janith-alt/GestureFlow.git
cd GestureFlow
```

1. Open this project folder in VS Code and install the Microsoft Python extension if needed. [VS Code Python setup](https://code.visualstudio.com/docs/python/python-tutorial)
2. Open a PowerShell terminal in the project folder and run these commands to set up the environment. If you already set up `.venv` on this PC, skip to the next step.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. If `hand_landmarker.task` is missing, save a copy in this folder beside `camera.py`. [Download Google's hand landmark model](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)
4. Press `Ctrl+Shift+P`, choose **Python: Select Interpreter**, and select `.venv\Scripts\python.exe`. Open `main.py` and use **Run Python File in Terminal**, or run this command.

   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

## Use the app

1. Click **Start Camera** and wait for the preview. The gesture label updates whenever the camera is running.
2. Check **Test mode (show actions only)** and click **Enable Gesture Control** to practice. **Last test action** shows the action that the pose would trigger.
3. To control the computer, uncheck **Test mode** and click **Enable Gesture Control** again. Press **F8** to disable controls even when another window has focus on Windows. **Stop Camera** and **Exit** both release the webcam.

| Gesture | What to do |
| --- | --- |
| Index finger | Extend your index finger with the other three fingers curled. Move the fingertip to steer the cursor on the primary display. |
| Thumb and index pinch | Bring those fingertips together to left-click at the current cursor position. Separate them before clicking again. |
| Two fingers | Extend index and middle fingers. Hold briefly, then move them up or down to scroll in that direction. |
| Open palm | Extend all five fingers to send the system play/pause key. |
| Thumbs up | Curl the four fingers and point your thumb up to raise the volume one step. |
| Thumbs down | Curl the four fingers and point your thumb down to lower the volume one step. |
| Closed fist | Hold for about half a second to pause controls. Click **Enable Gesture Control** to resume. |

Use one hand in good lighting with the wrist and fingertips visible. Hold each pose briefly. Click, play/pause, and volume gestures fire once per hold.

If the webcam cannot open, check Windows camera permissions for desktop apps and close other programs using the webcam. Play/pause needs an app that responds to the Windows media key.

## Test sample landmarks

Run the built-in example checks. They cover all seven gestures, an unrecognized pose, and no hand, with left and right hand coordinates.

```powershell
.\.venv\Scripts\python.exe gestures.py
```

## Project files

| File | Purpose |
| --- | --- |
| `main.py` | Builds the Tkinter window, updates the labels and preview, and handles the buttons and F8. |
| `camera.py` | Reads and mirrors the webcam frames with OpenCV, runs MediaPipe, and draws the landmarks. |
| `gestures.py` | Checks finger extension, pinch distance, and thumb direction. Contains the sample tests. |
| `controls.py` | Smooths cursor motion, applies action cooldowns, and sends input through PyAutoGUI or reports it in test mode. |
| `requirements.txt` | Pins the Python packages used by the app. |
| `hand_landmarker.task` | Holds the pre-trained MediaPipe model used to find 21 landmarks on the hand. |
| `README.md` | Explains setup, gestures, and testing. |

Google's bundled Hand Landmarker model is distributed under Apache License 2.0. [Model license](MEDIAPIPE_MODEL_LICENSE.txt) · [Google model card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf)
