import os
import sys
import pygame
from typing import Dict, Optional, Tuple


# 兼容 PyInstaller：优先使用 _MEIPASS 目录中的资源
_BASE = getattr(sys, "_MEIPASS", None)
if _BASE and os.path.isdir(_BASE):
    ROOT = _BASE
else:
    ROOT = os.path.dirname(os.path.dirname(__file__))
IMG_ROOT = os.path.join(ROOT, "assets", "images")
SND_ROOT = os.path.join(ROOT, "assets", "sounds")

_image_cache: Dict[Tuple[str, Optional[Tuple[int, int]]], pygame.Surface] = {}
_sound_cache: Dict[str, pygame.mixer.Sound] = {}
_bgm_loaded: Optional[str] = None
_master_muted: bool = False
_sfx_volume_scale: float = 1.0
_bgm_volume_scale: float = 1.0


def _safe_path(root: str, rel: str) -> str:
    path = os.path.normpath(os.path.join(root, rel))
    if not path.startswith(root):
        raise ValueError("unsafe asset path")
    return path


def ensure_audio_initialized() -> None:
    if not pygame.get_init():
        pygame.init()
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except Exception:
            # 某些环境下无声卡也允许继续运行
            pass


def load_image(rel_path: str, size: Optional[Tuple[int, int]] = None) -> Optional[pygame.Surface]:
    key = (rel_path, size)
    if key in _image_cache:
        return _image_cache[key]
    full = _safe_path(IMG_ROOT, rel_path)
    if not os.path.exists(full):
        return None
    # 在无显示环境（如服务端）避免 convert_alpha 依赖显示初始化
    try:
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            surf = pygame.image.load(full).convert_alpha()
        else:
            surf = pygame.image.load(full)
    except Exception:
        # 兜底加载
        surf = pygame.image.load(full)
    if size:
        surf = pygame.transform.smoothscale(surf, size)
    _image_cache[key] = surf
    return surf


def load_spritesheet_strip(rel_path: str, frames: int, scale: Optional[Tuple[int, int]] = None) -> Optional[list[pygame.Surface]]:
    """按横向等宽帧切割爆炸等序列帧。"""
    key = (rel_path, ("strip", frames, scale))
    if key in _image_cache:
        return _image_cache[key]  # type: ignore
    full = _safe_path(IMG_ROOT, rel_path)
    if not os.path.exists(full):
        return None
    sheet = pygame.image.load(full).convert_alpha()
    w, h = sheet.get_size()
    fw = max(1, w // max(1, frames))
    result: list[pygame.Surface] = []
    for i in range(frames):
        rect = pygame.Rect(i * fw, 0, fw, h)
        frame = sheet.subsurface(rect).copy()
        if scale:
            frame = pygame.transform.smoothscale(frame, scale)
        result.append(frame)
    _image_cache[key] = result  # type: ignore
    return result


def load_spritesheet_grid(rel_path: str, cols: int, rows: int, scale: Optional[Tuple[int, int]] = None) -> Optional[list[pygame.Surface]]:
    """按网格切割序列帧（例如3x3爆炸）。"""
    key = (rel_path, ("grid", cols, rows, scale))
    if key in _image_cache:
        return _image_cache[key]  # type: ignore
    full = _safe_path(IMG_ROOT, rel_path)
    if not os.path.exists(full):
        return None
    sheet = pygame.image.load(full).convert_alpha()
    sw, sh = sheet.get_size()
    fw = max(1, sw // max(1, cols))
    fh = max(1, sh // max(1, rows))
    frames: list[pygame.Surface] = []
    for r in range(rows):
        for c in range(cols):
            rect = pygame.Rect(c * fw, r * fh, fw, fh)
            frame = sheet.subsurface(rect).copy()
            if scale:
                frame = pygame.transform.smoothscale(frame, scale)
            frames.append(frame)
    _image_cache[key] = frames  # type: ignore
    return frames

def load_spritesheet_auto_strip(rel_path: str, scale: Optional[Tuple[int, int]] = None) -> Optional[list[pygame.Surface]]:
    """
    自动识别“横向等宽（正方形）”子弹/小物件序列帧：
    - 规则：若整图宽度可被高度整除，视为横向 N 帧（帧宽=高度）；否则返回单帧。
    - 可选按 scale 尺寸缩放（建议传入与游戏内渲染尺寸一致，如 (8,16) 或 (12,24)）。
    """
    key = (rel_path, ("auto_strip", scale))
    if key in _image_cache:
        return _image_cache[key]  # type: ignore
    full = _safe_path(IMG_ROOT, rel_path)
    if not os.path.exists(full):
        return None
    sheet = pygame.image.load(full).convert_alpha()
    sw, sh = sheet.get_size()
    # 默认单帧
    frames: list[pygame.Surface] = []
    if sh > 0 and sw % sh == 0:
        num = max(1, sw // sh)
        fw, fh = sh, sh
        for i in range(num):
            rect = pygame.Rect(i * fw, 0, fw, fh)
            frame = sheet.subsurface(rect).copy()
            if scale:
                frame = pygame.transform.smoothscale(frame, scale)
            frames.append(frame)
    else:
        frame = sheet
        if scale:
            frame = pygame.transform.smoothscale(frame, scale)
        frames.append(frame)
    _image_cache[key] = frames  # type: ignore
    return frames

def load_sound(rel_path: str, volume: float = 0.8) -> Optional[pygame.mixer.Sound]:
    ensure_audio_initialized()
    if rel_path in _sound_cache:
        return _sound_cache[rel_path]
    full = _safe_path(SND_ROOT, rel_path)
    if not os.path.exists(full) or not pygame.mixer.get_init():
        return None
    snd = pygame.mixer.Sound(full)
    snd.set_volume(volume * (_sfx_volume_scale if not _master_muted else 0.0))
    _sound_cache[rel_path] = snd
    return snd


def play_sound(rel_path: str, volume: float = 0.8) -> None:
    if _master_muted:
        return
    snd = load_sound(rel_path, volume)
    if snd is not None:
        # 确保运行时音量缩放
        snd.set_volume(volume * (_sfx_volume_scale if not _master_muted else 0.0))
        snd.play()


def play_bgm(rel_path: str, volume: float = 0.4, loop: bool = True) -> None:
    global _bgm_loaded
    ensure_audio_initialized()
    full = _safe_path(SND_ROOT, rel_path)
    if not os.path.exists(full) or not pygame.mixer.get_init():
        return
    if _bgm_loaded != full:
        try:
            pygame.mixer.music.load(full)
            _bgm_loaded = full
        except Exception:
            # MP3文件可能损坏或格式不兼容，静默失败
            return
    try:
        eff = 0.0 if _master_muted else volume * _bgm_volume_scale
        pygame.mixer.music.set_volume(eff)
        pygame.mixer.music.play(-1 if loop else 0)
    except Exception:
        # 播放失败时静默处理
        pass


def stop_bgm() -> None:
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()


def set_audio_config(muted: Optional[bool] = None, sfx_scale: Optional[float] = None, bgm_scale: Optional[float] = None) -> None:
    """设置主静音与音量缩放（0.0~1.0）。"""
    global _master_muted, _sfx_volume_scale, _bgm_volume_scale
    if muted is not None:
        _master_muted = bool(muted)
    if sfx_scale is not None:
        _sfx_volume_scale = max(0.0, min(1.0, float(sfx_scale)))
    if bgm_scale is not None:
        _bgm_volume_scale = max(0.0, min(1.0, float(bgm_scale)))
    # 立即更新 BGM 音量
    if pygame.mixer.get_init():
        cur = pygame.mixer.music.get_volume()
        # 用当前曲目的“原始音量”无从得知，按比例更新为 bgm_scale/mute
        new_v = 0.0 if _master_muted else min(1.0, max(0.0, _bgm_volume_scale * cur if cur > 0 else _bgm_volume_scale))
        pygame.mixer.music.set_volume(new_v)



def load_gif_frames(rel_path: str, scale: Optional[Tuple[int, int]] = None) -> Optional[list[pygame.Surface]]:
    """
    尝试使用 Pillow 读取 GIF 动画帧；若不可用或失败则返回 None。
    """
    key = (rel_path, ("gif_frames", scale))
    if key in _image_cache:
        return _image_cache[key]  # type: ignore
    full = _safe_path(IMG_ROOT, rel_path)
    if not os.path.exists(full):
        return None
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return None
    frames: list[pygame.Surface] = []
    try:
        img = Image.open(full)
        for frame_idx in range(getattr(img, "n_frames", 1)):
            img.seek(frame_idx)
            rgba = img.convert("RGBA")
            mode_str = rgba.tobytes()
            surf = pygame.image.fromstring(mode_str, rgba.size, "RGBA")
            if scale:
                surf = pygame.transform.smoothscale(surf, scale)
            frames.append(surf.convert_alpha())
    except Exception:
        return None
    _image_cache[key] = frames  # type: ignore
    return frames
