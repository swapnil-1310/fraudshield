"""Global test fixtures and environment configuration."""
import os
import sys
import pytest
from starlette.testclient import TestClient

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Force CPU mode for tests
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from app import app


@pytest.fixture
def client():
    """Provides a synchronous FastAPI TestClient."""
    return TestClient(app)
