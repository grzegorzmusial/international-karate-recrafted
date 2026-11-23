"""The animated regions must leave the fighting platform and landmarks intact."""
import os
from pathlib import Path
import unittest

import numpy as np
import pygame as pg

from arena_background import ArenaBackground, REFERENCE_SIZE


class ArenaBackgroundTests(unittest.TestCase):
    def test_movement_stays_in_the_sky_and_water(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        pg.display.init()
        self.addCleanup(pg.display.quit)
        pg.display.set_mode((1, 1))
        assets = Path(__file__).resolve().parent / 'assets'
        background = ArenaBackground(assets, REFERENCE_SIZE)
        screen = pg.Surface(REFERENCE_SIZE)

        background.draw(screen, 0)
        first = pg.surfarray.array3d(screen)
        background.draw(screen, 2)
        changed = np.any(first != pg.surfarray.array3d(screen), axis=2)

        self.assertTrue(changed[400:765, 90:140].any(), 'clouds')
        self.assertTrue(changed[650:722, 171:215].any(), 'sun')
        self.assertTrue(changed[160:811, 268:355].any(), 'water')
        self.assertFalse(changed[:, 402:].any(), 'fighting platform')
        self.assertFalse(changed[35:325, 114:232].any(), 'bridge and opera house')
