"""Vision module - gives Atlas eyes to read the screen using OCR."""

import gc
import logging

logger = logging.getLogger(__name__)


class Eyes:
    """Captures screenshots and reads text from them using EasyOCR.

    Provides methods to:
    - read_text(): get all text with bounding boxes and confidence
    - read_screen(): get all screen text as a single string
    - find_text(): find the screen coordinates of specific text
    - look(): convenience method for read_screen()

    Optimizations:
    - Uses BILINEAR resize instead of LANCZOS (faster, adequate for OCR)
    - Caches last OCR results to avoid duplicate captures in agent steps
    """

    def __init__(self, config: dict):
        eyes_cfg = config.get("eyes", {})
        self.unload_after_use = eyes_cfg.get("unload_after_use", True)
        self._use_gpu = eyes_cfg.get("gpu", "auto")

        self.reader = None
        self._loaded = False
        # Store the original screenshot size for coordinate mapping
        self._last_screenshot_size = None
        # Cache last OCR results to avoid duplicate processing in agent steps
        self._cached_results = None
        self._cached_screen_text = None

    def initialize(self):
        """Load the EasyOCR reader into memory."""
        import easyocr
        import torch

        gpu = self._use_gpu
        if gpu == "auto":
            gpu = torch.cuda.is_available()

        logger.info("Loading EasyOCR (gpu=%s)...", gpu)
        self.reader = easyocr.Reader(["en"], gpu=gpu)
        self._loaded = True
        logger.info("EasyOCR loaded.")

    def unload(self):
        """Unload the OCR reader to free RAM."""
        if self._loaded:
            del self.reader
            self.reader = None
            self._loaded = False
            gc.collect()
            logger.info("EasyOCR unloaded to free RAM.")
        self.invalidate_cache()

    def invalidate_cache(self):
        """Clear cached OCR results. Call when the screen may have changed."""
        self._cached_results = None
        self._cached_screen_text = None

    def capture_screen(self):
        """Take a screenshot of the primary monitor. Returns (image, original_size)."""
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

        original_size = img.size  # (width, height) before resize
        self._last_screenshot_size = original_size

        # Resize for faster OCR (BILINEAR is faster than LANCZOS, adequate for text)
        max_dim = 1920
        if img.width > max_dim or img.height > max_dim:
            scale = max_dim / max(img.width, img.height)
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

        return img, original_size

    def read_text(self, image=None):
        """OCR the screen and return text with bounding boxes.

        Returns cached results if available (same agent step).

        Returns:
            list of dicts: [{"text": "Login", "bbox": [[x1,y1],...], "confidence": 0.95}, ...]
            Coordinates are in ORIGINAL screen pixels (not resized).
        """
        import numpy as np

        # Return cached results if available
        if image is None and self._cached_results is not None:
            return self._cached_results

        if not self._loaded:
            self.initialize()

        if image is None:
            image, original_size = self.capture_screen()
        else:
            original_size = self._last_screenshot_size or image.size

        # Convert PIL to numpy for EasyOCR
        img_array = np.array(image)

        # Calculate scale factor to map coordinates back to real screen
        scale_x = original_size[0] / image.size[0] if image.size[0] != original_size[0] else 1.0
        scale_y = original_size[1] / image.size[1] if image.size[1] != original_size[1] else 1.0

        results = self.reader.readtext(img_array)

        parsed = []
        for bbox, text, confidence in results:
            # Scale bbox coordinates back to original screen size
            scaled_bbox = [
                [int(point[0] * scale_x), int(point[1] * scale_y)]
                for point in bbox
            ]
            parsed.append({
                "text": text,
                "bbox": scaled_bbox,
                "confidence": confidence,
            })

        # Cache results for this agent step
        if image is None or self._cached_results is None:
            self._cached_results = parsed

        return parsed

    def read_screen(self, image=None) -> str:
        """Capture screen and return all text as a single string."""
        # Return cached screen text if available
        if image is None and self._cached_screen_text is not None:
            return self._cached_screen_text

        results = self.read_text(image)
        texts = [r["text"] for r in results if r["confidence"] > 0.3]
        screen_text = " ".join(texts)

        # Cache for this agent step
        if image is None:
            self._cached_screen_text = screen_text

        return screen_text

    def find_text(self, target: str, image=None):
        """Find the center screen coordinates of specific text.

        Uses cached OCR results if available (avoids duplicate screenshot+OCR).

        Args:
            target: text to search for (case-insensitive partial match)
            image: optional PIL image (captures screen if None)

        Returns:
            (x, y) center coordinates in real screen pixels, or None if not found
        """
        results = self.read_text(image)
        target_lower = target.lower().strip()

        best_match = None
        best_confidence = 0.0

        for r in results:
            if target_lower in r["text"].lower() and r["confidence"] > best_confidence:
                best_match = r
                best_confidence = r["confidence"]

        if best_match is None:
            logger.warning("Could not find text '%s' on screen.", target)
            return None

        # Calculate center of the bounding box
        bbox = best_match["bbox"]
        cx = int(sum(p[0] for p in bbox) / len(bbox))
        cy = int(sum(p[1] for p in bbox) / len(bbox))

        logger.info(
            "Found '%s' at (%d, %d) with confidence %.2f",
            best_match["text"], cx, cy, best_confidence,
        )
        return (cx, cy)

    def look(self) -> str:
        """Capture screen, read all text, return it. Unloads model after if configured."""
        logger.info("Taking screenshot and reading text...")
        image, _ = self.capture_screen()
        text = self.read_screen(image)

        if text:
            logger.info("Screen text (first 200 chars): %s", text[:200])
        else:
            text = "I can't read any text on the screen right now."
            logger.info("No text detected on screen.")

        if self.unload_after_use:
            self.unload()

        return text
