import asyncio
import base64
import io
import time
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services.vision import VisualPerception, difference, preprocess


def frame(colour):
    image = Image.new("RGB", (80, 80), colour)
    for x in range(0, 80, 8):
        for y in range(0, 80, 8):
            image.putpixel((x, y), (255, 255, 255))
    out = io.BytesIO()
    image.save(out, "JPEG")
    return out.getvalue()


class VisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_latest_frame_and_session_isolation(self):
        one, two = VisualPerception(), VisualPerception()
        calls = []

        def infer(data, detailed=False):
            calls.append(data)
            return {"scene_summary": "A desk", "objects": ["desk"], "visible_text": [], "confidence": .8}

        with patch("services.vision.ollama_analyse", infer):
            one.start()
            one.submit(base64.b64encode(frame((100, 30, 20))).decode())
            one.submit(base64.b64encode(frame((20, 100, 30))).decode())
            self.assertEqual(one.dropped, 1)
            await asyncio.sleep(.1)
            self.assertEqual(one.context()["sequence_id"], 2)
            self.assertIsNone(two.context())
            await one.stop()
            self.assertIsNone(one.context())
            self.assertTrue(one.worker is None)
        self.assertEqual(len(calls), 1)

    async def test_inference_does_not_block_event_loop(self):
        def slow_infer(data, detailed=False):
            time.sleep(.2)
            return {"scene_summary": "A desk", "objects": [], "visible_text": [], "confidence": .5}
        vision = VisualPerception()
        with patch("services.vision.ollama_analyse", slow_infer):
            vision.start()
            vision.submit(base64.b64encode(frame((80, 30, 20))).decode())
            started = time.monotonic()
            await asyncio.sleep(.03)
            self.assertLess(time.monotonic() - started, .15)
            await asyncio.sleep(.25)
            self.assertIsNotNone(vision.context())
            await vision.stop()

    async def test_preprocess_and_difference(self):
        data, pixels = preprocess(frame((30, 50, 80)))
        self.assertLessEqual(len(data), 250000)
        self.assertEqual(difference(pixels, pixels), 0)
        self.assertGreater(difference(pixels, preprocess(frame((150, 100, 20)))[1]), 0)
        with self.assertRaises(ValueError):
            preprocess(b"not an image")

    async def test_expired_context(self):
        vision = VisualPerception()
        vision.enabled = True
        vision.latest = {"scene_summary": "old", "received_at": time.monotonic() - 1000}
        self.assertIsNone(vision.context())

    async def test_timeout_does_not_trigger_tight_retries(self):
        vision = VisualPerception()
        encoded = base64.b64encode(frame((80, 30, 20))).decode()
        with patch("services.vision.ollama_analyse", side_effect=TimeoutError) as infer:
            vision.start()
            vision.submit(encoded)
            for _ in range(20):
                if vision.status == "unavailable":
                    break
                await asyncio.sleep(.05)
            self.assertEqual(vision.status, "unavailable")
            self.assertGreater(vision.retry_after, time.monotonic())
            vision.submit(encoded)
            await asyncio.sleep(.1)
            self.assertEqual(infer.call_count, 1)
            await vision.stop()
