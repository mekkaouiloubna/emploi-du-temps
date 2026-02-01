@echo off
echo ===============================
echo   START FLASK PROJECT
echo ===============================

REM 1) Create virtual environment if not exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM 2) Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM 3) Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM 4) Install dependencies
if exist requirements.txt (
    echo Installing dependencies from requirements.txt...
    pip install -r requirements.txt
) else (
    echo Installing Flask dependencies...
    pip install flask flask-sqlalchemy flask-migrate
)

REM 5) Set Flask environment variables
set FLASK_APP=app.py
set FLASK_ENV=development

REM 6) Initialize migrations if not exists
if not exist migrations (
    echo Initializing database migrations...
    flask db init
)

REM 7) Migrate database
echo Creating migration...
flask db migrate -m "Auto migration"

REM 8) Upgrade database
echo Applying migrations...
flask db upgrade

REM 9) Run Flask server
echo Starting Flask server...
flask run

pause
