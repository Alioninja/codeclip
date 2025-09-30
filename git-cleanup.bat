@echo off
echo ========================================
echo  Git Cleanup - Remove Tracked Files
echo  That Are Now in .gitignore
echo ========================================
echo.
echo This will remove from git tracking (but keep on disk):
echo   - node_modules/ (11,924 files!)
echo   - __pycache__/*.pyc files
echo.
echo ⚠️  WARNING: This may take a minute due to node_modules size.
echo.
echo These files are now in .gitignore and shouldn't be tracked.
echo.
pause

echo.
echo Step 1: Removing node_modules from git tracking...
echo (This may take a minute - 11,924 files to process)
git rm -r --cached react-app/node_modules/

echo.
echo Step 2: Removing __pycache__ files from git tracking...
git rm -r --cached __pycache__/

echo.
echo ✅ Done! Now commit these changes:
echo.
echo    git add .gitignore
echo    git commit -m "Add .gitignore and untrack node_modules + __pycache__"
echo.
echo This will significantly reduce your repository size!
echo.
pause
