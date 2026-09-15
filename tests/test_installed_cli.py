import subprocess
import sys
from pathlib import Path

def test_cli_runs_from_isolated_working_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    fixture = root / "data/api_examples/houses.json"
    result = subprocess.run([sys.executable, "-m", "oireachtas_etl.cli", "run", "houses", "--fixture", str(fixture), "--offline", "--raw-dir", str(tmp_path / "raw")], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert '"excluded": []' in result.stdout
