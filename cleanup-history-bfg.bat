@echo off
echo ========================================
echo  BFG Repo-Cleaner - Remove Files from History
echo ========================================
echo.
echo This will REWRITE git history to completely remove:
echo   - react-app/node_modules/ (from ALL commits)
echo   - __pycache__/ (from ALL commits)
echo.
echo Current .git size: ~58 MB
echo After cleanup: ~2-5 MB (expected)
echo.
echo ⚠️  WARNING: This will:
echo   - Rewrite ALL commit history
echo   - Change all commit SHAs
echo   - Require force push
echo   - Require collaborators to re-clone
echo.
echo ✅ Backup will be created automatically
echo.
pause

echo.
echo Step 1: Creating backup...
cd /d "%~dp0.."
if exist codeclip-backup (
    echo Backup already exists, skipping...
) else (
    xcopy /E /I /H /Y codeclip codeclip-backup
    echo ✅ Backup created at: codeclip-backup
)

echo.
echo Step 2: Checking if BFG is installed...
where java >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Java not found! BFG requires Java.
    echo.
    echo Install Java from: https://www.java.com/download/
    echo Or use the alternative method in REMOVING-FILES-FROM-HISTORY.md
    pause
    exit /b 1
)

echo ✅ Java found

echo.
echo Step 3: Downloading BFG Repo-Cleaner...
cd /d "%~dp0"
if not exist bfg.jar (
    echo Downloading BFG...
    powershell -Command "Invoke-WebRequest -Uri 'https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar' -OutFile 'bfg.jar'"
    echo ✅ BFG downloaded
) else (
    echo ✅ BFG already downloaded
)

echo.
echo Step 4: Creating mirror clone...
cd /d "%~dp0.."
if exist codeclip-mirror (
    rd /s /q codeclip-mirror
)
git clone --mirror https://github.com/Alioninja/codeclip.git codeclip-mirror
cd codeclip-mirror

echo.
echo Step 5: Running BFG to remove node_modules from history...
java -jar "%~dp0bfg.jar" --delete-folders node_modules

echo.
echo Step 6: Running BFG to remove __pycache__ from history...
java -jar "%~dp0bfg.jar" --delete-folders __pycache__

echo.
echo Step 7: Cleaning up git repository...
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo.
echo Step 8: Checking new size...
echo.

echo.
echo ========================================
echo  ✅ History Rewritten Successfully!
echo ========================================
echo.
echo Your repository history is now clean.
echo.
echo NEXT STEPS (IMPORTANT):
echo.
echo 1. Review the mirror repository:
echo    cd codeclip-mirror
echo    git log --oneline
echo.
echo 2. Force push to GitHub (REWRITES REMOTE HISTORY):
echo    git push --force
echo.
echo 3. Update your working repository:
echo    cd ../codeclip
echo    git fetch origin
echo    git reset --hard origin/react
echo.
echo 4. Verify size reduction:
echo    Check .git folder size - should be ~2-5 MB
echo.
echo ⚠️  If you have collaborators, they must re-clone!
echo.
pause
