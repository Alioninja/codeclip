#!/bin/bash
echo "Building React application..."
cd react-app
npm run build
cd ..
echo ""
echo "Build complete! The React app is now ready to be served by Flask."
echo "Run 'python app.py' or './run.sh' to start the server."
