#!/bin/bash

echo "Checking database tables:"
docker exec -it $(docker-compose ps -q db) psql -U monaa -d monaa_lisa -c "\dt"
echo ""

echo "Number of papers in database:"
docker exec -it $(docker-compose ps -q db) psql -U monaa -d monaa_lisa -c "SELECT count(*) FROM papers;"
echo ""

echo "All papers in database:"
docker exec -it $(docker-compose ps -q db) psql -U monaa -d monaa_lisa -c "SELECT id, entry_id, title, hash FROM papers;"
echo ""

echo "Full paper details (including summaries):"
docker exec -it $(docker-compose ps -q db) psql -U monaa -d monaa_lisa -c "SELECT * FROM papers;"

echo "Done!"