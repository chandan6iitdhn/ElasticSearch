# Day 15 — Elasticsearch Deployment and Docker Integration

## Course status
- **Session 1:** 5/5 sections completed.
- **Session 2:** 5/5 sections completed.
- **Outcome:** Deployment concepts and read-only verification completed. A fully containerized Flask/PostgreSQL/Elasticsearch stack and persistent-storage migration have **not yet been performed**.

## 1. Deployment architecture
- **Docker image:** packaged filesystem and configuration used to create containers.
- **Container:** running instance of an image. Container != Elasticsearch node in general.
- **Elasticsearch node:** running Elasticsearch process; a cluster can have one or more nodes.
- Flask, PostgreSQL, and Kibana containers are not Elasticsearch nodes.
- Primary and replica shards cannot be allocated to the same Elasticsearch node.

## 2. Docker fundamentals and persistence
- `docker ps` shows running containers; `docker ps -a` includes stopped ones.
- `docker logs --tail 100 es01` inspects Elasticsearch logs.
- Elasticsearch's container data path: `/usr/share/elasticsearch/data`.
- Container writable-layer data survives stop/start and host reboot, but is removed with the container.
- A **named volume** survives container removal and can be reused by a replacement container; it is not a backup.
- Example named volume: `docker volume create es_data`; new container mount: `-v es_data:/usr/share/elasticsearch/data`.
- Existing containers cannot have new mounts attached via `docker update`.
- **Do not run `docker rm es01` or `docker compose down -v` on the existing deployment.**

### Existing environment findings
- Elasticsearch image: `docker.elastic.co/elasticsearch/elasticsearch:9.5.5`; container: `es01`.
- Kibana image: `docker.elastic.co/kibana/kibana:9.5.5`; container: `kib01`.
- Both connected to user-defined Docker network `elastic`.
- Elasticsearch port published to host on IPv4 `0.0.0.0:9200` and IPv6 `[::]:9200`; Kibana on 5601.
- `docker inspect es01 --format '{{json .Mounts}}'` returned `[]`.
- `docker volume ls` returned no volumes.
- `docker exec es01 ls -lah /usr/share/elasticsearch/data` showed `_state`, `indices`, `node.lock`, `nodes`, `snapshot_cache`.
- **Conclusion:** Elasticsearch data currently lives in the `es01` writable layer, not a mounted Docker volume.

## 3. Networking: localhost vs container names
- From Flask running directly on the Linux host, published services may be accessible at `localhost:9200` (Elasticsearch) and `localhost:5432` (PostgreSQL).
- From a Flask container, `localhost` means the Flask container itself.
- On a shared user-defined network, Flask may reach Elasticsearch as `https://es01:9200` and a containerized PostgreSQL service as `postgres:5432`.
- Docker DNS resolves container/service names on supported networks.
- Container-to-container traffic does not require host port publishing.
- `ports: ["5000:5000"]` maps HOST_PORT:CONTAINER_PORT; `EXPOSE` alone does not publish a port.
- HTTPS requires a trusted CA and a server certificate valid for the hostname actually used. `https://es01:9200` must be verified against the certificate, not assumed to work.
- Host port binding to `0.0.0.0` can expose services on multiple network interfaces. Bind to loopback or use network controls when external access is unnecessary.

## 4. Configuration and TLS
- Use environment variables rather than hardcoding secrets:
  - `ELASTICSEARCH_URL`
  - `ES_USERNAME`
  - `ES_PASSWORD`
  - `ES_CA_CERT`
  - `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- A CA certificate verifies Elasticsearch's TLS certificate. TLS protects data in transit; it is not encryption at rest.
- A host certificate file is not automatically accessible inside a Flask container; mount it read-only at a path the app uses.
- Use appropriately scoped application credentials, not administrator credentials where avoidable.

## 5. Dockerizing Flask
Illustrative Dockerfile (adjust entry point and dependencies to actual project):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

- `FROM`: base image.
- `WORKDIR`: working directory in image.
- `COPY`: copy build-context files.
- `RUN`: execute during image build (e.g., install dependencies).
- `CMD`: default container startup command; can be overridden at runtime.
- `docker build -t study-search-api:1.0 .` builds an image.
- `docker run ... study-search-api:1.0` creates and starts a container.
- Exclude `.venv/`, `.git/`, `__pycache__/`, `.env`, and other unnecessary/sensitive files with `.dockerignore`.
- Verify Flask entry point and include Gunicorn in dependencies before using the sample as a runnable configuration.

## 6. Docker Compose
- Compose defines services, networks, volumes, ports, environment, and startup relationships in YAML.
- Common commands:
  - `docker compose up -d`
  - `docker compose ps`
  - `docker compose logs -f`
  - `docker compose stop`
  - `docker compose start`
  - `docker compose down` (does not normally delete named volumes)
  - `docker compose down -v` (**removes Compose-managed named volumes**; dangerous for data)
- Reuse existing network if appropriate:

```yaml
networks:
  elastic:
    external: true
```

- `depends_on` short syntax controls startup order but does not guarantee readiness.
- `condition: service_healthy` waits for a configured dependency health check to pass before starting a dependent service.
- Health checks help at startup; application code still needs timeouts, retries where appropriate, and error handling for failures after startup.

## 7. Health checks
- `running` means the container's main process is running.
- Docker `healthy`/`unhealthy` requires a configured health check.
- Elasticsearch cluster `green`/`yellow`/`red` describes shard allocation, not Docker health-check status.
- Example PostgreSQL probe: `pg_isready -U study_user -d study_db` (readiness, not proof of every application operation).
- A single-node Elasticsearch cluster may legitimately be Yellow when primary shards are allocated but replicas cannot be assigned.
- Existing `es01` inspection:

```text
Healthcheck: null
Health status: Not configured
```

- This means no Docker health check is configured; it does **not** mean Elasticsearch is unhealthy.

## 8. Cluster and index verification
Using the existing host TLS and credentials:

```bash
curl --cacert "$ES_CA_CERT" -u "elastic:$ES_PASSWORD" \
  "https://localhost:9200/_cluster/health?pretty"

curl --cacert "$ES_CA_CERT" -u "elastic:$ES_PASSWORD" \
  "https://localhost:9200/_cat/nodes?v"

curl --cacert "$ES_CA_CERT" -u "elastic:$ES_PASSWORD" \
  "https://localhost:9200/_cat/indices/studies_v3?v"

curl --cacert "$ES_CA_CERT" -u "elastic:$ES_PASSWORD" \
  "https://localhost:9200/studies_v3/_count?pretty"
```

### Observed results during Day 15
- Cluster name: `docker-cluster`; one Elasticsearch node.
- Earlier cluster health: **Yellow**, 61 active primary shards, 5 unassigned shards, 0 unassigned primary shards.
- Node inspection: heap 83%, RAM 100%, CPU 6% at one point in time. A single reading is not enough to diagnose sustained memory pressure.
- Final `studies_v3` output:

```text
health status index      uuid                   pri rep docs.count docs.deleted store.size pri.store.size dataset.size
yellow open   studies_v3 Cs_dJg4tQkadcXSEgvyaUQ   1   1       1000            0     66.3kb         66.3kb       66.3kb
```

- **Interpretation:** Index open; one primary and one configured replica; 1,000 documents; no deleted documents reported; primary searchable. Yellow is expected for an unallocated replica on a single node.
- This is a verified development environment, **not** proof of full production readiness.

## 9. Safe migration strategies
**Option A: Rebuild Elasticsearch from PostgreSQL**
- PostgreSQL is the Study Search API's source of truth.
- If all required data and mappings are reproducible, build a new Elasticsearch deployment with a persistent volume and rerun the bulk indexer.
- Validate mappings, index settings, document counts, and search results before switching traffic.

**Option B: Elasticsearch snapshot and restore**
- Configure a snapshot repository on storage independent of the original container writable layer.
- Create a snapshot; verify completion and integrity.
- Start replacement Elasticsearch with a named data volume and compatible settings.
- Restore; verify indices, mappings, counts, and searches.
- Switch the application only after verification; keep the old container until recovery is proven.
- Do not treat raw copying of live Elasticsearch data files as a supported backup method.

## 10. Deployment troubleshooting workflow
1. `docker ps -a` — are containers running?
2. `docker logs --tail 100 es01` — errors, disk watermarks, OOM, TLS/auth problems?
3. Test authenticated HTTPS from the **same environment as the failing client**.
4. Check `/_cluster/health` and shard availability.
5. Check `/_cat/indices/studies_v3?v`, `/_count`, and direct `/_search`.
6. If direct Elasticsearch search works but Flask fails, investigate Flask hostname, Docker network, credentials, CA path, TLS hostname verification, and application logs.
7. If records are missing, inspect PostgreSQL-to-Elasticsearch bulk/incremental sync.
8. Validate persistence, backups, monitoring, and application failure handling before production deployment.

## 11. Key interview takeaways
- Image vs container vs Elasticsearch node vs cluster are distinct concepts.
- `RUN` executes at image build; `CMD` specifies the container's default startup command.
- `localhost` inside a container refers to that container.
- Publishing ports is not required for communication between containers on the same user-defined network.
- `depends_on` alone is not a readiness check; use health checks and application resilience.
- Container running != Docker healthy != Elasticsearch cluster healthy != application functioning.
- Named volumes provide lifecycle-independent storage; backups provide a separate recovery mechanism.
- Yellow Elasticsearch health means all primaries are assigned, while some replicas are unassigned; Red means at least one primary is unassigned.

## 12. Outstanding hands-on work
- Design and verify safe migration from current `es01` writable-layer storage to persistent volume storage.
- Configure Compose-managed health checks for a **new** deployment.
- Verify actual Flask entry point, Dockerfile, requirements, and container-to-Elasticsearch TLS hostname.
- Build and test an integrated Flask/PostgreSQL/Elasticsearch deployment without disturbing the existing working environment.

**Next:** Day 16 — End-to-End Study Search API.
