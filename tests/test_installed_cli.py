import os
import subprocess
import sys
from pathlib import Path

def test_cli_runs_from_isolated_working_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    fixture = root / "data/api_examples/houses.json"
    env = {**os.environ, "OIR_FUSEKI_GSP_URL": "http://local.test/data", "OIR_FUSEKI_SPARQL_URL": "http://local.test/query"}
    result = subprocess.run([sys.executable, "-m", "oireachtas_etl.cli", "run", "houses", "--fixture", str(fixture), "--offline", "--raw-dir", str(tmp_path / "raw")], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert '"excluded": []' in result.stdout
    assert '"published": false' in result.stdout


def test_reference_cli_runs_from_isolated_working_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "OIR_FUSEKI_GSP_URL": "http://local.test/data", "OIR_FUSEKI_SPARQL_URL": "http://local.test/query"}
    for endpoint, fixture in [("parties", "parties.json"), ("constituencies", "constituencies.json")]:
        result = subprocess.run([sys.executable, "-m", "oireachtas_etl.cli", "run", endpoint, "--fixture", str(root / "data/api_examples" / fixture), "--offline", "--raw-dir", str(tmp_path / endpoint)], cwd=tmp_path, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert '"published": false' in result.stdout
