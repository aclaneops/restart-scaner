@echo off
echo ========================================================
echo  Membangun Modern EPC Hardware Restarter ke Standalone EXE
echo  Target: Windows 7, Windows 8, Windows 10, Windows 11
echo ========================================================
echo.

REM Pastikan dependensi terpasang
pip install pyserial pyinstaller

echo.
echo Mengompilasi dengan PyInstaller...
pyinstaller --noconfirm --onedir --windowed --name "ScannerRestarter" app.py

if exist ..\drivers (
    echo Menyalin folder drivers...
    xcopy /E /I /Y ..\drivers dist\ScannerRestarter\drivers
)

echo.
echo ========================================================
echo  Selesai! File aplikasi berada di folder: dist\ScannerRestarter
echo ========================================================
pause
