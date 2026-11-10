# House Inventory

Local-first household inventory web application built with FastAPI and PostgreSQL.

## Quick Start (Docker Compose)

Run the database and web application with a single command:
```
bash
docker compose up --build
```
The app will be available at `http://localhost:8000`. Database files and uploaded media are persisted locally in `./data/postgres` and `./data/media`.

## Running on Kubernetes (OrbStack / Local K8s)

1. Build the image locally so Kubernetes can find `house-inventory:v2`:

```
bash
docker build -t house-inventory:v2 .
```

2. Apply the Kubernetes manifests:

```
bash
kubectl apply -f k8s-orbstack.yaml
```

3. If your `main.py` does not auto-apply `schema.sql` on boot, initialize the schema once:

```
bash
kubectl exec -i statefulset/postgres -- psql -U inventory -d inventory < app/schema.sql
```

4. Access the service at `http://localhost:8000` (or via your OrbStack service domain).
