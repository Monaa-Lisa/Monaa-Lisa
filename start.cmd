@echo off
setlocal enabledelayedexpansion

:: ----------------------------------------------------------------------------
:: Monaa-Lisa Interactive Setup Script (Windows)
:: ----------------------------------------------------------------------------

:header
cls
echo.
echo --------------------------------------------------------------------
echo.
echo     Monaa-Lisa - arXiv Paper Visualization System
echo.
echo --------------------------------------------------------------------
echo.

:check_docker
echo --------------------------------------------------------------------
echo Checking Docker...
echo --------------------------------------------------------------------
docker version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not running!
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)
echo [OK] Docker is available

docker info >nul 2>&1
if errorlevel 1 goto docker_not_running
goto docker_ok

:docker_not_running
echo [WARN] Docker daemon is not running. Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo Waiting for Docker to start (30 seconds)...
timeout /t 30 /nobreak >nul
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Could not start Docker. Please start it manually.
    pause
    exit /b 1
)

:docker_ok
echo [OK] Docker is running
echo.

:check_env
echo --------------------------------------------------------------------
echo Checking Environment Configuration...
echo --------------------------------------------------------------------
if exist ".env" goto env_exists

echo [WARN] No .env file found.
if exist ".env.example" goto copy_env_example

echo Creating default .env file...
(
    echo # Database Configuration
    echo POSTGRES_USER=monaa
    echo POSTGRES_PASSWORD=sicherespasswort
    echo POSTGRES_DB=monaa_lisa_db
    echo.
    echo # Semantic Scholar API Key
    echo SEMANTIC_SCHOLAR_API_KEY=
    echo.
    echo # Data directory
    echo DATA_DIR=/app/data
) > .env
echo [OK] Created default .env file
goto env_review

:copy_env_example
copy ".env.example" ".env" >nul
echo [OK] Created .env from .env.example
goto env_review

:env_review
echo.
echo Please review and edit .env if needed.
pause
goto env_done

:env_exists
echo [OK] .env file exists

:env_done
echo.

:check_mirrors
echo --------------------------------------------------------------------
echo Checking Mirror Configuration...
echo --------------------------------------------------------------------
if not exist "mirrors.json" (
    echo [ERROR] mirrors.json not found!
    echo This file is required for downloading the dataset.
    pause
    exit /b 1
)
echo [OK] mirrors.json found
echo.

:menu
echo --------------------------------------------------------------------
echo Select Action
echo --------------------------------------------------------------------
echo.
echo   1) Fresh Start (clean volumes + rebuild)
echo   2) Start Services (keep existing data)
echo   3) Stop Services
echo   4) View Logs
echo   5) Reset Database Only
echo   6) Exit
echo.
set /p choice="Enter choice [1-6]: "

if "%choice%"=="1" goto fresh_start
if "%choice%"=="2" goto start_services
if "%choice%"=="3" goto stop_services
if "%choice%"=="4" goto view_logs
if "%choice%"=="5" goto reset_database
if "%choice%"=="6" goto end
echo Invalid choice
goto menu

:fresh_start
echo.
echo --------------------------------------------------------------------
echo Fresh Start - Cleaning Everything...
echo --------------------------------------------------------------------
echo [WARN] This will delete all existing data!
set /p confirm="Are you sure? (y/N): "
if /i not "%confirm%"=="y" (
    echo Cancelled.
    goto menu
)
echo.
echo Stopping containers...
docker-compose down -v 2>nul

echo Removing old images...
docker rmi monaa-lisa-app:latest monaa-lisa-frontend:latest 2>nul

echo.
echo Building and starting fresh...
docker-compose up --build -d

echo.
echo Waiting for all services to become healthy...
echo (Backend needs time for npm install and migrations on first run)

:wait_fresh
timeout /t 5 /nobreak >nul
docker-compose ps --format "{{.Service}} {{.Health}}" 2>nul | findstr /i "unhealthy starting" >nul
if not errorlevel 1 goto wait_fresh

echo.
echo [OK] Services started!
echo.
echo --------------------------------------------------------------------
echo Access Points:
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:3000
echo   Database:  localhost:5432
echo --------------------------------------------------------------------
echo.
echo First run will download ~10GB of data. Check progress with:
echo   docker logs -f monaa-lisa-app-1
echo.
set /p view="Press Enter to view logs or 'q' to exit: "
if /i not "%view%"=="q" (
    docker-compose logs -f
)
goto menu

:start_services
echo.
echo --------------------------------------------------------------------
echo Starting Services...
echo --------------------------------------------------------------------
docker-compose up -d
echo.
echo Waiting for all services to become healthy...
echo (Backend needs time for npm install and migrations on first run)

:wait_loop
timeout /t 5 /nobreak >nul
docker-compose ps --format "{{.Service}} {{.Health}}" 2>nul | findstr /i "unhealthy starting" >nul
if not errorlevel 1 goto wait_loop

echo.
echo [OK] Services started!
echo.
echo --------------------------------------------------------------------
echo Access Points:
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:3000
echo   Database:  localhost:5432
echo --------------------------------------------------------------------
pause
goto menu

:stop_services
echo.
echo --------------------------------------------------------------------
echo Stopping Services...
echo --------------------------------------------------------------------
docker-compose down
echo [OK] All services stopped
pause
goto menu

:view_logs
echo.
echo --------------------------------------------------------------------
echo View Logs (Ctrl+C to exit)
echo --------------------------------------------------------------------
echo.
echo Select service:
echo   1) All services
echo   2) App (Python pipeline)
echo   3) Backend (NestJS)
echo   4) Database (PostgreSQL)
echo   5) Frontend (Svelte)
echo.
set /p log_choice="Enter choice [1-5]: "

if "%log_choice%"=="1" docker-compose logs -f
if "%log_choice%"=="2" docker-compose logs -f app
if "%log_choice%"=="3" docker-compose logs -f backend
if "%log_choice%"=="4" docker-compose logs -f db
if "%log_choice%"=="5" docker-compose logs -f frontend
if not "%log_choice%"=="1" if not "%log_choice%"=="2" if not "%log_choice%"=="3" if not "%log_choice%"=="4" if not "%log_choice%"=="5" docker-compose logs -f
goto menu

:reset_database
echo.
echo --------------------------------------------------------------------
echo Resetting Database...
echo --------------------------------------------------------------------
echo [WARN] This will delete all database data!
set /p confirm="Are you sure? (y/N): "
if /i not "%confirm%"=="y" (
    echo Cancelled.
    goto menu
)
echo Stopping services...
docker-compose down

echo Removing database volume...
docker volume rm monaa-lisa_pgdata 2>nul

echo Starting services...
docker-compose up -d

echo [OK] Database reset complete
pause
goto menu

:end
echo Goodbye!
exit /b 0
