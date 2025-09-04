"""
Основная точка входа для SGR Deep Research API сервера.
"""

import uvicorn
from api.endpoints import app
from settings import get_config


def main():
    """Запуск FastAPI сервера."""
    config = get_config()
    
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()



