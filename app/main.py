"""
A small FastAPI service, deliberately simple, whose only real purpose is to
give Kubernetes something genuine to autoscale. /work does real CPU-bound
computation (not a sleep() or a fake delay) so a load test causes real CPU
pressure - which is what the Horizontal Pod Autoscaler actually measures.
"""
import math
import os
import socket
import time

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="K8s Autoscaling Demo API", version="1.0.0")

POD_NAME = os.getenv("POD_NAME", socket.gethostname())
# my comment

class WorkResponse(BaseModel):
    pod_name: str
    duration_ms: float
    result: float


@app.get("/health")
def health():
    return {"status": "ok", "pod_name": POD_NAME}


@app.get("/")
def root():
    return {"message": "K8s autoscaling demo", "pod_name": POD_NAME}


@app.get("/work", response_model=WorkResponse)
def do_work(iterations: int = 2_000_000):
    """
    Deliberately CPU-bound work (not I/O, not sleep) - repeatedly computes
    sqrt/sin to burn real CPU cycles proportional to `iterations`. This is
    what a load test hits to drive CPU usage up and trigger the HPA.
    """
    start = time.perf_counter()
    total = 0.0
    for i in range(iterations):
        total += math.sqrt(i) * math.sin(i)
    duration_ms = (time.perf_counter() - start) * 1000

    return WorkResponse(pod_name=POD_NAME, duration_ms=duration_ms, result=total)
