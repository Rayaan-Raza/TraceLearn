import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app
client = TestClient(app)
print(client.post("/api/demo/reset").json())
