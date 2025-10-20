#!/bin/bash
# Quick Start Script for Test Generation UI

echo "🚀 Starting Test Generation UI..."
echo ""

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment (.venv)..."
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
elif [ -d "venv" ]; then
    echo "🐍 Activating virtual environment (venv)..."
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  No virtual environment found"
    echo "   Using system Python: $(which python3)"
fi
echo ""

# Check if Ollama is running
echo "📡 Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama is running"
else
    echo "❌ Ollama is not running!"
    echo "   Please start Ollama first:"
    echo "   ollama serve"
    exit 1
fi

# Check if required model is available
echo ""
echo "🤖 Checking Granite model..."
if curl -s http://localhost:11434/api/tags | grep -q "granite3.2-vision"; then
    echo "✅ granite3.2-vision:latest is available"
else
    echo "⚠️  granite3.2-vision:latest not found"
    echo "   Pulling model (this may take a few minutes)..."
    ollama pull granite3.2-vision:latest
fi

# Check Python dependencies
echo ""
echo "📦 Checking Python dependencies..."
python -c "import flask, selenium, werkzeug" 2>/dev/null || {
    echo "❌ Required dependencies not installed"
    echo "   Installing dependencies in virtual environment..."
    pip install -q flask werkzeug selenium pillow imagehash requests
    echo "✅ Dependencies installed"
}
echo "✅ All dependencies available"

# Create required directories
echo ""
echo "📁 Creating directories..."
mkdir -p generated_tests
mkdir -p uploads
echo "✅ Directories created"

# Start the UI
echo ""
echo "🎨 Starting Flask server..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🌐 Test Generation UI"
echo "  📍 URL: http://localhost:5000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Features:"
echo "  ✍️  Natural Language Test Creation"
echo "  📸 Screenshot-Based Test Generation"
echo "  📚 Test Library Management"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python ./ui/test_generation_ui.py
