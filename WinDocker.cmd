@echo off
setlocal enabledelayedexpansion

echo ===========================================
echo Monaa-Lisa Application Docker Launcher
echo ===========================================

REM Check if Docker is installed
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed or not in your PATH
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not running
    echo Please start Docker Desktop and try again
    pause
    exit /b 1
)

:menu
cls
echo Choose an option:
echo 1. Start application (quick start)
echo 2. Reset everything and start fresh
echo 3. Check database status
echo 4. Shutdown Docker/Server
echo 5. Exit
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" goto start_app
if "%choice%"=="2" goto reset_app
if "%choice%"=="3" goto check_db
if "%choice%"=="4" goto shutdown_app
if "%choice%"=="5" goto end
echo Invalid choice. Please try again.
pause
goto menu

:shutdown_app
echo.
echo Shutting down all containers...
docker-compose down

echo.
echo All Monaa-Lisa containers have been stopped.
echo.
echo Press any key to return to the menu
pause >nul
goto menu

:start_app
echo.
echo Starting Monaa-Lisa application...

echo 1. Making sure containers are down...
docker-compose down

echo 2. Starting database...
docker-compose up -d db
echo Waiting for database to initialize (10 seconds)...
timeout /t 10 /nobreak >nul

echo 3. Creating database tables...
docker-compose run --rm -e PYTHONPATH=/app/MonaaLisa/src app python MonaaLisa/src/Database/db.py

echo 4. Starting application, RESTful API and frontend...
docker-compose up -d app frontend rest

echo.
echo Docker has been contacted - wait a good minute and check the logs =)!
echo   - Frontend: http://localhost:5173
echo   - Database: http://localhost:5432
echo   - RESTful API: http://localhost:5000
echo.
echo Press any key to see application logs (Ctrl+C to exit logs)
pause >nul
docker-compose logs -f app rest
goto menu

:reset_app
echo.
echo Resetting everything and starting fresh...

echo 1. Stopping and removing all containers...
docker-compose down -v

echo 2. Cleaning Docker caches...
REM docker system prune -f

echo 3. Removing hash files...
if exist MonaaLisa\src\parsed_hashes.txt del MonaaLisa\src\parsed_hashes.txt
if exist parsed_hashes.txt del parsed_hashes.txt

echo 4. Rebuilding Docker images...
docker-compose build

echo 5. Starting PostgreSQL database...
docker-compose up -d db
echo Waiting for database to be ready (10 seconds)...
timeout /t 10 /nobreak >nul

echo 6. Creating database tables...
docker-compose run --rm -e PYTHONPATH=/app/MonaaLisa/src app python MonaaLisa/src/Database/db.py

echo 7. Starting the application, RESTful API and frontend...
docker-compose up -d app frontend rest

echo.
echo Docker has been contacted - wait a good minute and check the logs =)!
echo   - Frontend: http://localhost:5173
echo   - Database: http://localhost:5432
echo   - RESTful API: http://localhost:5000
echo.
echo Press any key to see application logs (Ctrl+C to exit logs)
pause >nul
docker-compose logs -f app rest
goto menu

:check_db
echo.
echo Checking database status...

REM Capture the container ID using Windows-compatible syntax
for /f "tokens=*" %%a in ('docker-compose ps -q db') do set DB_CONTAINER=%%a

if "%DB_CONTAINER%"=="" (
    echo [ERROR] No database container found. Please start the application first.
) else (
    echo Checking database tables:
    docker exec -it %DB_CONTAINER% psql -U monaa -d monaa_lisa -c "\dt"
    
    echo.
    echo Number of papers in database:
    docker exec -it %DB_CONTAINER% psql -U monaa -d monaa_lisa -c "SELECT count(*) FROM papers;"
)

echo.
echo Press any key to return to the menu
pause >nul
goto menu

:end
echo.
echo Good Night Monaa-Lisa =)
echo.
endlocal
