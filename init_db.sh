#!/bin/bash

echo "Waiting for database..."
sleep 10  

# Run DB creation script with PYTHONPATH set to include the src directory
docker-compose run --rm -e PYTHONPATH=/app/MonaaLisa/src app python MonaaLisa/src/Database/db.py

echo "Checking if tables were created:"
docker exec -it $(docker-compose ps -q db) psql -U monaa -d monaa_lisa -c "\dt"

echo "Done!"