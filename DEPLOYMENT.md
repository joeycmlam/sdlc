# SDLC AI Agent Platform — Deployment Guide

This guide covers production deployment strategies for the SDLC AI Agent Platform across Docker Compose, Kubernetes, and cloud providers.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Docker Compose Deployment](#docker-compose-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Provider Guides](#cloud-provider-guides)
6. [Monitoring & Observability](#monitoring--observability)
7. [Backup & Recovery](#backup--recovery)
8. [Security Hardening](#security-hardening)
9. [Performance Optimization](#performance-optimization)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Infrastructure Requirements

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| **CPU** | 2 cores | 4 cores | 8+ cores |
| **Memory** | 4 GB | 8 GB | 16+ GB |
| **Storage** | 20 GB | 50 GB | 100+ GB SSD |
| **Network** | 100 Mbps | 1 Gbps | 10 Gbps |

### Software Requirements

- **Container Runtime**: Docker 24+ or containerd 1.7+
- **Orchestration**: Docker Compose 2.0+ or Kubernetes 1.28+
- **Redis**: 7.0+ (managed service recommended)
- **TLS Certificates**: Valid SSL/TLS certificates for HTTPS
- **DNS**: Configured domains for services

### External Service Accounts

- **GitHub**:
  - GitHub CLI authenticated (`gh auth login`)
  - GitHub Personal Access Token with `repo`, `issues:write`, `read:user`
  - Optional: GitHub App for fine-grained permissions

- **Atlassian**:
  - Jira API token ([id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens))
  - Confluence API token (same token works for both)
  - User account with appropriate permissions

- **Cloud Provider** (for managed services):
  - AWS: IAM roles for ECS, ElastiCache, CloudWatch
  - Azure: Service principals for AKS, Redis Cache, Monitor
  - GCP: Service accounts for GKE, Memorystore, Operations

---

## Environment Configuration

### Environment Variables

Create a `.env` file or configure via secrets manager:

```bash
# ─────────────────────────────────────────────────────────────
# Core Configuration
# ─────────────────────────────────────────────────────────────

# Redis (required for sessions)
REDIS_URL=redis://redis:6379/0
# Production: Use managed service
# REDIS_URL=redis://:password@redis.example.com:6379/0

# Session TTL (seconds)
SESSION_TTL_SECONDS=86400  # 24 hours

# ─────────────────────────────────────────────────────────────
# GitHub Configuration
# ─────────────────────────────────────────────────────────────

# GitHub Personal Access Token (for REST API)
GH_TOKEN=ghp_...
# or GITHUB_TOKEN=ghp_...

# GitHub Copilot CLI (uses OAuth, no token needed)
# Authenticate with: gh auth login

# ─────────────────────────────────────────────────────────────
# Atlassian Configuration
# ─────────────────────────────────────────────────────────────

# Jira
JIRA_URL=https://yourorg.atlassian.net
JIRA_USER=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token

# Confluence
CONFLUENCE_URL=https://yourorg.atlassian.net/wiki
CONFLUENCE_USER=your-email@example.com
CONFLUENCE_API_TOKEN=your-confluence-api-token

# ─────────────────────────────────────────────────────────────
# Service Configuration
# ─────────────────────────────────────────────────────────────

# API Server
PORT=8001
ATLASSIAN_BRIDGE_URL=http://atlassian-bridge:8002

# Frontend
NEXT_PUBLIC_API_URL=http://copilot-agent:8001
# Production: Use public domain
# NEXT_PUBLIC_API_URL=https://api.example.com

# Atlassian Bridge
ALLOWED_ORIGINS=http://localhost:3000,https://yourapp.com

# ─────────────────────────────────────────────────────────────
# Worker Configuration
# ─────────────────────────────────────────────────────────────

ARQ_MAX_JOBS=10          # Concurrent jobs per worker
ARQ_JOB_TIMEOUT=600      # 10 minutes per job
ARQ_REDIS_POOL_SIZE=20   # Redis connection pool size

# ─────────────────────────────────────────────────────────────
# Monitoring & Logging
# ─────────────────────────────────────────────────────────────

LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
SENTRY_DSN=https://...@sentry.io/...  # Optional error tracking
```

### Secrets Management

**Development**: `.env` file (not committed to Git)

**Production**: Use cloud provider secrets manager

#### AWS Secrets Manager
```bash
aws secretsmanager create-secret \
  --name sdlc/production/github-token \
  --secret-string "ghp_..."

aws secretsmanager create-secret \
  --name sdlc/production/jira-credentials \
  --secret-string '{"url":"...","user":"...","token":"..."}'
```

#### Azure Key Vault
```bash
az keyvault secret set \
  --vault-name sdlc-vault \
  --name github-token \
  --value "ghp_..."

az keyvault secret set \
  --vault-name sdlc-vault \
  --name jira-credentials \
  --value '{"url":"...","user":"...","token":"..."}'
```

#### HashiCorp Vault
```bash
vault kv put secret/sdlc/github-token value=ghp_...
vault kv put secret/sdlc/jira-credentials \
  url=https://... \
  user=email@example.com \
  token=...
```

---

## Docker Compose Deployment

### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--pass", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - sdlc-network

  atlassian-bridge:
    build:
      context: ./atlassian-bridge
    restart: always
    environment:
      - JIRA_URL=${JIRA_URL}
      - JIRA_USER=${JIRA_USER}
      - JIRA_API_TOKEN=${JIRA_API_TOKEN}
      - CONFLUENCE_URL=${CONFLUENCE_URL}
      - CONFLUENCE_USER=${CONFLUENCE_USER}
      - CONFLUENCE_API_TOKEN=${CONFLUENCE_API_TOKEN}
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
    ports:
      - "8002:8002"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - sdlc-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  copilot-agent:
    build:
      context: ./sdlc-app/services/copilot-agent
    restart: always
    environment:
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - ATLASSIAN_BRIDGE_URL=http://atlassian-bridge:8002
      - GH_TOKEN=${GH_TOKEN}
      - SESSION_TTL_SECONDS=${SESSION_TTL_SECONDS:-86400}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    ports:
      - "8001:8001"
    depends_on:
      redis:
        condition: service_healthy
      atlassian-bridge:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - sdlc-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  arq-worker:
    build:
      context: ./sdlc-app/services/copilot-agent
    command: ["agent-worker"]
    restart: always
    environment:
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - ATLASSIAN_BRIDGE_URL=http://atlassian-bridge:8002
      - GH_TOKEN=${GH_TOKEN}
      - ARQ_MAX_JOBS=${ARQ_MAX_JOBS:-10}
      - ARQ_JOB_TIMEOUT=${ARQ_JOB_TIMEOUT:-600}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    depends_on:
      redis:
        condition: service_healthy
      copilot-agent:
        condition: service_healthy
    networks:
      - sdlc-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      replicas: 3  # Scale workers based on load

  frontend:
    build:
      context: ./sdlc-app
      args:
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL}
    restart: always
    environment:
      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
    ports:
      - "3000:3000"
    depends_on:
      copilot-agent:
        condition: service_healthy
    networks:
      - sdlc-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  redis_data:
    driver: local

networks:
  sdlc-network:
    driver: bridge
```

### Deployment Steps

```bash
# 1. Pull latest code
git pull origin main

# 2. Configure environment
cp .env.example .env
# Edit .env with production values

# 3. Build images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 4. Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 5. Verify health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:3000/api/health

# 6. Monitor logs
docker compose logs -f
```

### Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/sdlc

upstream frontend {
    server localhost:3000;
}

upstream api {
    server localhost:8001;
}

upstream atlassian {
    server localhost:8002;
}

server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API Server
    location /api/ {
        proxy_pass http://api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # Atlassian Bridge (internal only, optional)
    location /atlassian/ {
        deny all;  # Block external access
    }
}
```

---

## Kubernetes Deployment

### Namespace & ConfigMap

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sdlc-platform

---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sdlc-config
  namespace: sdlc-platform
data:
  SESSION_TTL_SECONDS: "86400"
  LOG_LEVEL: "INFO"
  ALLOWED_ORIGINS: "https://sdlc.example.com"
  NEXT_PUBLIC_API_URL: "https://api.sdlc.example.com"
```

### Secrets

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: sdlc-secrets
  namespace: sdlc-platform
type: Opaque
stringData:
  REDIS_PASSWORD: "your-redis-password"
  GH_TOKEN: "ghp_..."
  JIRA_URL: "https://yourorg.atlassian.net"
  JIRA_USER: "your-email@example.com"
  JIRA_API_TOKEN: "your-jira-token"
  CONFLUENCE_URL: "https://yourorg.atlassian.net/wiki"
  CONFLUENCE_USER: "your-email@example.com"
  CONFLUENCE_API_TOKEN: "your-confluence-token"
```

Apply secrets:
```bash
kubectl apply -f secrets.yaml
```

### Redis StatefulSet

```yaml
# redis-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: sdlc-platform
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
          - redis-server
          - --requirepass
          - $(REDIS_PASSWORD)
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: REDIS_PASSWORD
        ports:
        - containerPort: 6379
          name: redis
        volumeMounts:
        - name: redis-data
          mountPath: /data
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          exec:
            command:
            - redis-cli
            - --pass
            - $(REDIS_PASSWORD)
            - ping
          initialDelaySeconds: 30
          periodSeconds: 10
  volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 10Gi

---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: sdlc-platform
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
  clusterIP: None
```

### Atlassian Bridge Deployment

```yaml
# atlassian-bridge.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atlassian-bridge
  namespace: sdlc-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: atlassian-bridge
  template:
    metadata:
      labels:
        app: atlassian-bridge
    spec:
      containers:
      - name: atlassian-bridge
        image: your-registry/atlassian-bridge:latest
        ports:
        - containerPort: 8002
        env:
        - name: JIRA_URL
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: JIRA_URL
        - name: JIRA_USER
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: JIRA_USER
        - name: JIRA_API_TOKEN
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: JIRA_API_TOKEN
        - name: CONFLUENCE_URL
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: CONFLUENCE_URL
        - name: CONFLUENCE_USER
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: CONFLUENCE_USER
        - name: CONFLUENCE_API_TOKEN
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: CONFLUENCE_API_TOKEN
        - name: ALLOWED_ORIGINS
          valueFrom:
            configMapKeyRef:
              name: sdlc-config
              key: ALLOWED_ORIGINS
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: atlassian-bridge
  namespace: sdlc-platform
spec:
  selector:
    app: atlassian-bridge
  ports:
  - port: 8002
    targetPort: 8002
  type: ClusterIP
```

### Copilot Agent Deployment

```yaml
# copilot-agent.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: copilot-agent
  namespace: sdlc-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: copilot-agent
  template:
    metadata:
      labels:
        app: copilot-agent
    spec:
      containers:
      - name: copilot-agent
        image: your-registry/copilot-agent:latest
        command: ["agent-api", "--host", "0.0.0.0", "--port", "8001"]
        ports:
        - containerPort: 8001
        env:
        - name: REDIS_URL
          value: "redis://:$(REDIS_PASSWORD)@redis:6379/0"
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: REDIS_PASSWORD
        - name: GH_TOKEN
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: GH_TOKEN
        - name: ATLASSIAN_BRIDGE_URL
          value: "http://atlassian-bridge:8002"
        - name: SESSION_TTL_SECONDS
          valueFrom:
            configMapKeyRef:
              name: sdlc-config
              key: SESSION_TTL_SECONDS
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: sdlc-config
              key: LOG_LEVEL
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 20
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: copilot-agent
  namespace: sdlc-platform
spec:
  selector:
    app: copilot-agent
  ports:
  - port: 8001
    targetPort: 8001
  type: ClusterIP
```

### Arq Worker Deployment

```yaml
# arq-worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: arq-worker
  namespace: sdlc-platform
spec:
  replicas: 5
  selector:
    matchLabels:
      app: arq-worker
  template:
    metadata:
      labels:
        app: arq-worker
    spec:
      containers:
      - name: arq-worker
        image: your-registry/copilot-agent:latest
        command: ["agent-worker"]
        env:
        - name: REDIS_URL
          value: "redis://:$(REDIS_PASSWORD)@redis:6379/0"
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: REDIS_PASSWORD
        - name: GH_TOKEN
          valueFrom:
            secretKeyRef:
              name: sdlc-secrets
              key: GH_TOKEN
        - name: ATLASSIAN_BRIDGE_URL
          value: "http://atlassian-bridge:8002"
        - name: ARQ_MAX_JOBS
          value: "10"
        - name: ARQ_JOB_TIMEOUT
          value: "600"
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: sdlc-config
              key: LOG_LEVEL
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

### Frontend Deployment

```yaml
# frontend.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: sdlc-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: your-registry/frontend:latest
        ports:
        - containerPort: 3000
        env:
        - name: NEXT_PUBLIC_API_URL
          valueFrom:
            configMapKeyRef:
              name: sdlc-config
              key: NEXT_PUBLIC_API_URL
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: sdlc-platform
spec:
  selector:
    app: frontend
  ports:
  - port: 3000
    targetPort: 3000
  type: ClusterIP
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sdlc-ingress
  namespace: sdlc-platform
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - sdlc.example.com
    - api.sdlc.example.com
    secretName: sdlc-tls
  rules:
  - host: sdlc.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 3000
  - host: api.sdlc.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: copilot-agent
            port:
              number: 8001
```

### HorizontalPodAutoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: copilot-agent-hpa
  namespace: sdlc-platform
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: copilot-agent
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: arq-worker-hpa
  namespace: sdlc-platform
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: arq-worker
  minReplicas: 5
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 75
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 85
```

### Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f redis-statefulset.yaml
kubectl apply -f atlassian-bridge.yaml
kubectl apply -f copilot-agent.yaml
kubectl apply -f arq-worker.yaml
kubectl apply -f frontend.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml

# Verify deployment
kubectl get pods -n sdlc-platform
kubectl get services -n sdlc-platform
kubectl get ingress -n sdlc-platform

# Check logs
kubectl logs -n sdlc-platform -l app=copilot-agent
kubectl logs -n sdlc-platform -l app=arq-worker
```

---

## Cloud Provider Guides

### AWS (ECS + ElastiCache)

**Architecture**:
- **ECS Fargate**: Run containers without managing servers
- **ElastiCache for Redis**: Managed Redis cluster
- **Application Load Balancer**: HTTPS termination
- **CloudWatch**: Logging and monitoring
- **Secrets Manager**: Credential storage

**Deployment**:
```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name sdlc-platform

# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id sdlc-redis \
  --engine redis \
  --cache-node-type cache.t3.medium \
  --num-cache-nodes 1

# Register task definitions
aws ecs register-task-definition --cli-input-json file://copilot-agent-task.json
aws ecs register-task-definition --cli-input-json file://arq-worker-task.json
aws ecs register-task-definition --cli-input-json file://frontend-task.json

# Create services
aws ecs create-service --cli-input-json file://copilot-agent-service.json
aws ecs create-service --cli-input-json file://arq-worker-service.json
aws ecs create-service --cli-input-json file://frontend-service.json
```

### Azure (AKS + Azure Cache for Redis)

**Architecture**:
- **AKS**: Managed Kubernetes
- **Azure Cache for Redis**: Managed Redis
- **Application Gateway**: HTTPS termination
- **Azure Monitor**: Logging and monitoring
- **Key Vault**: Credential storage

**Deployment**:
```bash
# Create AKS cluster
az aks create \
  --resource-group sdlc-rg \
  --name sdlc-aks \
  --node-count 3 \
  --enable-managed-identity \
  --generate-ssh-keys

# Create Redis cache
az redis create \
  --resource-group sdlc-rg \
  --name sdlc-redis \
  --location eastus \
  --sku Standard \
  --vm-size c1

# Get AKS credentials
az aks get-credentials --resource-group sdlc-rg --name sdlc-aks

# Deploy to AKS (use Kubernetes manifests above)
kubectl apply -f k8s/
```

### GCP (GKE + Memorystore)

**Architecture**:
- **GKE**: Managed Kubernetes
- **Memorystore for Redis**: Managed Redis
- **Cloud Load Balancing**: HTTPS termination
- **Cloud Operations**: Logging and monitoring
- **Secret Manager**: Credential storage

**Deployment**:
```bash
# Create GKE cluster
gcloud container clusters create sdlc-cluster \
  --num-nodes 3 \
  --enable-autoscaling \
  --min-nodes 3 \
  --max-nodes 10 \
  --zone us-central1-a

# Create Redis instance
gcloud redis instances create sdlc-redis \
  --size=2 \
  --region=us-central1 \
  --redis-version=redis_7_0

# Get cluster credentials
gcloud container clusters get-credentials sdlc-cluster --zone us-central1-a

# Deploy to GKE
kubectl apply -f k8s/
```

---

## Monitoring & Observability

### Prometheus Metrics

Add Prometheus instrumentation to services:

```python
# api_server.py
from prometheus_client import Counter, Histogram, Gauge

request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
active_sessions = Gauge('active_sessions_total', 'Active sessions')
```

### Grafana Dashboards

**Key Metrics**:
- Request rate (req/s)
- Response latency (p50, p95, p99)
- Error rate (%)
- Active sessions
- Queue depth (Arq)
- Redis memory usage
- Worker concurrency

### Logging

**Structured Logging**:
```python
import logging
import json

logger = logging.getLogger(__name__)

def log_event(event_type, session_id, **kwargs):
    logger.info(json.dumps({
        "event": event_type,
        "session_id": session_id,
        **kwargs
    }))
```

**Log Aggregation**:
- **ELK Stack**: Elasticsearch, Logstash, Kibana
- **Datadog**: APM and log aggregation
- **CloudWatch Logs**: AWS-native logging
- **Azure Monitor**: Azure-native logging
- **Cloud Logging**: GCP-native logging

---

## Backup & Recovery

### Redis Backup

**RDB Snapshots**:
```bash
# Trigger manual snapshot
redis-cli SAVE

# Automated snapshots (redis.conf)
save 900 1      # Save after 900s if 1+ key changed
save 300 10     # Save after 300s if 10+ keys changed
save 60 10000   # Save after 60s if 10000+ keys changed
```

**AWS ElastiCache**:
- Enable automatic backups (daily snapshots)
- Retention: 1-35 days
- Manual snapshots for major updates

**Azure Cache**:
- Enable data persistence (RDB or AOF)
- Export backups to Storage Account

### Disaster Recovery

**Recovery Time Objective (RTO)**: 15 minutes
**Recovery Point Objective (RPO)**: 1 hour

**Runbook**:
1. Detect failure (monitoring alert)
2. Assess impact (Redis down, service degraded)
3. Restore Redis from latest snapshot
4. Restart dependent services
5. Verify health checks
6. Monitor for 15 minutes

---

## Security Hardening

### Network Security

- **Firewall Rules**: Restrict Redis to cluster IPs only
- **VPC/VNet**: Isolate services in private network
- **Security Groups**: Minimal ingress/egress rules
- **TLS**: Enable Redis TLS (6380) for production

### Application Security

- **Rate Limiting**: Throttle API requests per IP
- **Input Validation**: Sanitize all user inputs
- **CSRF Protection**: Token-based CSRF for mutations
- **Audit Logging**: Log all approval decisions

### Credential Rotation

```bash
# Rotate GitHub token quarterly
gh auth refresh

# Rotate Jira/Confluence tokens
# 1. Generate new token at id.atlassian.com
# 2. Update secrets in cluster
kubectl create secret generic sdlc-secrets \
  --from-literal=JIRA_API_TOKEN=new-token \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Restart services to pick up new token
kubectl rollout restart deployment/atlassian-bridge -n sdlc-platform
```

---

## Performance Optimization

### Redis Tuning

```bash
# Increase max memory
maxmemory 4gb
maxmemory-policy allkeys-lru

# Enable pipelining
tcp-keepalive 300

# Disable persistence for performance (if acceptable)
save ""
appendonly no
```

### Worker Scaling

**Auto-scale based on queue depth**:
```yaml
# Custom metric: arq:queue length
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: arq-worker-queue-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: arq-worker
  minReplicas: 5
  maxReplicas: 20
  metrics:
  - type: External
    external:
      metric:
        name: arq_queue_depth
      target:
        type: AverageValue
        averageValue: "10"  # 10 jobs per worker
```

---

## Troubleshooting

### Service Won't Start

**Check logs**:
```bash
kubectl logs -n sdlc-platform -l app=copilot-agent --tail=100
docker logs copilot-agent --tail=100
```

**Common causes**:
- Missing environment variables
- Redis connection failure
- Port already in use

### High Memory Usage

**Check Redis memory**:
```bash
redis-cli INFO memory
```

**Solutions**:
- Reduce `SESSION_TTL_SECONDS`
- Increase Redis `maxmemory`
- Enable eviction policy: `maxmemory-policy allkeys-lru`

### Slow Response Times

**Check metrics**:
- LLM API latency (GitHub Models)
- Redis latency (`redis-cli --latency`)
- Network latency (inter-service)

**Solutions**:
- Scale workers horizontally
- Use Redis connection pooling
- Cache frequently accessed data

---

## Maintenance

### Rolling Updates

```bash
# Kubernetes
kubectl set image deployment/copilot-agent \
  copilot-agent=your-registry/copilot-agent:v2.0.0 \
  -n sdlc-platform

kubectl rollout status deployment/copilot-agent -n sdlc-platform

# Docker Compose
docker compose pull
docker compose up -d --no-deps --build copilot-agent
```

### Health Checks

```bash
# API health
curl https://api.sdlc.example.com/health

# Redis health
redis-cli -h redis.example.com -a password ping

# Queue depth
redis-cli -h redis.example.com -a password LLEN arq:queue
```

---

## Checklist

### Pre-Deployment

- [ ] All environment variables configured
- [ ] Secrets stored in secrets manager (not `.env` files)
- [ ] SSL/TLS certificates obtained and configured
- [ ] DNS records created and verified
- [ ] GitHub CLI authenticated on worker nodes
- [ ] Atlassian API tokens generated and tested
- [ ] Redis configured with authentication
- [ ] Firewall rules and security groups configured
- [ ] Monitoring and alerting configured
- [ ] Backup strategy defined and tested

### Post-Deployment

- [ ] Health checks passing for all services
- [ ] End-to-end workflow tested (create session, run agent, approve checkpoint)
- [ ] Monitoring dashboards displaying metrics
- [ ] Logs aggregating correctly
- [ ] SSL/TLS certificates valid
- [ ] Autoscaling policies tested
- [ ] Disaster recovery plan documented
- [ ] Runbooks created for common incidents

---

## Support

For deployment assistance:
- GitHub Issues: [your-repo/issues](https://github.com/your-org/your-repo/issues)
- Slack: #sdlc-platform
- Email: platform-team@example.com

---

**Last Updated**: 2026-05-23
