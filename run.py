#!/usr/bin/env python3
"""Ponto de entrada para rodar a aplicação Flask."""
from app.app import app

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
