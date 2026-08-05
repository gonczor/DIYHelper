from runpy import run_path
from unittest.mock import patch


def test_main_script_starts_debug_server() -> None:
    with patch("uvicorn.run") as run:
        run_path("app/main.py", run_name="__main__")

    run.assert_called_once_with("app.main:app", host="0.0.0.0", port=8000, reload=True)
