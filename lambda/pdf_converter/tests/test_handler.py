"""Tests for PDF converter Lambda handler."""

import importlib
from pathlib import Path

from PIL import Image

# The 'lambda' directory name is a Python keyword; use importlib to load the module.
_handler_path = Path(__file__).resolve().parents[1] / "handler.py"
_spec = importlib.util.spec_from_file_location("pdf_converter_handler", _handler_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
crop_bottom_whitespace = _mod.crop_bottom_whitespace


class TestCropBottomWhitespace:
    def test_crops_black_rows(self):
        # Create a 100x100 image: top half white, bottom half black
        img = Image.new("RGB", (100, 100), (0, 0, 0))
        for y in range(50):
            for x in range(100):
                img.putpixel((x, y), (255, 255, 255))

        cropped = crop_bottom_whitespace(img)
        # Should crop near row 50 (plus small padding)
        assert cropped.size[1] < 100
        assert cropped.size[1] >= 50

    def test_no_crop_needed(self):
        # All-white image: no black rows to crop
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        cropped = crop_bottom_whitespace(img)
        assert cropped.size[1] == 100


# Integration test with sample_dashboard.pdf fixture would go here
# Place a sample PDF at lambda/pdf_converter/tests/fixtures/sample_dashboard.pdf
