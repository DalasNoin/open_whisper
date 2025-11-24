#!/bin/bash
set -e

echo "Building Open Whisper Desktop App..."

# Install PyInstaller if needed
uv add --dev pyinstaller

# Clean previous builds
rm -rf build dist

# Build the app with PyInstaller
uv run pyinstaller \
    --name "Open Whisper Desktop" \
    --windowed \
    --icon icons/icon.icns \
    --add-data "backend:backend" \
    --add-data "config.json:." \
    --hidden-import "backend.app" \
    --hidden-import "backend.service" \
    --hidden-import "backend.config" \
    main_desktop.py

echo ""
echo "✅ Build complete!"
echo ""
echo "App location: dist/Open Whisper Desktop.app"
echo ""
echo "To run:"
echo "  open 'dist/Open Whisper Desktop.app'"
echo ""
echo "To install:"
echo "  cp -r 'dist/Open Whisper Desktop.app' /Applications/"
