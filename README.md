# Kubernetes Autoscaling + GitOps Demo

A containerized app deployed to Kubernetes via Helm, with real Horizontal
Pod Autoscaling, GitOps-based continuous deployment via ArgoCD, and
Prometheus/Grafana monitoring — running entirely on a local cluster, no
cloud account or spend required.

## Why this project, and why local

Kubernetes expertise is valued independent of which cloud it runs on the same manifests here would work on EKS, GKE, or AKS with only the image registry and a couple of values changed.Running it locally (via Kind) means the entire thing is testable end-to-end for free, with no AWS dependency at all.

## What this demonstrates

- **Real autoscaling, not a config file that's never been tested.** 
The app has a genuinely CPU-bound `/work` endpoint (not a fake sleep), and a load-testing script that drives real load against it so the HPA scaling from 2 to more pods is something you can actually watch happen, not just claim.
- **GitOps, not manual `kubectl apply`.** ArgoCD watches this repo and keeps the cluster in sync automatically. The CI workflow demonstrates the full loop: code change → image built and pushed → Helm chart's image tag bumped automatically → ArgoCD detects the change → cluster updates itself, with no manual deployment step.
- **Production-shaped packaging.** A proper Helm chart (not raw YAML copy-pasted around) with configurable values, resource requests/limits, health probes, and autoscaling the way real teams package Kubernetes apps.
- **Real monitoring.** Prometheus + Grafana, the industry-standard stack, not just `kubectl top`.

## Architecture

```
GitHub push -> GitHub Actions -> build image -> push to Docker Hub
                                       |
                                       v
                          bump image tag in Helm chart -> git push
                                       |
                                       v
                    ArgoCD detects the change -> syncs cluster automatically
                                       |
                                       v
              Kubernetes: Deployment (2-8 pods) <-> HPA watches CPU
                                       |
                                       v
                          Service -> pods serve /work, /health
                                       |
                                       v
                    Prometheus scrapes metrics -> Grafana dashboards
```

## Components

- **`app/`** — the FastAPI demo service. `/health` for probes, `/work` for
  genuinely CPU-bound load (verified locally: real measured duration, not
  a fixed sleep).
- **`helm-chart/`** — Deployment, Service, and HorizontalPodAutoscaler,
  fully configurable via `values.yaml`. Templates validated for correct
  YAML structure before use.
- **`argocd/application.yaml`** — the GitOps definition: which repo/path
  ArgoCD watches, and that it should auto-sync and self-heal (revert any
  manual `kubectl` changes back to match the repo).
- **`monitoring/prometheus-values.yaml`** — trimmed-down values for
  installing the community `kube-prometheus-stack` chart on a small local
  cluster.
- **`load-testing/generate_load.py`** — concurrent load generator, tested
  locally (26/26 requests succeeded in a live test run against the app).
- **`.github/workflows/build-and-push.yml`** — builds the image, pushes to
  Docker Hub, and bumps the Helm chart's image tag automatically, which is
  what actually triggers ArgoCD to deploy the new version.

## What's been tested, and what hasn't

Tested locally, directly: the FastAPI app (`/health` and `/work` both
verified working, with `/work` confirmed to do real measurable CPU work),
and the load-testing script (a live run completed 26/26 successful
requests). The Helm templates were validated for correct YAML structure.

**Not yet tested**: the actual cluster deployment, HPA scaling behavior,
ArgoCD sync, and the Prometheus/Grafana install — these need a real
Kubernetes cluster (Docker + Kind), which isn't available in the
environment this was built in. Follow the setup below on your own machine
to complete that testing — and same as the AWS projects, if something
errors, bring the exact error back and we'll debug it together.

## Setup

### 1. Prerequisites
- Docker Desktop installed and running
- `kubectl`, `helm`, and `kind` installed
- A Docker Hub account (free) for pushing images

### 2. Create the local cluster
```bash
kind create cluster --name gitops-demo
kubectl cluster-info
```

### 3. Install the metrics server (required for HPA to work)
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
# Kind's cluster needs one extra flag for metrics-server to work locally:
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

### 4. Build and load the image directly (fastest path for local testing)
```bash
docker build -t k8s-autoscaling-demo:latest .
kind load docker-image k8s-autoscaling-demo:latest --name gitops-demo
```

### 5. Deploy with Helm directly (to confirm it works, before adding GitOps)
```bash
helm install demo ./helm-chart
kubectl get pods -w
```

### 6. Port-forward and confirm it's actually serving
```bash
kubectl port-forward svc/demo-k8s-autoscaling-demo 8080:80
curl http://localhost:8080/health
```

### 7. Generate load and watch the HPA scale
In one terminal:
```bash
kubectl get hpa -w
```
In another:
```bash
pip install requests
python load-testing/generate_load.py --url http://localhost:8080 --duration 180 --concurrency 20
```
Watch the `REPLICAS` column climb as CPU usage crosses the 50% threshold —
this is your portfolio screenshot.

### 8. Install ArgoCD (for the GitOps piece)
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl port-forward svc/argocd-server -n argocd 8081:443
```
Get the initial admin password:
```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```
Open https://localhost:8081, log in as `admin`, then:
```bash
kubectl apply -f argocd/application.yaml
```
Update `argocd/application.yaml`'s `repoURL` first to point at your actual
GitHub repo.

### 9. Install Prometheus + Grafana
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  -f monitoring/prometheus-values.yaml -n monitoring --create-namespace
kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80
```
Log into Grafana at http://localhost:3000 (`admin` / `admin`, matching the
values file) and explore the pre-built Kubernetes dashboards.

### 10. Set up the CI/CD secrets
In your GitHub repo: Settings → Secrets and variables → Actions, add
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (create a token at
hub.docker.com → Account Settings → Security).

## Tear down
```bash
kind delete cluster --name gitops-demo
```
