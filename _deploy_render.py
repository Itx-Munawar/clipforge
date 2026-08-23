"""Deploy ClipForge to Render using their API."""
import requests
import json
import time

API_KEY = "rnd_UY6ABsP5S92nNh93QLY4o8WpvrP0"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
BASE = "https://api.render.com/v1"


def deploy():
    # Step 1: Create Docker-based web service
    print("Step 1: Creating web service...")
    payload = {
        "type": "web_service",
        "name": "clipforge",
        "repo": "https://github.com/Itx-Munawar/clipforge",
        "branch": "main",
        "service_details": {
            "runtime": "docker",
            "dockerfilePath": "Dockerfile",
            "envVars": [
                {"key": "PORT", "value": "8000"}
            ],
            "plan": "free",
            "healthCheckPath": "/api/health",
            "autoDeploy": "yes",
        },
    }
    r = requests.post(f"{BASE}/services", headers=HEADERS, json=payload)
    if r.status_code not in (200, 201):
        print(f"Failed to create service: {r.status_code}")
        print(r.text[:500])
        return None

    service = r.json()
    service_id = service["id"]
    print(f"Service created: {service_id}")
    print(f"Name: {service.get('name')}")
    return service_id


def wait_for_deploy(service_id):
    """Wait for the service to finish deploying."""
    print("\nStep 2: Waiting for deployment...")
    start = time.time()
    max_wait = 600  # 10 minutes

    while time.time() - start < max_wait:
        r = requests.get(f"{BASE}/services/{service_id}", headers=HEADERS)
        if r.status_code != 200:
            print(f"  Error checking status: {r.status_code}")
            time.sleep(10)
            continue

        svc = r.json()
        details = svc.get("service_details", {})
        status = details.get("status", "unknown")
        last_deploy = details.get("last_deploy", {})
        deploy_status = last_deploy.get("status", "unknown") if last_deploy else "unknown"

        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] Service: {status} | Deploy: {deploy_status}")

        if deploy_status == "live":
            url = details.get("url", "")
            print(f"\n{'='*60}")
            print(f"  DEPLOYED!")
            print(f"  URL: {url}")
            print(f"  Health: {url}/api/health")
            print(f"{'='*60}")
            return url

        if deploy_status in ("build_failed", "canceled"):
            print(f"\nDeployment failed: {deploy_status}")
            # Get logs
            r2 = requests.get(f"{BASE}/services/{service_id}/logs", headers=HEADERS)
            if r2.status_code == 200:
                logs = r2.json()
                print("Last logs:")
                for entry in logs[-20:]:
                    print(f"  {entry.get('message', '')}")
            return None

        time.sleep(15)

    print("Timed out waiting for deployment")
    return None


if __name__ == "__main__":
    service_id = deploy()
    if service_id:
        url = wait_for_deploy(service_id)
        if url:
            print(f"\nYour ClipForge app is live at: {url}")
