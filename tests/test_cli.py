import json

from typer.testing import CliRunner

from mock_api_py.cli import app, find_available_port

runner = CliRunner()


def test_auto_create_missing_db_file(tmp_path):
    target = tmp_path / "auto_db.json"
    assert not target.exists()

    # Run the generate command or verify file creation
    result = runner.invoke(app, ["generate", "--output", str(target), "--schema", "users:2,posts:3"])
    assert result.exit_code == 0
    assert target.exists()

    with open(target, encoding="utf-8") as f:
        data = json.load(f)
    assert "users" in data
    assert len(data["users"]) == 2
    assert "posts" in data
    assert len(data["posts"]) == 3


def test_find_available_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        busy_port = s.getsockname()[1]
        next_port = find_available_port("127.0.0.1", busy_port)
        assert next_port != busy_port
        assert next_port > busy_port


def test_cli_import_command(tmp_path):
    spec_file = tmp_path / "openapi.json"
    spec_data = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "components": {
            "schemas": {
                "Category": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                }
            }
        },
    }
    spec_file.write_text(json.dumps(spec_data), encoding="utf-8")

    out_file = tmp_path / "imported.json"
    result = runner.invoke(app, ["import", str(spec_file), "--output", str(out_file), "--count", "4"])
    assert result.exit_code == 0
    assert out_file.exists()

    with open(out_file, encoding="utf-8") as f:
        data = json.load(f)
    assert "categories" in data
    assert len(data["categories"]) == 4


def test_cli_run_help_options():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--fixtures" in result.output
    assert "--scenario" in result.output
    assert "--stream-interval" in result.output

