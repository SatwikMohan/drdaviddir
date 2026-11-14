import sys
import io
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from scripts import setup_vision


class SetupVisionTests(unittest.TestCase):
    def test_rerun_reuses_model(self):
        with patch.object(setup_vision, "ensure_service", return_value=[{"name": setup_vision.config.VISION_MODEL}]) as service, \
             patch.object(setup_vision, "pull_model") as pull, \
             patch.object(setup_vision, "verify_image_inference") as verify:
            setup_vision.main([])
        service.assert_called_once_with(install=True, start=True)
        pull.assert_not_called()
        verify.assert_called_once()

    def test_missing_model_is_pulled_and_verified(self):
        with patch.object(setup_vision, "ensure_service", return_value=[]), \
             patch.object(setup_vision, "pull_model") as pull, \
             patch.object(setup_vision, "service_models", return_value=[{"name": setup_vision.config.VISION_MODEL}]), \
             patch.object(setup_vision, "verify_image_inference") as verify:
            setup_vision.main([])
        pull.assert_called_once()
        verify.assert_called_once()

    def test_check_is_read_only(self):
        with patch.object(setup_vision, "ensure_service", return_value=[{"name": setup_vision.config.VISION_MODEL}]) as service, \
             patch.object(setup_vision, "pull_model") as pull, \
             patch.object(setup_vision, "verify_image_inference") as verify:
            setup_vision.main(["--check"])
        service.assert_called_once_with(install=False, start=False)
        pull.assert_not_called()
        verify.assert_not_called()

    def test_missing_install_and_stopped_service_are_prepared(self):
        model = {"name": setup_vision.config.VISION_MODEL}
        with patch.object(setup_vision, "ollama_binary", side_effect=[None, Path("C:/Ollama/ollama.exe")]), \
             patch.object(setup_vision, "install_windows_ollama") as install, \
             patch.object(setup_vision, "service_models", side_effect=[None, [model]]), \
             patch.object(setup_vision.subprocess, "Popen") as start, \
             patch.object(setup_vision.time, "sleep"):
            models = setup_vision.ensure_service()
        self.assertEqual(models, [model])
        install.assert_called_once()
        start.assert_called_once()

    def test_processor_report_uses_ollama_vram_data(self):
        output = io.StringIO()
        model = {"name": setup_vision.config.VISION_MODEL, "size": 100, "size_vram": 0}
        with patch.object(setup_vision, "api", return_value={"models": [model]}), redirect_stdout(output):
            setup_vision.report_processor()
        self.assertIn("100% CPU", output.getvalue())
        model["size_vram"] = 100
        output = io.StringIO()
        with patch.object(setup_vision, "api", return_value={"models": [model]}), redirect_stdout(output):
            setup_vision.report_processor()
        self.assertIn("100% GPU", output.getvalue())
