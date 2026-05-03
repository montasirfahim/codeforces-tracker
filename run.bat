@echo off
echo Starting Codeforces Solve Checker...
if not exist venv (
    echo Virtual environment not found. Please ensure the project is set up correctly.
    pause
    exit /b
)
call .\venv\Scripts\activate
python manage.py runserver
pause
