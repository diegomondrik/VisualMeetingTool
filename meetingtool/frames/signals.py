"""Scores that say how much a sampled frame adds over the previous one.

Ported from the original MeetingTool (tools/extract_frames.py): the composite
score is 0.4 x zone change + 0.3 x edge change + 0.3 x time coverage.
Inputs are grayscale uint8 arrays of the content area (camera strip removed).
"""

import numpy as np

W_ZONE = 0.4
W_EDGE = 0.3
W_TEMPORAL = 0.3


def to_gray(rgb):
    """Luminance of an RGB uint8 array, as uint8."""
    rgb = rgb.astype(np.float32)
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    return gray.astype(np.uint8)


def zone_score(prev_gray, curr_gray, grid_rows=3, grid_cols=4, local_threshold=8.0):
    """Fraction of grid zones whose mean absolute difference exceeds the
    threshold: catches a local change a global mean would miss."""
    h, w = prev_gray.shape
    zone_h, zone_w = h // grid_rows, w // grid_cols
    changed = 0
    for r in range(grid_rows):
        for c in range(grid_cols):
            window = (slice(r * zone_h, (r + 1) * zone_h), slice(c * zone_w, (c + 1) * zone_w))
            diff = np.abs(prev_gray[window].astype(np.float32) - curr_gray[window].astype(np.float32))
            if float(diff.mean()) > local_threshold:
                changed += 1
    return changed / (grid_rows * grid_cols)


def _edge_density(gray, threshold):
    g = np.pad(gray.astype(np.float32), 1, mode="edge")
    gx = (g[:-2, 2:] - g[:-2, :-2]) + 2 * (g[1:-1, 2:] - g[1:-1, :-2]) + (g[2:, 2:] - g[2:, :-2])
    gy = (g[2:, :-2] - g[:-2, :-2]) + 2 * (g[2:, 1:-1] - g[:-2, 1:-1]) + (g[2:, 2:] - g[:-2, 2:])
    return float(np.mean(np.sqrt(gx ** 2 + gy ** 2) > threshold))


def edge_score(prev_gray, curr_gray, threshold=50.0):
    """Relative change in Sobel edge density: new text, a slide transition,
    an annotation."""
    prev_density = _edge_density(prev_gray, threshold)
    curr_density = _edge_density(curr_gray, threshold)
    return min(abs(curr_density - prev_density) / max(prev_density, curr_density, 0.001), 1.0)


def temporal_score(timestamp, duration, budget, candidate_timestamps):
    """Reward samples in parts of the meeting that have no candidate yet."""
    if duration <= 0 or budget <= 0:
        return 0.5
    segment = duration / budget
    index = int(timestamp / segment)
    same = sum(1 for t in candidate_timestamps if int(t / segment) == index)
    return {0: 1.0, 1: 0.6, 2: 0.3}.get(same, 0.1)


CAMERA_SHARP_DENSITY = 0.028
CAMERA_SHARP_SHARE = 0.25


def is_camera_view(gray, step=40, visible=8):
    """Whether the content area shows a person on camera rather than a screen
    (INGOL D-176): few sharp steps between neighbouring pixels, and most visible
    steps soft. Text, tables and slides have sharp edges; a face or a room does
    not. Measured on a real meeting: camera views at most 0.021 and 0.14,
    screens at least 0.031 and 0.35. A gallery of participants is not caught:
    its tiles have sharp borders, like a slide with little text."""
    g = gray.astype(np.int16)
    gx = np.abs(np.diff(g, axis=1))[:-1]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    density = ((gx > step).mean() + (gy > step).mean()) / 2
    strongest = np.maximum(gx, gy)
    share = (strongest > step).sum() / max(1, (strongest > visible).sum())
    return bool(density < CAMERA_SHARP_DENSITY and share < CAMERA_SHARP_SHARE)


def composite_score(prev_gray, curr_gray, timestamp, duration, budget, candidate_timestamps):
    return (
        W_ZONE * zone_score(prev_gray, curr_gray)
        + W_EDGE * edge_score(prev_gray, curr_gray)
        + W_TEMPORAL * temporal_score(timestamp, duration, budget, candidate_timestamps)
    )
