"""
Fires concurrent requests at the /work endpoint to drive real CPU load
against the deployed pods - this is what triggers the HorizontalPodAutoscaler
to actually scale up. Point it at your cluster's service URL.

Usage:
    python generate_load.py --url http://localhost:8080 --duration 120 --concurrency 20
"""
import argparse
import threading
import time

import requests


def worker(url: str, stop_at: float, stats: dict, lock: threading.Lock):
    while time.time() < stop_at:
        try:
            resp = requests.get(f"{url}/work", params={"iterations": 2_000_000}, timeout=10)
            with lock:
                stats["requests"] += 1
                if resp.status_code == 200:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
        except requests.RequestException:
            with lock:
                stats["requests"] += 1
                stats["failed"] += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Base URL of the service, e.g. http://localhost:8080")
    parser.add_argument("--duration", type=int, default=120, help="How long to generate load, in seconds")
    parser.add_argument("--concurrency", type=int, default=20, help="Number of concurrent worker threads")
    args = parser.parse_args()

    print(f"Generating load against {args.url} for {args.duration}s with {args.concurrency} concurrent workers...")
    print("While this runs, in another terminal watch: kubectl get hpa -w")

    stats = {"requests": 0, "success": 0, "failed": 0}
    lock = threading.Lock()
    stop_at = time.time() + args.duration

    threads = [
        threading.Thread(target=worker, args=(args.url, stop_at, stats, lock))
        for _ in range(args.concurrency)
    ]
    for t in threads:
        t.start()

    try:
        while time.time() < stop_at:
            time.sleep(5)
            with lock:
                print(f"  ... {stats['requests']} requests sent so far ({stats['success']} succeeded, {stats['failed']} failed)")
    except KeyboardInterrupt:
        print("Stopping early...")

    for t in threads:
        t.join()

    print(f"\nDone. Total: {stats['requests']} requests, {stats['success']} succeeded, {stats['failed']} failed.")


if __name__ == "__main__":
    main()
