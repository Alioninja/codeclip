@echo off
echo Building React application...
cd react-app
call npm run build
cd ..
echo.
echo Build complete! The React app is now ready to be served by Flask.
echo Run 'python app.py' or 'run.bat' to start the server.
pause
