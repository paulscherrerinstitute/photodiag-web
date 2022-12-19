import re

from setuptools import find_packages, setup

with open("photodiag_web/__init__.py") as f:
    version = re.search(r'__version__ = "(.*?)"', f.read()).group(1)

setup(
    name="photodiag_web",
    version=version,
    description="A webserver for photon diagnostics services.",
    packages=find_packages(),
    license="GNU GPLv3",
)
