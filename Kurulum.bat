@echo off
cd /d "%~dp0"
set PY=python
if exist "C:\python_314\python.exe" set PY=C:\python_314\python.exe
echo Gerekli kutuphaneler kuruluyor...
"%PY%" -m pip install -r requirements.txt
echo.
echo Kurulum bitti. Artik Baslat.bat ile uygulamayi acabilirsin.
pause
