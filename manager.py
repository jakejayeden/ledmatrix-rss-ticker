"""RSS News Ticker plugin for ChuckBuilds/LEDMatrix."""

from __future__ import annotations

import io
import os
import time
from typing import Dict, List, Optional

import feedparser
import requests
from PIL import Image, ImageDraw, ImageFont

from src.plugin_system.base_plugin import BasePlugin


class RSSTickerPlugin(BasePlugin):
    """Scrolling RSS/Atom headline ticker with per-feed static logos."""

    # LEDMatrix uses this flag to put animated/scroller plugins into its
    # high-FPS ScreenRunner loop (currently paced at 8 ms / up to 125 FPS).
    # Without it the plugin is treated as a static screen and display() is
    # called at roughly 1 Hz, which makes a time-based ticker jump in steps.
    enable_scrolling = True

    FONT_PATH = "assets/fonts/PressStart2P-Regular.ttf"

    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        self._headlines: Dict[int, List[str]] = {}
        self._positions: Dict[int, int] = {}
        self._logos: Dict[int, Optional[Image.Image]] = {}
        self._last_refresh = 0.0
        self._active_feed_pos = 0
        self._batch: List[str] = []
        self._batch_started = time.monotonic()
        self._scroll_x = 0.0
        self._last_frame = time.monotonic()
        self._cycle_complete = False
        self._load_config(config)
        self._load_font()
        self.update()

    def _load_config(self, config):
        self.feeds = [
            f for f in config.get("feeds", [])
            if isinstance(f, dict) and f.get("enabled", True)
        ]
        self.headlines_per_feed = int(config.get("headlines_per_feed", 3))
        self.feed_rotation_seconds = float(config.get("feed_rotation_seconds", 30))
        self.rss_refresh_seconds = float(config.get("rss_refresh_seconds", 300))
        self.max_headlines_per_feed = int(config.get("max_headlines_per_feed", 50))
        self.scroll_speed = float(config.get("scroll_speed_px_per_second", 30))
        self.headline_gap = int(config.get("headline_gap_px", 18))
        self.logo_width = int(config.get("logo_width", 28))
        self.background_color = tuple(config.get("background_color", [0, 0, 0]))

    def on_config_change(self, new_config):
        super().on_config_change(new_config)
        self._load_config(self.config)
        self._headlines.clear()
        self._positions.clear()
        self._logos.clear()
        self._last_refresh = 0
        self._active_feed_pos = 0
        self._batch = []
        self._cycle_complete = False
        self.update()

    def _load_font(self):
        try:
            self.font = ImageFont.truetype(self.FONT_PATH, 8)
        except Exception:
            self.font = ImageFont.load_default()
            self.logger.warning("Could not load %s; using Pillow default font", self.FONT_PATH)

    def get_update_interval(self):
        return max(30.0, self.rss_refresh_seconds)

    def update(self):
        now = time.time()
        if self._last_refresh and now - self._last_refresh < self.rss_refresh_seconds:
            return

        for idx, feed in enumerate(self.feeds):
            url = str(feed.get("url", "")).strip()
            if not url:
                continue
            try:
                parsed = feedparser.parse(url)
                titles = []
                seen = set()
                for entry in parsed.entries[: self.max_headlines_per_feed]:
                    title = " ".join(str(entry.get("title", "")).split())
                    if title and title not in seen:
                        titles.append(title)
                        seen.add(title)
                if titles:
                    old_pos = self._positions.get(idx, 0)
                    self._headlines[idx] = titles
                    self._positions[idx] = old_pos % len(titles)
                else:
                    self.logger.warning("No headlines found for feed %s", feed.get("name", url))
            except Exception as exc:
                self.logger.warning("Failed to fetch feed %s: %s", url, exc)

            logo_ref = str(feed.get("logo", "")).strip()
            if idx not in self._logos or self._logos[idx] is None:
                self._logos[idx] = self._load_logo(logo_ref)

        self._last_refresh = now
        if not self._batch:
            self._select_next_batch(initial=True)

    def _load_logo(self, logo_ref: str) -> Optional[Image.Image]:
        if not logo_ref:
            return None
        try:
            if logo_ref.startswith(("http://", "https://")):
                response = requests.get(logo_ref, timeout=8)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
            else:
                path = logo_ref
                if not os.path.isabs(path):
                    local = os.path.join(os.path.dirname(__file__), path)
                    path = local if os.path.exists(local) else path
                image = Image.open(path)
            return image.convert("RGBA")
        except Exception as exc:
            self.logger.warning("Could not load logo %s: %s", logo_ref, exc)
            return None

    def _available_feed_indices(self) -> List[int]:
        return [idx for idx in range(len(self.feeds)) if self._headlines.get(idx)]

    def _select_next_batch(self, initial=False):
        available = self._available_feed_indices()
        if not available:
            self._batch = []
            return

        if initial:
            self._active_feed_pos = 0
        else:
            self._active_feed_pos += 1
            if self._active_feed_pos >= len(available):
                self._active_feed_pos = 0
                self._cycle_complete = True

        feed_idx = available[self._active_feed_pos]
        headlines = self._headlines[feed_idx]
        start = self._positions.get(feed_idx, 0) % len(headlines)
        count = min(self.headlines_per_feed, len(headlines))
        self._batch = [headlines[(start + i) % len(headlines)] for i in range(count)]
        self._positions[feed_idx] = (start + count) % len(headlines)
        self._current_feed_idx = feed_idx
        self._batch_started = time.monotonic()
        self._scroll_x = 0.0
        self._last_frame = time.monotonic()

    def _ticker_text(self) -> str:
        space_width = max(1, self._text_width(" "))
        spaces = max(1, int(round(self.headline_gap / space_width)))
        return (" " * spaces).join(self._batch)

    def _text_width(self, text: str) -> int:
        if not text:
            return 0
        box = self.font.getbbox(text)
        return max(0, box[2] - box[0])

    def _advance_if_needed(self, viewport_width: int):
        text_width = self._text_width(self._ticker_text())
        elapsed = time.monotonic() - self._batch_started
        finished_scroll = self._scroll_x > text_width + viewport_width
        timed_out = elapsed >= self.feed_rotation_seconds
        if finished_scroll or timed_out:
            self._select_next_batch(initial=False)

    def _render_frame(self, width: int, height: int) -> Image.Image:
        frame = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(frame)

        if not self._batch:
            message = "NO RSS DATA"
            bbox = draw.textbbox((0, 0), message, font=self.font)
            x = max(0, (width - (bbox[2] - bbox[0])) // 2)
            y = max(0, (height - (bbox[3] - bbox[1])) // 2)
            draw.text((x, y), message, font=self.font, fill=(255, 80, 80))
            return frame

        feed = self.feeds[self._current_feed_idx]
        logo_zone = min(max(12, self.logo_width), max(12, width // 2))
        logo = self._logos.get(self._current_feed_idx)

        if logo is not None:
            max_w = max(1, logo_zone - 2)
            max_h = max(1, height - 2)
            scale = min(max_w / logo.width, max_h / logo.height)
            size = (max(1, int(logo.width * scale)), max(1, int(logo.height * scale)))
            fitted = logo.resize(size, Image.Resampling.LANCZOS)
            lx = max(0, (logo_zone - fitted.width) // 2)
            ly = max(0, (height - fitted.height) // 2)
            frame.paste(fitted, (lx, ly), fitted)
        else:
            label = str(feed.get("name", "RSS"))[:4].upper()
            bbox = draw.textbbox((0, 0), label, font=self.font)
            lx = max(0, (logo_zone - (bbox[2] - bbox[0])) // 2)
            ly = max(0, (height - (bbox[3] - bbox[1])) // 2)
            draw.text((lx, ly), label, font=self.font, fill=(180, 180, 180))

        viewport_x = logo_zone + 1
        viewport_width = max(1, width - viewport_x)
        ticker = Image.new("RGB", (viewport_width, height), self.background_color)
        ticker_draw = ImageDraw.Draw(ticker)
        text = self._ticker_text()
        color = tuple(feed.get("text_color", [255, 255, 255]))
        bbox = ticker_draw.textbbox((0, 0), text, font=self.font)
        text_h = bbox[3] - bbox[1]
        text_y = max(0, (height - text_h) // 2 - bbox[1])
        text_x = int(viewport_width - self._scroll_x)
        ticker_draw.text((text_x, text_y), text, font=self.font, fill=color)
        frame.paste(ticker, (viewport_x, 0))
        return frame

    def display(self, force_clear=False):
        try:
            width = int(self.display_manager.width)
            height = int(self.display_manager.height)
            now = time.monotonic()
            dt = min(0.25, max(0.0, now - self._last_frame))
            self._last_frame = now
            self._scroll_x += self.scroll_speed * dt

            logo_zone = min(max(12, self.logo_width), max(12, width // 2))
            viewport_width = max(1, width - logo_zone - 1)
            self._advance_if_needed(viewport_width)
            frame = self._render_frame(width, height)

            if force_clear:
                self.display_manager.clear()
            canvas = getattr(self.display_manager, "image", None)
            if canvas is None:
                raise RuntimeError("Display manager does not expose image canvas")
            canvas.paste(frame, (0, 0))
            self.display_manager.update_display()
        except Exception as exc:
            self.logger.error("RSS ticker display error: %s", exc, exc_info=True)

    def supports_dynamic_duration(self) -> bool:
        return True

    def is_cycle_complete(self) -> bool:
        return self._cycle_complete

    def reset_cycle_state(self):
        self._cycle_complete = False
        self._batch_started = time.monotonic()
        self._scroll_x = 0.0
        self._last_frame = time.monotonic()
        if not self._batch:
            self._select_next_batch(initial=True)

    def validate_config(self):
        if not super().validate_config():
            return False
        if not isinstance(self.config.get("feeds", []), list):
            self.logger.error("feeds must be an array")
            return False
        for feed in self.config.get("feeds", []):
            if not isinstance(feed, dict) or not isinstance(feed.get("url", ""), str):
                self.logger.error("Each feed must be an object containing a string url")
                return False
        return True
