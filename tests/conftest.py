import pytest

from anchor import config
from anchor.core import Store


@pytest.fixture
def make_store(tmp_path):
    """Build a store with an explicit config, so a local anchor.toml never leaks in."""
    def make(cfg: dict | None = None, name: str = "test.db") -> Store:
        return Store(str(tmp_path / name), config.from_dict(cfg))
    return make


@pytest.fixture
def store(make_store):
    return make_store()
