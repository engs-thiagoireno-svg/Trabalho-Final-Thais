@echo off
REM Etapa 2 - Qualidade de dados: roda tudo e sobe na branch "qualidade".
REM Uso: extraia o zip na raiz do repositorio e de dois cliques neste arquivo.
cd /d "%~dp0"

echo.
echo [1/5] Branch qualidade...
git rev-parse --verify qualidade >nul 2>&1
if errorlevel 1 (git checkout -b qualidade) else (git checkout qualidade)
if errorlevel 1 goto erro

echo.
echo [2/5] Conferindo config\config.ini...
if not exist config\config.ini (
  echo Falta o config\config.ini. Copie o config\config.example.ini e coloque a senha do Neon.
  goto erro
)
findstr /c:"COLOQUE_SUA_SENHA_AQUI" config\config.ini >nul
if not errorlevel 1 (
  echo Abra o config\config.ini e troque COLOQUE_SUA_SENHA_AQUI pela senha do Neon.
  goto erro
)

echo.
echo [3/5] Instalando bibliotecas...
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
if errorlevel 1 goto erro

echo.
echo [4/5] Rodando a qualidade no banco do grupo...
python -m src.qualidade.executar
if errorlevel 1 goto erro

echo.
echo [5/5] Enviando para o GitHub...
git add .
git commit -m "qualidade: regras, metricas, limpeza e antes x depois"
git push -u origin qualidade
if errorlevel 1 goto erro

echo.
echo Pronto! Branch qualidade enviada.
pause
exit /b 0

:erro
echo.
echo Deu erro no passo acima. Copie a mensagem e mande para o Claude.
pause
exit /b 1
