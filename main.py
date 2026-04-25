from app.cli import run_cli
from app.main import app, create_app

__all__ = ['app', 'create_app']

if __name__ == '__main__':
    run_cli()
