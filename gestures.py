"""Classify one hand pose from MediaPipe's 21 landmarks."""

from enum import Enum
from math import dist


class Gesture(Enum):
    NO_HAND = "No hand"
    UNKNOWN = "Unrecognized"
    POINT = "Index finger"
    PINCH = "Thumb and index pinch"
    SCROLL = "Two fingers"
    PALM = "Open palm"
    THUMBS_UP = "Thumbs up"
    THUMBS_DOWN = "Thumbs down"
    FIST = "Closed fist"


def _finger_extended(points, base, palm_size):
    knuckle, joint, _, tip = points[base:base + 4]
    reach = dist(knuckle, tip)
    bent_length = dist(knuckle, joint) + dist(joint, tip)
    # A straight finger reaches past its middle joint, away from the wrist.
    return (
        reach > dist(knuckle, joint) + 0.12 * palm_size
        and reach >= 0.82 * bent_length
        and dist(points[0], tip) > dist(points[0], joint)
    )


def classify(landmarks, aspect_ratio=1.0):
    """Return a single gesture for a sequence of normalized landmarks."""
    if not landmarks:
        return Gesture.NO_HAND
    if len(landmarks) != 21:
        return Gesture.UNKNOWN

    # Convert x and z to the same scale as y before measuring distances.
    points = [(p.x * aspect_ratio, p.y, p.z * aspect_ratio) for p in landmarks]
    wrist, middle_knuckle = points[0], points[9]
    palm_size = max(dist(wrist, middle_knuckle), dist(points[5], points[17]))
    if palm_size < 0.0001:
        return Gesture.UNKNOWN

    fingers = tuple(_finger_extended(points, base, palm_size) for base in (5, 9, 13, 17))
    thumb_tip, index_tip = points[4], points[8]

    # Check the pinch first. Allow more error in estimated depth than in x/y.
    # The neighboring joints help distinguish a pinch from a curled fist.
    if (
        dist(thumb_tip[:2], index_tip[:2]) < 0.26 * palm_size
        and abs(thumb_tip[2] - index_tip[2]) < 0.36 * palm_size
        and dist(index_tip, points[5]) > 0.42 * palm_size
        and dist(index_tip, points[12]) > 0.32 * palm_size
    ):
        return Gesture.PINCH

    palm_center = tuple((a + b) / 2 for a, b in zip(wrist, middle_knuckle))
    thumb_out = (
        dist(thumb_tip, palm_center) > dist(points[3], palm_center) + 0.08 * palm_size
        and dist(thumb_tip, points[5]) > 0.48 * palm_size
    )

    if all(fingers) and thumb_out:
        return Gesture.PALM
    if fingers == (True, True, False, False):
        return Gesture.SCROLL
    if fingers == (True, False, False, False):
        return Gesture.POINT

    if not any(fingers):
        if not thumb_out:
            return Gesture.FIST
        dx = thumb_tip[0] - points[2][0]
        dy = thumb_tip[1] - points[2][1]
        if abs(dy) > max(0.45 * palm_size, 1.2 * abs(dx)):
            return Gesture.THUMBS_UP if dy < 0 else Gesture.THUMBS_DOWN

    return Gesture.UNKNOWN


def _check_samples():
    from types import SimpleNamespace

    # Each group follows MediaPipe order: wrist, thumb, index, middle, ring, pinky.
    wrist = [(0.52, 0.75)]
    tucked_thumb = [(0.43, 0.68), (0.37, 0.61), (0.40, 0.53), (0.48, 0.55)]
    open_thumb = [(0.43, 0.68), (0.37, 0.61), (0.31, 0.55), (0.25, 0.50)]
    raised_thumb = [(0.43, 0.68), (0.37, 0.60), (0.36, 0.49), (0.35, 0.39)]
    pinch_thumb = [(0.43, 0.68), (0.36, 0.61), (0.32, 0.54), (0.34, 0.48)]
    bent_index = [(0.43, 0.55), (0.43, 0.48), (0.44, 0.51), (0.44, 0.55)]
    bent_middle = [(0.52, 0.53), (0.52, 0.45), (0.52, 0.49), (0.52, 0.55)]
    bent_ring = [(0.60, 0.55), (0.60, 0.49), (0.59, 0.52), (0.59, 0.57)]
    bent_pinky = [(0.67, 0.58), (0.67, 0.53), (0.66, 0.56), (0.65, 0.61)]
    open_index = [(0.43, 0.55), (0.42, 0.43), (0.41, 0.36), (0.40, 0.31)]
    open_middle = [(0.52, 0.53), (0.52, 0.40), (0.52, 0.32), (0.52, 0.27)]
    open_ring = [(0.60, 0.55), (0.62, 0.43), (0.63, 0.36), (0.64, 0.32)]
    open_pinky = [(0.67, 0.58), (0.71, 0.49), (0.73, 0.44), (0.75, 0.40)]
    pinch_index = [(0.43, 0.55), (0.41, 0.45), (0.37, 0.44), (0.35, 0.47)]

    folded_fingers = bent_index + bent_middle + bent_ring + bent_pinky
    thumbs_up = wrist + raised_thumb + folded_fingers
    samples = {
        Gesture.NO_HAND: [],
        Gesture.UNKNOWN: wrist + tucked_thumb + bent_index + open_middle + bent_ring + bent_pinky,
        Gesture.POINT: wrist + tucked_thumb + open_index + bent_middle + bent_ring + bent_pinky,
        Gesture.PINCH: wrist + pinch_thumb + pinch_index + bent_middle + bent_ring + bent_pinky,
        Gesture.SCROLL: wrist + tucked_thumb + open_index + open_middle + bent_ring + bent_pinky,
        Gesture.PALM: wrist + open_thumb + open_index + open_middle + open_ring + open_pinky,
        Gesture.THUMBS_UP: thumbs_up,
        Gesture.THUMBS_DOWN: [(1 - x, 1 - y) for x, y in thumbs_up],
        Gesture.FIST: wrist + tucked_thumb + folded_fingers,
    }

    checked = 0
    for expected, coordinates in samples.items():
        for direction in (1, -1):
            # Match the 4:3 camera geometry and check both left and right hands.
            landmarks = [
                SimpleNamespace(x=0.5 + direction * (x - 0.5) * 0.75, y=y, z=0.0)
                for x, y in coordinates
            ]
            if expected is Gesture.PINCH:
                # Contact can still have a small estimated depth difference.
                landmarks[8].z = -0.055
            actual = classify(landmarks, aspect_ratio=4 / 3)
            if actual is not expected:
                raise AssertionError(f"Expected {expected.value}, got {actual.value}")
            checked += 1
        print(f"PASS  {expected.value}")
    print(f"{checked} sample landmark checks passed.")


if __name__ == "__main__":
    _check_samples()
