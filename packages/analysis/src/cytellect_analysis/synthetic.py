"""Seeded synthetic demonstration only. No biological performance claim."""
import numpy as np
from scipy.ndimage import gaussian_filter


def synthetic_field(seed=0, size=256):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:size, :size]
    nuclei = np.zeros((size, size), np.uint32)
    nucleoli = np.zeros_like(nuclei)
    dapi = np.full((size, size), 120., dtype=float)
    ncl = np.full_like(dapi, 100.)
    gfp = np.full_like(dapi, 80.)
    label = 1
    for row in range(3):
        for col in range(3):
            x = 48 + col * 79 + rng.integers(-4, 5)
            y = 46 + row * 78 + rng.integers(-4, 5)
            area = ((xx-x)/25)**2 + ((yy-y)/29)**2 < 1
            nuclei[area] = label
            dapi[area] += 1700 + rng.uniform(0, 300)
            ncl[area] += 250 + seed % 3 * 90
            gfp[area] += 300 + rng.uniform(0, 1600)
            for k, (dx, dy) in enumerate([(-8,-7), (8,9)]):
                small = (xx-x-dx)**2 + (yy-y-dy)**2 < (5+k)**2
                small &= area
                nucleoli[small] = label * 2 - 1 + k
                ncl[small] += 2000 - seed % 3 * 280
                dapi[small] -= 400
            label += 1
    channels = {}
    for key, image in [("dapi", dapi), ("ncl", ncl), ("gfp", gfp)]:
        image = gaussian_filter(image, .8) + rng.normal(0, 12, image.shape)
        channels[key] = np.clip(image, 0, 65535).astype(np.uint16)
    return channels, nuclei, nucleoli
