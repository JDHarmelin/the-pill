#!/bin/bash
# The Pill - Mac Launcher
# Double-click this file in Finder to launch The Pill.

PORT=8080

# Move to the project directory (same folder as this script)
cd "$(dirname "$0")"

clear
echo ""
echo "  =============================================="
echo "    THE PILL  —  Shkreli Method Stock Analysis"
echo "  =============================================="
echo ""

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "  ERROR: Virtual environment not found."
    echo ""
    echo "  Run these commands first:"
    echo "    python3 -m venv venv"
    echo "    source venv/bin/activate"
    echo "    pip install -r requirements.txt"
    echo ""
    read -p "  Press Enter to exit..."
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "  Created .env from template."
        echo "  Please add your API keys to .env, then launch again."
        echo ""
        open -e .env 2>/dev/null || open .env
        read -p "  Press Enter to exit..."
        exit 1
    else
        echo "  ERROR: .env file not found."
        echo "  Create a .env file with your ANTHROPIC_API_KEY and FINNHUB_API_KEY."
        echo ""
        read -p "  Press Enter to exit..."
        exit 1
    fi
fi

# Kill any existing process on the port
EXISTING=$(lsof -ti :$PORT 2>/dev/null)
if [ -n "$EXISTING" ]; then
    echo "  Clearing port $PORT..."
    echo "$EXISTING" | xargs kill -9 2>/dev/null
    sleep 1
fi

# Activate virtual environment
source venv/bin/activate

# Clean up server on exit (Ctrl+C or window close)
cleanup() {
    echo ""
    echo "  Shutting down..."
    kill "$SERVER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
    # Kill anything still on the port
    lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null
    echo "  Goodbye."
}
trap cleanup EXIT SIGTERM SIGHUP SIGINT

# Start Flask server in background
echo "  Starting server..."
python app.py &
SERVER_PID=$!

# Wait for the port to be open (up to 10 seconds)
echo "  Waiting for server to be ready..."
READY=0
for i in $(seq 1 10); do
    if lsof -i :$PORT -s TCP:LISTEN > /dev/null 2>&1; then
        READY=1
        break
    fi
    # Check if the process crashed
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done

if [ "$READY" -eq 0 ]; then
    echo "  ERROR: Server failed to start."
    echo "  Check your .env keys and that requirements are installed."
    echo ""
    read -p "  Press Enter to exit..."
    exit 1
fi

# Open the browser
open http://127.0.0.1:$PORT

echo "  Running at: http://127.0.0.1:$PORT"
echo ""
echo "  ─────────────────────────────────────────────"
echo "  Close this window to stop the server."
echo "  ─────────────────────────────────────────────"
echo ""

# Keep alive until server exits
wait "$SERVER_PID"
