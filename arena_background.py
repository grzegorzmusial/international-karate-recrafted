"""Animated layers for the Sydney harbour painting."""
import math

import numpy as np
import pygame as pg


REFERENCE_SIZE = (960, 540)
WATER_ORIGIN = (40, 240)
CLOUD_ORIGIN = (235, 0)
SUN_CENTER = (686, 188)


class PaintedLayer:
    def __init__(self, mask_path, origin, target_size):
        mask = pg.image.load(str(mask_path))
        self.surface = pg.Surface(mask.get_size(), pg.SRCALPHA)
        pg.surfarray.pixels_alpha(self.surface)[:] = pg.surfarray.array3d(mask)[:, :, 0]
        self.rect = self.surface.get_rect(topleft=origin)
        scale_x, scale_y = (a / b for a, b in zip(target_size, REFERENCE_SIZE))
        x = round(self.rect.left * scale_x)
        y = round(self.rect.top * scale_y)
        width = round(self.rect.right * scale_x) - x
        height = round(self.rect.bottom * scale_y) - y
        self.destination = (x, y)
        self.scaled = pg.Surface((width, height), pg.SRCALPHA)

    def scale(self):
        pg.transform.smoothscale(self.surface, self.scaled.get_size(), self.scaled)

    def composite(self, scene, backdrop):
        region = self.scaled.get_rect(topleft=self.destination)
        scene.blit(backdrop, self.destination, region)
        scene.blit(self.scaled, self.destination)


class ArenaBackground:
    def __init__(self, assets, target_size):
        painting = pg.image.load(str(assets / 'sydney-sunset.png')).convert()
        self.backdrop = pg.transform.smoothscale(painting, target_size)
        self.scene = self.backdrop.copy()
        texture = pg.transform.smoothscale(painting, REFERENCE_SIZE)
        self.water = PaintedLayer(assets / 'water-mask.png', WATER_ORIGIN, target_size)
        water_rect = self.water.rect.inflate(24, 12)
        rgb_mask = np.uint32(sum(self.water.surface.get_masks()[:3]))
        water_rgb = pg.surfarray.array3d(texture.subsurface(water_rect))
        self.water_colors = pg.surfarray.map_array(self.water.surface, water_rgb) & rgb_mask
        self.water_alpha = pg.surfarray.array2d(self.water.surface) & ~rgb_mask
        self.water_x = np.arange(12, 12 + self.water.rect.width, dtype=np.int32)[:, None]
        self.water_y = np.arange(6, 6 + self.water.rect.height, dtype=np.int32)[None, :]
        depth = (self.water_y - 6) / (self.water.rect.height - 1)
        self.wave_phase = (0.065 * self.water_x + 10.5 * np.log1p(6 * depth)).astype(np.float32)
        self.wave_height = (0.5 + 2.4 * depth).astype(np.float32)
        self.current_phase = (0.19 * self.water_y).astype(np.float32)
        self.current_width = (1.0 + 5.5 * depth).astype(np.float32)

        self.clouds = PaintedLayer(assets / 'cloud-mask.png', CLOUD_ORIGIN, target_size)
        cloud_rect = self.clouds.rect.inflate(60, 0)
        self.cloud_source = texture.subsurface(cloud_rect).copy()
        self.cloud_colors = pg.Surface(self.clouds.rect.size).convert()
        self.cloud_area = self.cloud_colors.get_rect()
        self.cloud_frame = -1
        self.water_frame = -1

        x, y = np.ogrid[-55:56, -55:56]
        radius = np.sqrt(x * x + y * y)
        # Keep the painted solar disk. The warm haze around it changes intensity.
        alpha = 94 * np.exp(-((radius - 10) / 22) ** 2) * np.clip((54 - radius) / 20, 0, 1)
        alpha *= np.clip((radius - 7) / 6, 0, 1)
        glow = pg.Surface(alpha.shape, pg.SRCALPHA)
        glow.fill((255, 216, 114))
        pg.surfarray.pixels_alpha(glow)[:] = alpha.astype(np.uint8)
        scale_x, scale_y = (a / b for a, b in zip(target_size, REFERENCE_SIZE))
        self.glow = pg.transform.smoothscale(glow, (round(111 * scale_x), round(111 * scale_y)))
        self.glow_rect = self.glow.get_rect(center=(
            round(SUN_CENTER[0] * scale_x), round(SUN_CENTER[1] * scale_y)))

    def draw(self, target, elapsed):
        cloud_frame = int(elapsed * 15)
        if cloud_frame != self.cloud_frame:
            self.update_clouds(cloud_frame / 15)
            self.clouds.composite(self.scene, self.backdrop)
            self.cloud_frame = cloud_frame

        water_frame = int(elapsed * 30)
        if water_frame != self.water_frame:
            self.update_water(water_frame / 30)
            self.water.composite(self.scene, self.backdrop)
            self.water_frame = water_frame

        target.blit(self.scene, (0, 0))
        self.glow.set_alpha(round(146 + 63 * math.sin(elapsed * 1.3)))
        target.blit(self.glow, self.glow_rect)

    def update_clouds(self, elapsed):
        shift = 24 * math.sin(elapsed * 0.095)
        whole = math.floor(shift)
        self.cloud_area.x = 30 - whole
        self.cloud_source.set_alpha(None)
        self.cloud_colors.blit(self.cloud_source, (0, 0), self.cloud_area)
        self.cloud_area.x -= 1
        self.cloud_source.set_alpha(round((shift - whole) * 255))
        self.cloud_colors.blit(self.cloud_source, (0, 0), self.cloud_area)
        pg.surfarray.pixels3d(self.clouds.surface)[:] = pg.surfarray.pixels3d(self.cloud_colors)
        self.clouds.scale()

    def update_water(self, elapsed):
        ripple = np.sin(self.wave_phase - elapsed * 4.4)
        current = np.sin(self.current_phase - elapsed * 2.6) * self.current_width
        elevation = ripple * self.wave_height
        source_x = self.water_x + np.rint(current + elevation).astype(np.int32)
        source_y = self.water_y + np.rint(elevation).astype(np.int32)
        pg.surfarray.pixels2d(self.water.surface)[:] = self.water_colors[source_x, source_y] | self.water_alpha
        self.water.scale()
