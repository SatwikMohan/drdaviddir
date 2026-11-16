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
import config


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

    async def test_identical_scene_is_refreshed_periodically(self):
        seen = []
        vision = VisualPerception(lambda item, change: seen.append(item["sequence_id"]))
        encoded = base64.b64encode(frame((80, 30, 20))).decode()
        result = {"scene_summary": "A room", "objects": [], "visible_text": [], "confidence": .8}
        with patch("services.vision.ollama_analyse", return_value=result) as infer, \
             patch.object(config, "VISION_COOLDOWN_SECONDS", 0), \
             patch.object(config, "VISION_PERIODIC_SECONDS", .05):
            vision.start()
            vision.submit(encoded)
            for _ in range(30):
                if vision.context():
                    break
                await asyncio.sleep(.05)
            self.assertIsNotNone(vision.context())
            await asyncio.sleep(.06)
            vision.submit(encoded)
            for _ in range(30):
                if infer.call_count == 2:
                    break
                await asyncio.sleep(.05)
            self.assertEqual(infer.call_count, 2)
            self.assertEqual(seen, [1, 2])
            await vision.stop()

    async def test_gradual_change_is_compared_with_last_analysed_scene(self):
        vision = VisualPerception()
        result = {"scene_summary": "A room", "objects": [], "visible_text": [], "confidence": .8}
        with patch("services.vision.ollama_analyse", return_value=result) as infer, \
             patch.object(config, "VISION_COOLDOWN_SECONDS", 0), \
             patch.object(config, "VISION_PERIODIC_SECONDS", 1000), \
             patch.object(config, "VISION_CHANGE_THRESHOLD", .075):
            vision.start()
            vision.submit(base64.b64encode(frame((50, 50, 50))).decode())
            self.assertIsNotNone(await vision.wait_for_sequence(1, 2))
            for level in (60, 68, 76):
                vision.submit(base64.b64encode(frame((level, level, level))).decode())
                await asyncio.sleep(.05)
            self.assertEqual(infer.call_count, 2)
            self.assertEqual(vision.context()["sequence_id"], 4)
            await vision.stop()

    async def test_wait_for_new_frame_does_not_return_previous_scene(self):
        vision = VisualPerception()
        observations = iter(("Previous scene", "New scene"))

        def infer(data, detailed=False):
            return {"scene_summary": next(observations), "objects": [],
                    "visible_text": [], "confidence": .8}

        with patch("services.vision.ollama_analyse", infer), \
             patch.object(config, "VISION_COOLDOWN_SECONDS", 0):
            vision.start()
            vision.submit(base64.b64encode(frame((50, 50, 50))).decode())
            self.assertEqual((await vision.wait_for_sequence(1, 2))["scene_summary"], "Previous scene")
            waiter = asyncio.create_task(vision.wait_for_sequence(2, 2))
            await asyncio.sleep(.02)
            self.assertFalse(waiter.done())
            vision.submit(base64.b64encode(frame((160, 160, 160))).decode())
            self.assertEqual((await waiter)["scene_summary"], "New scene")
            await vision.stop()
