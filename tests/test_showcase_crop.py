import numpy as np


def test_nuclear_window_follows_the_nuclear_stain_and_prefers_the_centre_on_ties():
    from cytellect_showcase.build import nuclear_window

    image = np.full((256, 256), 100, dtype=np.uint16)
    image[192:240, 16:64] = 4000  # the only stained area, far from the centre
    # Windows starting at y 176 or 192 and x 0 or 16 all hold it; the one nearest the centre wins.
    assert nuclear_window(image, [64, 64], 16) == [176, 16, 64, 64]
    two = np.full((256, 256), 100, dtype=np.uint16)
    two[0:32, 0:32] = 4000
    two[112:144, 112:144] = 4000  # same area, at the centre
    assert nuclear_window(two, [64, 64], 16) == [96, 96, 64, 64]
