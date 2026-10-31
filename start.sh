#!/bin/bash
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting Excel Analytics Pro...${NC}"

# Start backend
cd backend
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
echo -e "${GREEN}✓ Starting backend on http://localhost:5000${NC}"
python app.py &
BACKEND_PID=$!
cd ..

sleep 2

# Start frontend
cd frontend
echo -e "${GREEN}✓ Starting frontend on http://localhost:3000${NC}"
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  App running at: http://localhost:3000          ${NC}"
echo -e "${GREEN}  API running at: http://localhost:5000          ${NC}"
echo -e "${GREEN}  Press Ctrl+C to stop both servers              ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════${NC}"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Servers stopped.'" INT
wait
