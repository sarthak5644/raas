#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Excel Analytics Pro - Setup Script       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.9+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $(python3 --version)${NC}"

# Check Node
if ! command -v node &>/dev/null; then
    echo -e "${RED}✗ Node.js not found. Please install Node.js 18+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js $(node --version)${NC}"

echo ""
echo -e "${BLUE}[1/4] Setting up Backend...${NC}"
cd backend

# Virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Create .env if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env 2>/dev/null || echo -e "${YELLOW}⚠ Please configure backend/.env${NC}"
fi

cd ..

echo ""
echo -e "${BLUE}[2/4] Setting up Frontend...${NC}"
cd frontend
npm install --legacy-peer-deps -q
echo -e "${GREEN}✓ Node.js dependencies installed${NC}"
cd ..

echo ""
echo -e "${BLUE}[3/4] Creating directories...${NC}"
mkdir -p uploads reports backend/database
echo -e "${GREEN}✓ Directories created${NC}"

echo ""
echo -e "${BLUE}[4/4] Setup complete!${NC}"
echo ""
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup Complete! Run with: ./start.sh      ${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Optional: Add your API keys to backend/.env${NC}"
echo -e "  GEMINI_API_KEY  → https://aistudio.google.com/app/apikey"
echo -e "  STRIPE keys     → https://dashboard.stripe.com/test/apikeys"
echo ""
