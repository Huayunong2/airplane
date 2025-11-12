import sys
import os
import asyncio
import json
import pygame

if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.engine import Engine
from utils.config import load_config
from utils.logger import get_logger


logger = get_logger("multiplayer_client")
CONFIG = load_config()


def choose_font(size: int):
    pygame.font.init()
    return pygame.font.SysFont("Microsoft YaHei", size) or pygame.font.SysFont(None, size)


async def ws_task(status: dict):
    import websockets
    uri = f"ws://{CONFIG['network']['ws_host']}:{CONFIG['network']['ws_port']}"
    try:
        async with websockets.connect(uri, ping_interval=10) as ws:
            status["state"] = "已连接"
            async for msg in ws:
                status["last_msg"] = msg
    except Exception as e:
        status["state"] = f"连接失败: {e}"


def run(as_child: bool = True) -> None:
    engine = Engine()
    font = choose_font(22)
    status = {"state": "连接中...", "last_msg": ""}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(ws_task(status))

    running = True
    while running:
        engine.begin_frame()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # ESC 返回上一级，不退出整个程序
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    running = False

        t1 = font.render("多人联机（预览）", True, (180, 230, 255))
        engine.screen.blit(t1, (20, 20))
        t2 = font.render(f"状态: {status['state']}", True, (220, 220, 220))
        engine.screen.blit(t2, (20, 60))
        t3 = font.render("按 ESC/BACKSPACE 返回主菜单", True, (220, 220, 220))
        engine.screen.blit(t3, (20, 100))

        engine.end_frame()
        # pump event loop without blocking
        try:
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass

    try:
        task.cancel()
        loop.stop()
        loop.close()
    except Exception:
        pass

    if not as_child:
        engine.quit()
        pygame.quit()


if __name__ == "__main__":
    run()

