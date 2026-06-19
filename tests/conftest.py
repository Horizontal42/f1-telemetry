import os
import pytest
from telemetry.parser import load_lap

_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def sample_path():
    return os.path.join(_FIXTURES, "sample_lap.csv")


@pytest.fixture(scope="session")
def truncated_path():
    return os.path.join(_FIXTURES, "truncated.csv")


@pytest.fixture(scope="session")
def sample_lap(sample_path):
    return load_lap(sample_path)


@pytest.fixture(scope="session")
def acc_path():
    return os.path.join(_FIXTURES, "acc_lap.csv")


@pytest.fixture(scope="session")
def acc_lap(acc_path):
    return load_lap(acc_path)
