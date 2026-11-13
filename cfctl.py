#!/usr/bin/env python3
"""
cfctl.py - Antigravity Cloudflare CLI Controller
Manages Cloudflare zones, DNS records, email DNS/routing, and SSL/TLS settings
directly from the IDE terminal and agentic workflows with zero third-party dependencies.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

API_BASE = "https://api.cloudflare.com/client/v4"

# Default target configuration for AutoBI on Coolify + Eskiz Mail
AUTOBI_COOLIFY_IP = "92.5.62.107"
AUTOBI_ESKIZ_IP = "45.138.159.4"

AUTOBI_DESIRED_RECORDS = [
    {"type": "A", "name": "autobi.uz", "content": AUTOBI_COOLIFY_IP, "proxied": True, "ttl": 1},
    {"type": "CNAME", "name": "www.autobi.uz", "content": "autobi.uz", "proxied": True, "ttl": 1},
    {"type": "A", "name": "ftp.autobi.uz", "content": AUTOBI_ESKIZ_IP, "proxied": False, "ttl": 14400},
    {"type": "A", "name": "webmail.autobi.uz", "content": AUTOBI_ESKIZ_IP, "proxied": False, "ttl": 14400},
    {"type": "A", "name": "mail.autobi.uz", "content": AUTOBI_ESKIZ_IP, "proxied": False, "ttl": 3600},
    {"type": "MX", "name": "autobi.uz", "content": "mail.autobi.uz", "priority": 10, "ttl": 3600},
    {"type": "TXT", "name": "autobi.uz", "content": f"v=spf1 +a +mx +ipv4:{AUTOBI_ESKIZ_IP} ~all", "ttl": 3600},
    {"type": "TXT", "name": "_dmarc.autobi.uz", "content": "v=DMARC1; p=none;", "ttl": 3600},
]


def load_cf_config() -> Dict[str, str]:
    """Load Cloudflare credentials from env files and process environment."""
    cfg = {
        "api_token": "",
        "api_key": "",
        "email": "",
        "account_id": "",
        "zone_id": "",
    }
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.expanduser("~/.cloudflare.env"),
        os.path.join(base_dir, ".coolify.env"),
        os.path.join(base_dir, ".cloudflare.env"),
        os.path.join(base_dir, ".env"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    key = k.strip().upper()
                    val = v.strip().strip('"').strip("'")
                    if key in ("CF_API_TOKEN", "CLOUDFLARE_API_TOKEN"):
                        cfg["api_token"] = val
                    elif key in ("CF_API_KEY", "CLOUDFLARE_API_KEY"):
                        cfg["api_key"] = val
                    elif key in ("CF_API_EMAIL", "CLOUDFLARE_EMAIL", "CF_EMAIL"):
                        cfg["email"] = val
                    elif key in ("CF_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID"):
                        cfg["account_id"] = val
                    elif key in ("CF_ZONE_ID", "CLOUDFLARE_ZONE_ID"):
                        cfg["zone_id"] = val

    # Environment variables always take highest priority
    cfg["api_token"] = os.environ.get("CF_API_TOKEN") or os.environ.get("CLOUDFLARE_API_TOKEN") or cfg["api_token"]
    cfg["api_key"] = os.environ.get("CF_API_KEY") or os.environ.get("CLOUDFLARE_API_KEY") or cfg["api_key"]
    cfg["email"] = os.environ.get("CF_API_EMAIL") or os.environ.get("CLOUDFLARE_EMAIL") or cfg["email"]
    cfg["account_id"] = os.environ.get("CF_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_ACCOUNT_ID") or cfg["account_id"]
    cfg["zone_id"] = os.environ.get("CF_ZONE_ID") or os.environ.get("CLOUDFLARE_ZONE_ID") or cfg["zone_id"]
    return cfg


def cf_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    cfg: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Perform an authenticated request to the Cloudflare v4 REST API."""
    cfg = cfg or load_cf_config()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "AutoBI-cfctl/1.0",
    }
    if cfg.get("api_token"):
        headers["Authorization"] = f"Bearer {cfg['api_token']}"
    elif cfg.get("api_key") and cfg.get("email"):
        headers["X-Auth-Key"] = cfg["api_key"]
        headers["X-Auth-Email"] = cfg["email"]
    else:
        raise RuntimeError(
            "Cloudflare credentials not found. Set CF_API_TOKEN in .cloudflare.env (or environment)."
        )

    url = f"{API_BASE}{endpoint}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if not payload.get("success", False):
                errors = payload.get("errors", [])
                raise RuntimeError(f"Cloudflare API error: {errors}")
            return payload
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Cloudflare HTTP {e.code}: {err_body}") from e


def resolve_zone_id(domain: str, cfg: Optional[Dict[str, str]] = None) -> str:
    """Resolve zone ID from a domain name (or return if already a 32-hex ID)."""
    clean = domain.strip().rstrip(".").lower()
    if len(clean) == 32 and all(c in "0123456789abcdef" for c in clean):
        return clean
    q = urllib.parse.urlencode({"name": clean})
    res = cf_request(f"/zones?{q}", cfg=cfg)
    zones = res.get("result", [])
    if not zones:
        raise RuntimeError(f"Zone '{clean}' was not found in this Cloudflare account.")
    return zones[0]["id"]


def normalize_fqdn(name: str, zone_name: str) -> str:
    """Convert '@', short hostnames, or trailing-dot FQDNs into canonical Cloudflare name."""
    n = name.strip().rstrip(".").lower()
    z = zone_name.strip().rstrip(".").lower()
    if n in ("@", "", z):
        return z
    if n.endswith(f".{z}"):
        return n
    return f"{n}.{z}"


def cmd_verify(args):
    cfg = load_cf_config()
    if not cfg.get("api_token") and not (cfg.get("api_key") and cfg.get("email")):
        print("[!] Missing Cloudflare credentials.")
        print("    Add CF_API_TOKEN=<your_token> to .cloudflare.env or set $env:CF_API_TOKEN.")
        sys.exit(1)
    res = cf_request("/user/tokens/verify", cfg=cfg)
    info = res.get("result", {})
    print(f"[+] Cloudflare token status: {info.get('status', 'unknown')} (id={info.get('id', '')})")


def cmd_zones(args):
    res = cf_request("/zones?per_page=50")
    zones = res.get("result", [])
    if not zones:
        print("[*] No zones found.")
        return
    print(f"{'DOMAIN':<24} {'STATUS':<12} {'ZONE ID':<34} {'NAMESERVERS'}")
    print("-" * 100)
    for z in zones:
        ns = ", ".join(z.get("name_servers", []))
        print(f"{z['name']:<24} {z['status']:<12} {z['id']:<34} {ns}")


def cmd_dns_list(args):
    zid = resolve_zone_id(args.domain)
    res = cf_request(f"/zones/{zid}/dns_records?per_page=100")
    records = res.get("result", [])
    print(f"{'TYPE':<7} {'NAME':<28} {'CONTENT':<38} {'PROXY':<7} {'TTL':<7} {'ID'}")
    print("-" * 115)
    for r in records:
        prox = "orange" if r.get("proxied") else "grey"
        ttl = "auto" if r.get("ttl") == 1 else str(r.get("ttl"))
        content = str(r.get("content", ""))
        if r.get("priority") is not None:
            content = f"{r['priority']} {content}"
        print(f"{r['type']:<7} {r['name']:<28} {content[:36]:<38} {prox:<7} {ttl:<7} {r['id']}")


def upsert_dns_record(
    zid: str,
    zone_name: str,
    rec_type: str,
    name: str,
    content: str,
    ttl: int = 1,
    proxied: Optional[bool] = None,
    priority: Optional[int] = None,
    dry_run: bool = False,
) -> str:
    """Create or update a DNS record in Cloudflare by matching type + canonical name."""
    fqdn = normalize_fqdn(name, zone_name)
    rtype = rec_type.upper()

    # For TXT records, match existing records by content prefix if multiple TXT records exist on apex
    q = urllib.parse.urlencode({"type": rtype, "name": fqdn, "per_page": 50})
    existing = cf_request(f"/zones/{zid}/dns_records?{q}").get("result", [])

    target = None
    if rtype == "TXT":
        prefix = content.strip('"').split("=", 1)[0].lower() if "=" in content else content.strip('"')[:12].lower()
        for item in existing:
            if item.get("content", "").strip('"').lower().startswith(prefix):
                target = item
                break
    elif existing:
        target = existing[0]

    payload: Dict[str, Any] = {
        "type": rtype,
        "name": fqdn,
        "content": content.rstrip(".") if rtype in ("CNAME", "MX") else content,
        "ttl": ttl,
    }
    if rtype in ("A", "AAAA", "CNAME") and proxied is not None:
        payload["proxied"] = proxied
    if rtype == "MX" and priority is not None:
        payload["priority"] = priority

    if target:
        if dry_run:
            return f"[DRY-RUN] UPDATE {rtype} {fqdn} -> {payload['content']} (proxied={payload.get('proxied')})"
        cf_request(f"/zones/{zid}/dns_records/{target['id']}", method="PUT", data=payload)
        return f"[UPDATED] {rtype} {fqdn} -> {payload['content']} (proxied={payload.get('proxied')})"
    else:
        if dry_run:
            return f"[DRY-RUN] CREATE {rtype} {fqdn} -> {payload['content']} (proxied={payload.get('proxied')})"
        cf_request(f"/zones/{zid}/dns_records", method="POST", data=payload)
        return f"[CREATED] {rtype} {fqdn} -> {payload['content']} (proxied={payload.get('proxied')})"


def cmd_dns_add(args):
    zid = resolve_zone_id(args.domain)
    zone_name = args.domain.strip().rstrip(".").lower()
    if args.upsert:
        msg = upsert_dns_record(
            zid,
            zone_name,
            args.type,
            args.name,
            args.content,
            ttl=args.ttl,
            proxied=args.proxied if args.type.upper() in ("A", "AAAA", "CNAME") else None,
            priority=args.priority,
        )
        print(msg)
        return

    fqdn = normalize_fqdn(args.name, zone_name)
    rtype = args.type.upper()
    payload: Dict[str, Any] = {
        "type": rtype,
        "name": fqdn,
        "content": args.content.rstrip(".") if rtype in ("CNAME", "MX") else args.content,
        "ttl": args.ttl,
    }
    if rtype in ("A", "AAAA", "CNAME"):
        payload["proxied"] = bool(args.proxied)
    if rtype == "MX" and args.priority is not None:
        payload["priority"] = args.priority
    res = cf_request(f"/zones/{zid}/dns_records", method="POST", data=payload)
    r = res["result"]
    print(f"[+] Created DNS record {r['id']}: {r['type']} {r['name']} -> {r['content']}")


def cmd_dns_delete(args):
    zid = resolve_zone_id(args.domain)
    cf_request(f"/zones/{zid}/dns_records/{args.id}", method="DELETE")
    print(f"[-] Deleted DNS record {args.id} from {args.domain}")


def cmd_ssl(args):
    zid = resolve_zone_id(args.domain)
    if args.action == "get":
        res = cf_request(f"/zones/{zid}/settings/ssl")
        print(f"[*] SSL/TLS mode for {args.domain}: {res['result']['value']}")
    elif args.action == "set":
        res = cf_request(f"/zones/{zid}/settings/ssl", method="PATCH", data={"value": args.mode})
        print(f"[+] Updated SSL/TLS mode for {args.domain} -> {res['result']['value']}")


def cmd_email_status(args):
    zid = resolve_zone_id(args.domain)
    records = cf_request(f"/zones/{zid}/dns_records?per_page=100").get("result", [])
    print(f"=== Email DNS Records for {args.domain} ===")
    for r in records:
        if r["type"] in ("MX", "TXT") or any(k in r["name"] for k in ("mail", "webmail", "dkim", "dmarc")):
            extra = f" (prio={r['priority']})" if r.get("priority") is not None else ""
            prox = "orange" if r.get("proxied") else "grey"
            print(f"  {r['type']:<5} {r['name']:<30} {r['content']}{extra} [{prox}]")

    try:
        routing = cf_request(f"/zones/{zid}/email/routing")
        er = routing.get("result", {})
        print(f"\n=== Cloudflare Email Routing ===")
        print(f"  Enabled: {er.get('enabled', False)} | Status: {er.get('status', 'unknown')}")
    except Exception as e:
        print(f"\n[*] Email Routing status unavailable with current token scope: {e}")


def cmd_setup_autobi(args):
    zid = resolve_zone_id("autobi.uz")
    print("[*] Syncing autobi.uz DNS records to Cloudflare (Coolify @ 92.5.62.107 + Eskiz Mail @ 45.138.159.4)...")
    for rec in AUTOBI_DESIRED_RECORDS:
        msg = upsert_dns_record(
            zid=zid,
            zone_name="autobi.uz",
            rec_type=rec["type"],
            name=rec["name"],
            content=rec["content"],
            ttl=rec.get("ttl", 1),
            proxied=rec.get("proxied"),
            priority=rec.get("priority"),
            dry_run=args.dry_run,
        )
        print(" ", msg)

    if not args.dry_run:
        res = cf_request(f"/zones/{zid}/settings/ssl", method="PATCH", data={"value": "full"})
        print(f"  [SSL] Mode set to '{res['result']['value']}' (prevents Coolify Traefik redirect loop)")
    else:
        print("  [DRY-RUN] SSL mode would be set to 'full'")


def cmd_export_bind(args):
    """Print or write a BIND zone file ready for Cloudflare 'Import DNS records'."""
    lines = [
        "; AutoBI Zone File for Cloudflare Import (autobi.uz)",
        "; Root & www point to Coolify VPS (92.5.62.107). Mail/Webmail/FTP point to Eskiz (45.138.159.4).",
        "$ORIGIN autobi.uz.",
        "$TTL 3600",
        f"@\t3600\tIN\tA\t{AUTOBI_COOLIFY_IP} ; cf_tags=cf-proxied:true",
        "www\t3600\tIN\tCNAME\tautobi.uz. ; cf_tags=cf-proxied:true",
        f"ftp\t14400\tIN\tA\t{AUTOBI_ESKIZ_IP} ; cf_tags=cf-proxied:false",
        f"webmail\t14400\tIN\tA\t{AUTOBI_ESKIZ_IP} ; cf_tags=cf-proxied:false",
        f"mail\t3600\tIN\tA\t{AUTOBI_ESKIZ_IP} ; cf_tags=cf-proxied:false",
        "@\t3600\tIN\tMX\t10 mail.autobi.uz.",
        f"@\t3600\tIN\tTXT\t\"v=spf1 +a +mx +ipv4:{AUTOBI_ESKIZ_IP} ~all\"",
        "_dmarc\t3600\tIN\tTXT\t\"v=DMARC1; p=none;\"",
    ]
    content = "\n".join(lines) + "\n"
    if getattr(args, "out", None):
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[+] Wrote BIND zone file to {args.out}")
    else:
        print(content, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Antigravity Cloudflare CLI Controller (cfctl)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("verify", help="Verify Cloudflare API token")
    sub.add_parser("zones", help="List Cloudflare zones")

    dns_p = sub.add_parser("dns", help="Manage DNS records")
    dns_sub = dns_p.add_subparsers(dest="dns_cmd", required=True)

    p_list = dns_sub.add_parser("list", help="List DNS records for a domain")
    p_list.add_argument("domain")

    p_add = dns_sub.add_parser("add", help="Add or upsert a DNS record")
    p_add.add_argument("domain")
    p_add.add_argument("--type", required=True, help="A, AAAA, CNAME, MX, TXT, SRV, CAA")
    p_add.add_argument("--name", required=True, help="Host (@, www, mail, _dmarc, etc.)")
    p_add.add_argument("--content", required=True, help="Record value / IP / target")
    p_add.add_argument("--ttl", type=int, default=1, help="TTL in seconds (1 = Auto)")
    p_add.add_argument("--proxied", action="store_true", help="Enable Cloudflare orange-cloud proxy")
    p_add.add_argument("--priority", type=int, default=None, help="Priority for MX/SRV")
    p_add.add_argument("--upsert", action="store_true", help="Update existing matching record if present")

    p_del = dns_sub.add_parser("delete", help="Delete a DNS record by ID")
    p_del.add_argument("domain")
    p_del.add_argument("--id", required=True)

    ssl_p = sub.add_parser("ssl", help="Inspect or set SSL/TLS encryption mode")
    ssl_sub = ssl_p.add_subparsers(dest="action", required=True)
    p_ssl_get = ssl_sub.add_parser("get")
    p_ssl_get.add_argument("domain")
    p_ssl_set = ssl_sub.add_parser("set")
    p_ssl_set.add_argument("domain")
    p_ssl_set.add_argument("mode", choices=["off", "flexible", "full", "strict"])

    email_p = sub.add_parser("email", help="Inspect email DNS and Cloudflare Email Routing")
    email_sub = email_p.add_subparsers(dest="email_cmd", required=True)
    p_es = email_sub.add_parser("status")
    p_es.add_argument("domain")

    setup_p = sub.add_parser("setup-autobi", help="Sync all autobi.uz DNS + SSL settings to Cloudflare")
    setup_p.add_argument("--dry-run", action="store_true")

    exp_p = sub.add_parser("export-bind", help="Print or write BIND zone file for Cloudflare dashboard import")
    exp_p.add_argument("--out", default=None, help="Optional output file path (e.g. autobi_uz.zone)")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "verify":
            cmd_verify(args)
        elif args.command == "zones":
            cmd_zones(args)
        elif args.command == "dns":
            if args.dns_cmd == "list":
                cmd_dns_list(args)
            elif args.dns_cmd == "add":
                cmd_dns_add(args)
            elif args.dns_cmd == "delete":
                cmd_dns_delete(args)
        elif args.command == "ssl":
            cmd_ssl(args)
        elif args.command == "email":
            if args.email_cmd == "status":
                cmd_email_status(args)
        elif args.command == "setup-autobi":
            cmd_setup_autobi(args)
        elif args.command == "export-bind":
            cmd_export_bind(args)
    except Exception as exc:
        print(f"[!] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

