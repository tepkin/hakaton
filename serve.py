"""Точка входа веб-сервера GreenPlan AI (портативный и системный Python, любая ОС).

Хост/порт из окружения: в Docker GREENPLAN_HOST=0.0.0.0, локально 127.0.0.1.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.cli import main  # noqa: E402

if __name__ == "__main__":
    host = os.environ.get("GREENPLAN_HOST", "127.0.0.1")
    port = int(os.environ.get("GREENPLAN_PORT", "8000"))
    sys.exit(main(["serve", "--host", host, "--port", str(port)]))