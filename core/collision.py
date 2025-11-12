import pygame
from typing import Iterable


def rect_collide(a: pygame.Rect, b: pygame.Rect) -> bool:
    return a.colliderect(b)


def any_collide(rect: pygame.Rect, rects: Iterable[pygame.Rect]) -> bool:
    return any(rect.colliderect(r) for r in rects)

