import time
import pygame
from typing import List, Optional
from utils import assets


def load_explosion_frames() -> Optional[List[pygame.Surface]]:
    return assets.load_spritesheet_grid("fx/explosion_sheet.png", cols=3, rows=3, scale=(96, 96))


class Explosion:
    def __init__(self, x: int, y: int, frames: Optional[List[pygame.Surface]]) -> None:
        self.frames = frames
        self.size = 96
        self.x = x - self.size // 2
        self.y = y - self.size // 2
        self.start = time.time()
        self.frame = 0
        self.done = False

    def update(self) -> None:
        if self.frames:
            elapsed = time.time() - self.start
            self.frame = int(elapsed * 18)  # ~18 FPS
            if self.frame >= len(self.frames):
                self.done = True
        else:
            if time.time() - self.start > 0.4:
                self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        if self.frames and not self.done:
            surface.blit(self.frames[min(self.frame, len(self.frames) - 1)], (self.x, self.y))
        else:
            r = int(16 + (time.time() - self.start) * 90)
            pygame.draw.circle(surface, (255, 200, 120), (self.x, self.y), max(2, r), 2)

