#!/bin/bash
# ============================================================
# update-github.sh
# Run this every time you want to save and push changes.
# Usage:
#   chmod +x update-github.sh
#   ./update-github.sh "your commit message"
# ============================================================

MSG="${1:-Update coaching board}"

echo ""
echo "=== Pushing update to GitHub ==="
echo "Message: $MSG"
echo ""

git add index.html cap_server.py notion_coachees.csv notion_sessions.csv notion_setup_guide.md README.md .gitignore
git commit -m "$MSG"
git push origin main

echo ""
echo "✅ Done!"
