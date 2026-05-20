@echo off
if exist "%~dp0token_cache.db" del "%~dp0token_cache.db"
uv run "%~dp0token_dashboard.py"
pause
