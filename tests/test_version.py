import re

from sound_mixer import __version__


def test_version_format():
    assert re.match(r"^\d+\.\d+\.\d+$", __version__)
