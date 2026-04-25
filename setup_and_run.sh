#!/bin/bash
# ===========================================
# PED Smart Classroom — Setup & Run
# Executa tudo automaticamente no seu Mac
# ===========================================

set -e

echo ""
echo "========================================="
echo "  PED Smart Classroom — Setup Automático"
echo "========================================="
echo ""

cd "$(dirname "$0")"

# 1. Criar ambiente virtual (limpo)
echo "[1/6] Criando ambiente virtual Python..."
rm -rf .venv
python3 -m venv .venv

# 2. Ativar ambiente virtual
echo "[2/6] Ativando ambiente virtual..."
source .venv/bin/activate

# 3. Instalar dependências
echo "[3/6] Instalando dependências (pode levar ~30s)..."
pip install -r requirements.txt --quiet

# 4. Criar .env se não existir
if [ ! -f .env ]; then
    echo "[4/6] Criando arquivo .env..."
    cp .env.example .env
else
    echo "[4/6] Arquivo .env já existe, mantendo."
fi

# 5. Criar pastas de dados
echo "[5/6] Criando pastas de dados..."
mkdir -p .analytics .telemetry .cache memory

# 6. Iniciar servidor
echo "[6/6] Iniciando servidor..."
echo ""
echo "========================================="
echo "  Servidor rodando! Acesse:"
echo ""
echo "  Frontend:  http://localhost:8000/ui/"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Health:    http://localhost:8000/health"
echo ""
echo "  Para parar: pressione Ctrl+C"
echo "========================================="
echo ""

uvicorn app.main:app --reload
