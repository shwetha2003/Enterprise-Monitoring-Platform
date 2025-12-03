cd frontend
# Remove existing node_modules and lock file
rm -rf node_modules
rm -f package-lock.json

# Install with package-lock generation
npm install --package-lock-only

# Verify
if [ -f "package-lock.json" ]; then
    echo "✅ package-lock.json generated"
    echo "Lines: $(wc -l < package-lock.json)"
else
    echo "❌ Failed to generate package-lock.json"
    exit 1
fi
