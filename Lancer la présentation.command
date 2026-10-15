#!/bin/bash
# Présentation Vertane : lance un petit serveur local et ouvre la présentation dans le navigateur.
# Servie en local, la 3D marche même sans internet (three.js est dans assets/vendor).
cd "$(dirname "$0")" || exit 1
PORT=8777
URL="http://localhost:$PORT/presentation.html"
SRV=""
if ! lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  python3 assets/presentation/serveur.py $PORT &
  SRV=$!
  sleep 1
fi
if [ -d "/Applications/Google Chrome.app" ]; then open -a "Google Chrome" "$URL"; else open "$URL"; fi
echo ""
echo "  Présentation ouverte : $URL"
echo "  → F : plein écran · S : vue présentateur · ? : aide"
echo ""
echo "  Laisse cette fenêtre ouverte pendant la présentation."
echo "  Ferme-la (ou Ctrl+C) à la fin pour arrêter le serveur."
[ -n "$SRV" ] && wait $SRV
