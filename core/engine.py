import pygame
from utils.config import load_config


class Engine:
    def __init__(self) -> None:
        self.config = load_config()
        pygame.init()
        window = self.config["window"]
        flags = 0
        if window.get("fullscreen"):
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((window["width"], window["height"]), flags)
        pygame.display.set_caption(window["title"])
        self.clock = pygame.time.Clock()
        self.fps = self.config["fps"]

    def begin_frame(self) -> None:
        self.clock.tick(self.fps)
        self.screen.fill((10, 10, 20))

    def end_frame(self) -> None:
        pygame.display.flip()

    def quit(self) -> None:
        pygame.quit()

