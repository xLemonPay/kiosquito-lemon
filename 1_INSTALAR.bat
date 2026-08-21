@echo off
chcp 65001 >nul
title Instalar - El Kiosquito de Lemon
echo ============================================
echo      EL KIOSQUITO DE LEMON - INSTALAR
echo ============================================
echo.
python --version
echo.
echo Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo ============================================
echo Listo. Ahora configura el archivo .env
echo y despues abre 2_INICIAR.bat
echo ============================================
pause
