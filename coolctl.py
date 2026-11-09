#!/usr/bin/env python3
"""
coolctl.py — Antigravity Coolify CLI Controller
Manage Oracle Cloud VPS, Coolify projects, deployments, and logs directly from the terminal.
"""

import sys
import os
import argparse
import subprocess
import json
import urllib.request
import urllib.error

# Load environment configuration from .coolify.env
CONFIG = {
    "url": "http://92.5.62.107:8000",
    "token": "",
    "app_uuid": "xdsdvywwzbh80firse12wyem",
    "ssh_host": "ubuntu@92.5.62.107",
    "ssh_key": os.path.join(os.path.dirname(__file__), ".ssh", "oracle_vps"),
}

env_file = os.path.join(os.path.dirname(__file__), ".coolify.env")
if os.path.exists(env_file):
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.lower().replace("coolify_", "")
                CONFIG[k] = v.strip()


def api_request(endpoint: str, method: str = "GET", data: dict = None):
    url = f"{CONFIG['url'].rstrip('/')}{endpoint}"
    headers = {
        "Authorization": f"Bearer {CONFIG['token']}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    req_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            body = res.read().decode("utf-8")
            try:
                return json.loads(body)
            except Exception:
                return body
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"[!] HTTP Error {e.code}: {err_msg}")
        return None
    except Exception as e:
        print(f"[!] Network Error: {e}")
        return None


def cmd_status(args):
    print("=" * 65)
    print(" 🚀 COOLIFY CLOUD ORCHESTRATOR STATUS")
    print("=" * 65)
    version = api_request("/api/v1/version")
    print(f"[*] Coolify Engine Version : {version}")
    print(f"[*] Endpoint               : {CONFIG['url']}")
    
    apps = api_request("/api/v1/applications")
    if apps and isinstance(apps, list):
        print("\n--- Deployed Applications ---")
        for app in apps:
            name = app.get("name", "Unknown")
            fqdn = app.get("fqdn", "No Domain")
            status = app.get("status", "Unknown")
            uuid = app.get("uuid", "")
            print(f"  • {name}")
            print(f"    UUID   : {uuid}")
            print(f"    URL    : {fqdn}")
            print(f"    Status : {status}")
    else:
        print("[!] No applications found or failed to fetch.")
    print("=" * 65)


def cmd_deploy(args):
    app_uuid = args.uuid or CONFIG.get("app_uuid")
    if not app_uuid:
        print("[!] Error: No application UUID specified.")
        return
    print(f"[*] Triggering deployment for application [{app_uuid}]...")
    res = api_request(f"/api/v1/deploy?uuid={app_uuid}", method="POST")
    if res:
        print(f"[+] Deployment triggered successfully!")
        if isinstance(res, dict) and "deployment_uuid" in res:
            print(f"    Deployment UUID: {res['deployment_uuid']}")
        print(f"[*] App URL: http://{app_uuid}.92.5.62.107.sslip.io")
    else:
        # Fallback to GET deploy query if POST is not configured
        res_get = api_request(f"/api/v1/deploy?uuid={app_uuid}", method="GET")
        if res_get:
            print(f"[+] Deployment triggered successfully via GET webhook!")
        else:
            print("[!] Deployment trigger returned no response or failed.")


def cmd_server(args):
    print("=" * 65)
    print(" 💻 ORACLE CLOUD ALWAYS FREE HARDWARE TELEMETRY")
    print("=" * 65)
    ssh_cmd = [
        "ssh", "-i", CONFIG["ssh_key"],
        CONFIG["ssh_host"],
        "echo '=== CPU & UPTIME ===' && uptime && echo '' && echo '=== MEMORY ===' && free -h && echo '' && echo '=== DISK STORAGE ===' && df -h / && echo '' && echo '=== ACTIVE CONTAINERS ===' && sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
    ]
    try:
        subprocess.run(ssh_cmd, check=True)
    except Exception as e:
        print(f"[!] SSH Error: {e}")
    print("=" * 65)


def cmd_logs(args):
    lines = args.lines or 50
    print(f"[*] Fetching last {lines} log lines from AutoBI container...")
    ssh_cmd = [
        "ssh", "-i", CONFIG["ssh_key"],
        CONFIG["ssh_host"],
        f"sudo docker logs --tail {lines} $(sudo docker ps -q --filter name=xdsdvywwzbh80firse12wyem)"
    ]
    try:
        subprocess.run(ssh_cmd, check=True)
    except Exception as e:
        print(f"[!] Failed to fetch logs: {e}")


def main():
    parser = argparse.ArgumentParser(description="Antigravity Coolify Controller (coolctl)")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status
    subparsers.add_parser("status", help="Show Coolify version, applications and status")

    # Deploy
    deploy_parser = subparsers.add_parser("deploy", help="Deploy or re-build application")
    deploy_parser.add_argument("--uuid", help="Application UUID (defaults to AutoBI)", default=None)

    # Server
    subparsers.add_parser("server", help="Show real-time server hardware metrics (CPU, RAM, Disk)")

    # Logs
    logs_parser = subparsers.add_parser("logs", help="Stream container logs")
    logs_parser.add_argument("-n", "--lines", type=int, default=50, help="Number of lines to show")

    args = parser.parse_args()
    if not args.command or args.command == "status":
        cmd_status(args)
    elif args.command == "deploy":
        cmd_deploy(args)
    elif args.command == "server":
        cmd_server(args)
    elif args.command == "logs":
        cmd_logs(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

