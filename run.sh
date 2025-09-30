#!/bin/bash

echo "🚀 Starting Codebase to Clipboard Web Application..."
echo

cd "$(dirname "$0")"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python run.py
elif [ -f ".venv/Scripts/python.exe" ]; then
    .venv/Scripts/python.exe run.py
else
    python run.py
fi