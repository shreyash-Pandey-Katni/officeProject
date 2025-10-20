#!/bin/bash
# Virtual Environment Setup Script for Test Generation Project

echo "🔧 Setting up Virtual Environment..."
echo ""

# Check if virtual environment already exists
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists at ./venv"
    read -p "Do you want to recreate it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing old virtual environment..."
        rm -rf venv
    else
        echo "✅ Using existing virtual environment"
        source venv/bin/activate
        echo "✅ Virtual environment activated!"
        echo ""
        echo "Python: $(which python)"
        echo "Version: $(python --version)"
        exit 0
    fi
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment"
    echo "   Make sure python3-venv is installed:"
    echo "   sudo apt-get install python3-venv"
    exit 1
fi

echo "✅ Virtual environment created"
echo ""

# Activate virtual environment
echo "🚀 Activating virtual environment..."
source venv/bin/activate

echo "✅ Virtual environment activated!"
echo ""
echo "Python location: $(which python)"
echo "Python version: $(python --version)"
echo ""

# Upgrade pip
echo "⬆️  Upgrading pip..."
python -m pip install --upgrade pip > /dev/null 2>&1

# Install core dependencies
echo "📦 Installing core dependencies..."
pip install selenium flask werkzeug requests pillow imagehash > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Core dependencies installed"
echo ""

# Create requirements.txt
echo "📝 Creating requirements.txt..."
pip freeze > requirements.txt
echo "✅ requirements.txt created"
echo ""

# Create activation reminder
cat > activate_venv.sh << 'EOF'
#!/bin/bash
# Quick activation script
source venv/bin/activate
echo "✅ Virtual environment activated!"
echo "Python: $(which python)"
echo ""
echo "To deactivate, run: deactivate"
EOF

chmod +x activate_venv.sh

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SETUP COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Virtual environment is now active!"
echo ""
echo "📦 Installed packages:"
pip list --format=columns
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "NEXT STEPS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Virtual environment is already activated in this terminal"
echo ""
echo "2. For NEW terminals, activate with:"
echo "   source venv/bin/activate"
echo "   OR"
echo "   ./activate_venv.sh"
echo ""
echo "3. Start the Test Generation UI:"
echo "   ./start_test_ui.sh"
echo ""
echo "4. Deactivate when done:"
echo "   deactivate"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
