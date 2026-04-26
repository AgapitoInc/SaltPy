from . import core
from . import utils

"""
SaltPy: Open-Source Sonar Survey Processing for Solution-Mined Caverns
"""

__version__ = "0.1.0"
__author__ = "Matthew W. Bauer, Brandon Lampe, Kaitlyn Manalili, Baris Ates"
__license__ = "MIT"

# Import main modules for easier access

__all__ = [
    "core",
    "utils",
]

from saltpy_public import SonarPy, SonarPyVista, SonarDXF
from saltpy_public import get_igrf_path
