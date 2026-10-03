@echo off
cd /d "%~dp0"
py -m unittest discover -s tests -v 2>nul || python -m unittest discover -s tests -v
pause
