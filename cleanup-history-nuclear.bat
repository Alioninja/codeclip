@echo off
echo ========================================
echo  Nuclear Option - Fresh Git History
echo ========================================
echo.
echo This will:
echo   ✅ Keep all your current code
echo   ✅ Remove ALL git history
echo   ✅ Start with clean slate
echo   ✅ Repository will be ~2-5 MB
echo.
echo   ❌ Lose all commit history
echo   ❌ Lose all branches except current
echo   ❌ Lose all tags
echo.
echo Current .git size: ~58 MB
echo After: ~2 MB
echo.
echo ⚠️  This is IRREVERSIBLE!
echo.
set /p confirm="Type 'YES' to proceed: "

if /i "%confirm%" NEQ "YES" (
    echo.
    echo Cancelled.
    pause
    exit /b
)

echo.
echo Step 1: Creating backup...
cd /d "%~dp0.."
if exist codeclip-backup-nuclear (
    rd /s /q codeclip-backup-nuclear
)
xcopy /E /I /H /Y codeclip codeclip-backup-nuclear
echo ✅ Backup created at: codeclip-backup-nuclear

cd codeclip

echo.
echo Step 2: Removing .git directory...
rd /s /q .git
echo ✅ Git history removed

echo.
echo Step 3: Initializing fresh repository...
git init
echo ✅ New git repository initialized

echo.
echo Step 4: Adding all files...
git add .
echo ✅ Files staged

echo.
echo Step 5: Creating initial commit...
git commit -m "Initial commit - Clean repository

- Removed node_modules and __pycache__ from history
- All functionality preserved
- ~97%% size reduction
- Previous history archived in backup folder"
echo ✅ Initial commit created

echo.
echo Step 6: Setting up remote...
git remote add origin https://github.com/Alioninja/codeclip.git
git branch -M react
echo ✅ Remote configured

echo.
echo ========================================
echo  ✅ Repository Reset Complete!
echo ========================================
echo.
echo Repository is now clean with fresh history.
echo.
echo FINAL STEP - Force Push to GitHub:
echo.
echo   git push --force origin react
echo.
echo ⚠️  This will OVERWRITE the remote repository!
echo ⚠️  Collaborators must re-clone!
echo.
echo Backup location: D:\Github\codeclip-backup-nuclear
echo.
pause
