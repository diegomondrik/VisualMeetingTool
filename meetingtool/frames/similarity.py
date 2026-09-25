"""Structural similarity (SSIM) with numpy alone.

Same definition scikit-image uses by default for uint8 images: a uniform
7x7 window, K1 = 0.01, K2 = 0.03, data range 255, sample covariance; the mean
over every full window. Replaces the scikit-image dependency of the
original MeetingTool.
"""

import numpy as np

WINDOW = 7
K1, K2, DATA_RANGE = 0.01, 0.03, 255.0


def _window_means(x, size):
    padded = np.pad(x, ((1, 0), (1, 0)))
    integral = padded.cumsum(axis=0).cumsum(axis=1)
    sums = integral[size:, size:] - integral[:-size, size:] - integral[size:, :-size] + integral[:-size, :-size]
    return sums / (size * size)


def ssim(a, b):
    """SSIM of two grayscale images of the same shape, in [-1, 1]."""
    if a.shape != b.shape:
        raise ValueError(f"images differ in shape: {a.shape} and {b.shape}")
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    size = min(WINDOW, *a.shape)
    n = size * size
    cov_norm = n / (n - 1) if n > 1 else 1.0
    ux, uy = _window_means(a, size), _window_means(b, size)
    uxx, uyy, uxy = _window_means(a * a, size), _window_means(b * b, size), _window_means(a * b, size)
    vx = cov_norm * (uxx - ux * ux)
    vy = cov_norm * (uyy - uy * uy)
    vxy = cov_norm * (uxy - ux * uy)
    c1, c2 = (K1 * DATA_RANGE) ** 2, (K2 * DATA_RANGE) ** 2
    s = ((2 * ux * uy + c1) * (2 * vxy + c2)) / ((ux * ux + uy * uy + c1) * (vx + vy + c2))
    return float(s.mean())
