#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/crawler.log"
PYTHON="$SCRIPT_DIR/venv/bin/python"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 크롤링 시작 =====" >> "$LOG_FILE"

cd "$SCRIPT_DIR" && "$PYTHON" main.py >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "===== 크롤링 성공 =====" >> "$LOG_FILE"
else
    echo "===== 크롤링 실패 (종료 코드: $?) =====" >> "$LOG_FILE"
fi
