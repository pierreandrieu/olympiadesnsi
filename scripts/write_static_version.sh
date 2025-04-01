#!/bin/bash

# Ce script écrit le hash court du dernier commit + date dans le fichier .staticversion
# Exemple : 3f2a9e1-202504012355

cd "$(dirname "$0")/.."  # se place à la racine du projet

VERSION_FILE="olympiadesnsi/.staticversion"

if git rev-parse --git-dir > /dev/null 2>&1; then
    HASH=$(git rev-parse --short HEAD)
    DATE=$(date +%Y%m%d%H%M)
    VERSION="${HASH}-${DATE}"
    echo "$VERSION" > "$VERSION_FILE"
    echo "✅ Static version écrite dans $VERSION_FILE : $VERSION"
else
    echo "⚠️  Pas de dépôt Git, version fixée à 'dev'"
    echo "dev" > "$VERSION_FILE"
fi
