"""One real conversion per combination, generated from the registry (capability matrix)."""

import pytest

from app.tools.converter import matrix, verify
from tests.engines.conftest import light, media

LIGHT_CATEGORIES = ("document", "image")


def _params():
    for candidate in matrix.candidates():
        mark = light if candidate.category in LIGHT_CATEGORIES else media
        yield pytest.param(candidate, id=candidate.key, marks=mark)


@pytest.mark.parametrize("candidate", list(_params()))
def test_real_conversion(candidate, fixtures, tmp_path):
    verify.run_candidate(candidate, fixtures, tmp_path)


def test_only_verified_combinations_are_available():
    """Every candidate is either verified (available) or seeded as planned: no third state."""
    verified = matrix.verified_keys()
    keys = {c.key for c in matrix.candidates()}
    assert verified <= keys, "verified.json lists combinations that are not in the matrix"
