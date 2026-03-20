#!/bin/bash
# MiroFish - ワンクリック起動スクリプト
# Usage: ./start.sh       (バックエンド＋フロントエンド)
#        ./start.sh back   (バックエンドのみ)
#        ./start.sh front  (フロントエンドのみ)
#        ./start.sh stop   (全プロセス停止)

DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID_FILE="$DIR/.backend.pid"
FRONTEND_PID_FILE="$DIR/.frontend.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

start_backend() {
    echo -e "${GREEN}[Backend]${NC} Starting on port 5001..."

    mkdir -p "$DIR/backend/logs"

    if [ ! -d "$DIR/node_modules" ]; then
        echo -e "${YELLOW}[Root]${NC} Installing root dependencies..."
        npm install
    fi

    if [ ! -x "$DIR/backend/.venv/bin/python" ]; then
        echo -e "${YELLOW}[Backend]${NC} Setting up virtualenv..."
        cd "$DIR/backend"
        python3 -m venv .venv
        .venv/bin/pip install -r requirements.txt
        cd "$DIR"
    fi

    # Kill existing
    if [ -f "$BACKEND_PID_FILE" ]; then
        kill $(cat "$BACKEND_PID_FILE") 2>/dev/null
        rm -f "$BACKEND_PID_FILE"
    fi
    lsof -ti:5001 | xargs kill -9 2>/dev/null

    cd "$DIR/backend"
    .venv/bin/python run.py > "$DIR/backend/logs/startup.log" 2>&1 &
    BPID=$!
    echo $BPID > "$BACKEND_PID_FILE"

    # Wait for health check
    for i in $(seq 1 10); do
        sleep 1
        if curl -s http://localhost:5001/health > /dev/null 2>&1; then
            echo -e "${GREEN}[Backend]${NC} Ready at ${CYAN}http://localhost:5001${NC}"
            return 0
        fi
    done
    echo -e "${RED}[Backend]${NC} Failed to start. Check logs/startup.log"
    return 1
}

start_frontend() {
    echo -e "${CYAN}[Frontend]${NC} Starting..."

    if ! command -v npm >/dev/null 2>&1; then
        echo -e "${RED}[Frontend]${NC} npm is not installed."
        return 1
    fi

    if [ ! -d "$DIR/frontend/node_modules" ]; then
        echo -e "${YELLOW}[Frontend]${NC} Installing dependencies..."
        cd "$DIR/frontend"
        npm install
        cd "$DIR"
    fi

    # Kill existing
    if [ -f "$FRONTEND_PID_FILE" ]; then
        kill $(cat "$FRONTEND_PID_FILE") 2>/dev/null
        rm -f "$FRONTEND_PID_FILE"
    fi

    cd "$DIR/frontend"
    npm run dev > /dev/null 2>&1 &
    FPID=$!
    echo $FPID > "$FRONTEND_PID_FILE"
    sleep 3

    # Detect port from vite output
    FPORT=$(lsof -p $FPID -iTCP -sTCP:LISTEN 2>/dev/null | grep -oE ':[0-9]+' | head -1 | tr -d ':')
    if [ -z "$FPORT" ]; then
        FPORT="5173"
    fi
    echo -e "${CYAN}[Frontend]${NC} Ready at ${CYAN}http://localhost:${FPORT}${NC}"
}

stop_all() {
    echo -e "${YELLOW}Stopping MiroFish...${NC}"
    if [ -f "$BACKEND_PID_FILE" ]; then
        kill $(cat "$BACKEND_PID_FILE") 2>/dev/null
        rm -f "$BACKEND_PID_FILE"
        echo -e "${GREEN}[Backend]${NC} Stopped"
    fi
    if [ -f "$FRONTEND_PID_FILE" ]; then
        kill $(cat "$FRONTEND_PID_FILE") 2>/dev/null
        rm -f "$FRONTEND_PID_FILE"
        echo -e "${CYAN}[Frontend]${NC} Stopped"
    fi
    lsof -ti:5001 | xargs kill -9 2>/dev/null
}

case "${1:-all}" in
    back|backend)
        start_backend
        ;;
    front|frontend)
        start_frontend
        ;;
    stop)
        stop_all
        ;;
    all|"")
        echo -e "${YELLOW}=== MiroFish Engine ===${NC}"
        echo ""
        start_backend && start_frontend
        echo ""
        echo -e "${GREEN}All systems go!${NC} Press Ctrl+C to stop."
        trap stop_all EXIT
        wait
        ;;
    *)
        echo "Usage: $0 [back|front|stop]"
        ;;
esac
