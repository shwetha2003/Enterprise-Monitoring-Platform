#!/bin/bash

# Script to generate package-lock.json for Docker builds

echo "Cleaning up..."
rm -rf node_modules
rm -f package-lock.json

echo "Installing dependencies..."
npm install --package-lock-only

echo "Verifying package-lock.json..."
if [ -f "package-lock.json" ]; then
    echo "✅ package-lock.json generated successfully"
    echo "File size: $(wc -l < package-lock.json) lines"
else
    echo "❌ Failed to generate package-lock.json"
    exit 1
fi
