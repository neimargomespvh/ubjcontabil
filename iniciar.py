cd ~/Projetos/UbjContabil

# se ainda não tiver .env
cp -n .env.example .env
# edite JWT_SECRET (>=32 chars) e ADMIN_PASSWORD

# evita conflito de porta
sed -i 's/"5432:5432"/"5433:5432"/' docker-compose.yml

docker compose down
docker compose up -d

# acompanhar
docker compose ps
docker compose logs -f db
# quando o db estiver healthy:
docker compose logs -f admin