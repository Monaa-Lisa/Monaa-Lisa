#!/bin/bash

# ----------------------------------------------------------------------------
# Monaa-Lisa Interactive Setup Script
# ----------------------------------------------------------------------------

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    clear
    echo ""
    echo "--------------------------------------------------------------------"
    echo ""
    echo "    ███╗   ███╗ ██████╗ ███╗   ██╗ █████╗  █████╗"
    echo "    ████╗ ████║██╔═══██╗████╗  ██║██╔══██╗██╔══██╗"
    echo "    ██╔████╔██║██║   ██║██╔██╗ ██║███████║███████║"
    echo "    ██║╚██╔╝██║██║   ██║██║╚██╗██║██╔══██║██╔══██║"
    echo "    ██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║  ██║██║  ██║"
    echo "    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝"
    echo ""
    echo "    ██╗     ██╗███████╗ █████╗"
    echo "    ██║     ██║██╔════╝██╔══██╗"
    echo "    ██║     ██║███████╗███████║"
    echo "    ██║     ██║╚════██║██╔══██║"
    echo "    ███████╗██║███████║██║  ██║"
    echo "    ╚══════╝╚═╝╚══════╝╚═╝  ╚═╝"
    echo ""
    echo "--------------------------------------------------------------------"
    echo ""
}

print_section() {
    echo ""
    echo "--------------------------------------------------------------------"
    echo "$1"
    echo "--------------------------------------------------------------------"
}

check_docker() {
    print_section "Checking Docker..."
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}[ERROR] Docker is not installed!${NC}"
        echo "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "${YELLOW}[WARN] Docker is not running. Attempting to start...${NC}"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            open -a Docker
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            sudo systemctl start docker
        fi
        echo "Waiting for Docker to start..."
        sleep 10
        
        if ! docker info &> /dev/null; then
            echo -e "${RED}[ERROR] Could not start Docker. Please start it manually.${NC}"
            exit 1
        fi
    fi
    
    echo -e "${GREEN}[OK] Docker is running${NC}"
}

check_env_file() {
    print_section "Checking Environment Configuration..."
    
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}[WARN] No .env file found. Creating from template...${NC}"
        
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo -e "${GREEN}[OK] Created .env from .env.example${NC}"
        else
            echo "Creating default .env file..."
            cat > .env << 'EOF'
# Database Configuration
POSTGRES_USER=monaa
POSTGRES_PASSWORD=sicherespasswort
POSTGRES_DB=monaa_lisa_db

# Semantic Scholar API Key (optional but recommended)
SEMANTIC_SCHOLAR_API_KEY=

# Data directory
DATA_DIR=/app/data
EOF
            echo -e "${GREEN}[OK] Created default .env file${NC}"
        fi
        
        echo ""
        echo "Please review and edit .env if needed."
        read -p "Press Enter to continue or Ctrl+C to exit and edit .env first..."
    else
        echo -e "${GREEN}[OK] .env file exists${NC}"
    fi
}

check_mirrors() {
    print_section "Checking Mirror Configuration..."
    
    if [ ! -f "mirrors.json" ]; then
        echo -e "${RED}[ERROR] mirrors.json not found!${NC}"
        echo "This file is required for downloading the dataset."
        exit 1
    fi
    
    echo -e "${GREEN}[OK] mirrors.json found${NC}"
}

select_action() {
    print_section "Select Action"
    
    echo ""
    echo "  1) Fresh Start (clean volumes + rebuild)"
    echo "  2) Start Services (keep existing data)"
    echo "  3) Stop Services"
    echo "  4) View Logs"
    echo "  5) Reset Database Only"
    echo "  6) Exit"
    echo ""
    
    read -p "Enter choice [1-6]: " choice
    
    case $choice in
        1) fresh_start ;;
        2) start_services ;;
        3) stop_services ;;
        4) view_logs ;;
        5) reset_database ;;
        6) echo "Goodbye!"; exit 0 ;;
        *) echo -e "${RED}Invalid choice${NC}"; select_action ;;
    esac
}

fresh_start() {
    print_section "Fresh Start - Cleaning Everything..."
    
    echo -e "${YELLOW}[WARN] This will delete all existing data!${NC}"
    read -p "Are you sure? (y/N): " confirm
    
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Cancelled."
        select_action
        return
    fi
    
    echo ""
    echo "Stopping containers..."
    docker-compose down -v 2>/dev/null || true
    
    echo "Removing old images..."
    docker rmi monaa-lisa-app:latest monaa-lisa-frontend:latest 2>/dev/null || true
    
    echo ""
    echo "Building and starting fresh..."
    docker-compose up --build -d
    
    echo ""
    echo -e "${GREEN}[OK] Services started!${NC}"
    echo ""
    echo "--------------------------------------------------------------------"
    echo "Access Points:"
    echo "  Frontend:  http://localhost:5173"
    echo "  Backend:   http://localhost:3000"
    echo "  Database:  localhost:5432"
    echo "--------------------------------------------------------------------"
    echo ""
    echo "First run will download ~10GB of data. Check progress with:"
    echo "  docker logs -f monaa-lisa-app-1"
    echo ""
    
    read -p "Press Enter to view logs or 'q' to exit: " view
    if [[ "$view" != "q" ]]; then
        docker-compose logs -f
    fi
}

start_services() {
    print_section "Starting Services..."
    
    docker-compose up -d
    
    echo ""
    echo -e "${GREEN}[OK] Services started!${NC}"
    echo ""
    echo "--------------------------------------------------------------------"
    echo "Access Points:"
    echo "  Frontend:  http://localhost:5173"
    echo "  Backend:   http://localhost:3000"
    echo "  Database:  localhost:5432"
    echo "--------------------------------------------------------------------"
    
    read -p "Press Enter to return to menu..."
    select_action
}

stop_services() {
    print_section "Stopping Services..."
    
    docker-compose down
    
    echo -e "${GREEN}[OK] All services stopped${NC}"
    
    read -p "Press Enter to return to menu..."
    select_action
}

view_logs() {
    print_section "View Logs (Ctrl+C to exit)"
    
    echo ""
    echo "Select service:"
    echo "  1) All services"
    echo "  2) App (Python pipeline)"
    echo "  3) Backend (NestJS)"
    echo "  4) Database (PostgreSQL)"
    echo "  5) Frontend (Svelte)"
    echo ""
    
    read -p "Enter choice [1-5]: " log_choice
    
    case $log_choice in
        1) docker-compose logs -f ;;
        2) docker-compose logs -f app ;;
        3) docker-compose logs -f backend ;;
        4) docker-compose logs -f db ;;
        5) docker-compose logs -f frontend ;;
        *) docker-compose logs -f ;;
    esac
    
    select_action
}

reset_database() {
    print_section "Resetting Database..."
    
    echo -e "${YELLOW}[WARN] This will delete all database data!${NC}"
    read -p "Are you sure? (y/N): " confirm
    
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Cancelled."
        select_action
        return
    fi
    
    echo "Stopping services..."
    docker-compose down
    
    echo "Removing database volume..."
    docker volume rm monaa-lisa_pgdata 2>/dev/null || true
    
    echo "Starting services..."
    docker-compose up -d
    
    echo -e "${GREEN}[OK] Database reset complete${NC}"
    
    read -p "Press Enter to return to menu..."
    select_action
}

# Main
print_header
check_docker
check_env_file
check_mirrors
select_action
