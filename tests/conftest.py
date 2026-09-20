"""codec und protocol lassen sich ohne Home Assistant testen."""

import pathlib
import sys

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "syrup")
)
