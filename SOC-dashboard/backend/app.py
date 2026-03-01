from flask import Flask, jsonify, request
from flask_cors import CORS
import boto3, json, time
from datetime import datetime
from collections import defaultdict, Counter

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────
# ⚙️  CONFIGURE THESE TWO LINES
# ─────────────────────────────────────────
AWS_REGION      = "ap-south-1"
LOG_GROUP_NAME  = "aws-waf-logs-threshholdACL"   # ← paste your log group name here
# ─────────────────────────────────────────

cw = boto3.client("logs", region_name=AWS_REGION)

# ── helpers ──────────────────────────────────────────────────────────────────

def run_query(hours: int, extra_filter: str = "") -> list[dict]:
    """Run a CloudWatch Insights query and return parsed log dicts."""
    end   = int(time.time() * 1000)
    start = end - hours * 3_600_000

    qs = f"""
    fields @timestamp, @message
    | filter ispresent(@message)
    {extra_filter}
    | sort @timestamp desc
    | limit 10000
    """
    resp     = cw.start_query(logGroupName=LOG_GROUP_NAME,
                               startTime=start, endTime=end, queryString=qs)
    query_id = resp["queryId"]

    while True:
        r = cw.get_query_results(queryId=query_id)
        if r["status"] == "Complete":
            break
        time.sleep(0.5)

    logs = []
    for record in r["results"]:
        msg = next((f["value"] for f in record if f["field"] == "@message"), None)
        if msg:
            try:
                logs.append(json.loads(msg))
            except Exception:
                pass
    return logs


def flatten(log: dict) -> dict:
    """Pull the fields we care about to the top level."""
    req = log.get("httpRequest", {})
    headers = {h["name"].lower(): h["value"] for h in req.get("headers", [])}
    rate_rules = log.get("rateBasedRuleList", [])
    return {
        "timestamp"    : log.get("timestamp", 0),
        "action"       : log.get("action", "ALLOW"),
        "clientIp"     : req.get("clientIp", "Unknown"),
        "country"      : req.get("country", "Unknown"),
        "uri"          : req.get("uri", "/"),
        "method"       : req.get("httpMethod", "GET"),
        "userAgent"    : headers.get("user-agent", "Unknown"),
        "terminatingRule": log.get("terminatingRuleId", "Default_Action"),
        "isRateLimited": len(rate_rules) > 0,
        "rateRules"    : rate_rules,
    }


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


@app.route("/api/stats")
def stats():
    hours = int(request.args.get("hours", 24))
    raw   = run_query(hours)
    logs  = [flatten(l) for l in raw]

    total    = len(logs)
    blocked  = sum(1 for l in logs if l["action"] == "BLOCK")
    allowed  = total - blocked
    rate_lim = sum(1 for l in logs if l["isRateLimited"])
    uniq_ips = len({l["clientIp"] for l in logs})
    uniq_cc  = len({l["country"]  for l in logs})

    return jsonify({
        "totalRequests"   : total,
        "blocked"         : blocked,
        "allowed"         : allowed,
        "rateLimited"     : rate_lim,
        "uniqueIps"       : uniq_ips,
        "uniqueCountries" : uniq_cc,
        "blockRate"       : round(blocked / total * 100, 1) if total else 0,
    })


@app.route("/api/timeline")
def timeline():
    hours    = int(request.args.get("hours", 24))
    interval = int(request.args.get("interval", 60))   # minutes
    raw      = run_query(hours)
    logs     = [flatten(l) for l in raw]

    buckets: dict = defaultdict(lambda: {"total": 0, "blocked": 0, "allowed": 0})
    for l in logs:
        dt      = datetime.utcfromtimestamp(l["timestamp"] / 1000)
        minute  = (dt.minute // interval) * interval
        key     = dt.replace(minute=minute, second=0, microsecond=0).strftime("%H:%M")
        buckets[key]["total"]   += 1
        buckets[key]["blocked" if l["action"] == "BLOCK" else "allowed"] += 1

    return jsonify([{"time": k, **v} for k, v in sorted(buckets.items())])


@app.route("/api/top-ips")
def top_ips():
    hours  = int(request.args.get("hours", 24))
    limit  = int(request.args.get("limit", 10))
    raw    = run_query(hours)
    logs   = [flatten(l) for l in raw]

    counts = Counter(l["clientIp"] for l in logs)
    result = []
    for ip, cnt in counts.most_common(limit):
        ip_logs = [l for l in logs if l["clientIp"] == ip]
        blocked = sum(1 for l in ip_logs if l["action"] == "BLOCK")
        result.append({
            "ip"        : ip,
            "count"     : cnt,
            "blocked"   : blocked,
            "allowed"   : cnt - blocked,
            "country"   : ip_logs[0]["country"],
            "blockRate" : round(blocked / cnt * 100, 1),
        })
    return jsonify(result)


@app.route("/api/countries")
def countries():
    hours = int(request.args.get("hours", 24))
    raw   = run_query(hours)
    logs  = [flatten(l) for l in raw]

    buckets: dict = defaultdict(lambda: {"total": 0, "blocked": 0, "allowed": 0})
    for l in logs:
        cc = l["country"]
        buckets[cc]["total"] += 1
        buckets[cc]["blocked" if l["action"] == "BLOCK" else "allowed"] += 1

    result = [{"country": k, **v,
               "blockRate": round(v["blocked"] / v["total"] * 100, 1)}
              for k, v in buckets.items()]
    result.sort(key=lambda x: x["total"], reverse=True)
    return jsonify(result)


@app.route("/api/recent")
def recent():
    hours = int(request.args.get("hours", 1))
    limit = int(request.args.get("limit", 40))
    raw   = run_query(hours)
    logs  = [flatten(l) for l in raw]
    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify(logs[:limit])


@app.route("/api/rate-limited")
def rate_limited():
    hours = int(request.args.get("hours", 1))
    raw   = run_query(hours)
    logs  = [flatten(l) for l in raw if len(l.get("rateBasedRuleList", [])) > 0
             if isinstance(l, dict)]

    seen: dict = {}
    for l in [flatten(x) for x in raw if x.get("rateBasedRuleList")]:
        ip = l["clientIp"]
        rule = l["rateRules"][0] if l["rateRules"] else {}
        if ip not in seen:
            seen[ip] = {
                "ip"             : ip,
                "country"        : l["country"],
                "ruleName"       : rule.get("rateBasedRuleName", "Unknown"),
                "maxRate"        : rule.get("maxRateAllowed", 0),
                "evalWindow"     : rule.get("evaluationWindowSec", 300),
                "lastSeen"       : l["timestamp"],
                "triggerCount"   : 1,
            }
        else:
            seen[ip]["triggerCount"] += 1
            seen[ip]["lastSeen"] = max(seen[ip]["lastSeen"], l["timestamp"])

    now = int(time.time() * 1000)
    result = []
    for d in seen.values():
        elapsed   = (now - d["lastSeen"]) / 1000
        remaining = max(0, d["evalWindow"] - elapsed)
        d["timeRemaining"] = int(remaining)
        d["active"]        = remaining > 0
        result.append(d)

    result.sort(key=lambda x: x["lastSeen"], reverse=True)
    return jsonify(result)


@app.route("/api/uri-stats")
def uri_stats():
    hours = int(request.args.get("hours", 24))
    raw   = run_query(hours)
    logs  = [flatten(l) for l in raw]
    counts = Counter(l["uri"] for l in logs)
    return jsonify([{"uri": k, "count": v} for k, v in counts.most_common(10)])


@app.route("/api/useragents")
def useragents():
    hours  = int(request.args.get("hours", 24))
    raw    = run_query(hours)
    logs   = [flatten(l) for l in raw]
    scanners = ["shodan", "censys", "nmap", "nikto", "sqlmap",
                "masscan", "palo alto", "scanner", "zgrab", "xpanse"]
    result = []
    for ua, cnt in Counter(l["userAgent"] for l in logs).most_common(15):
        label = "scanner" if any(s in ua.lower() for s in scanners) else "other"
        result.append({"ua": ua[:80], "count": cnt, "type": label})
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
