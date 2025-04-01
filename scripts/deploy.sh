#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo ""
echo "🔄 Pulling latest code..."
git pull

echo ""
echo "✍️  Writing static version..."
./scripts/write_static_version.sh

echo ""
echo "📦 Running collectstatic..."
python3 manage.py collectstatic --noinput

echo ""
echo "✅ Done!"
