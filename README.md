# 🛡️ SOC Dashboard — AWS Automated Attack Detection & Alerting

A real-time **Security Operations Center (SOC) Dashboard** built on AWS.  
When someone brute-forces the admin login page, the system **automatically detects, blocks, geolocates, and emails an alert** — in under 30 seconds. Zero manual work.

**Live domain:** `your-domain.com`  
**Dashboard:** hosted on S3 static website  
**Attack map:** `http://your-load-balancer-url:8080/attack_map.html`

---

## 📐 Architecture Overview

```
Attacker
   │
   ▼
Route 53 (DNS)
   │
   ▼
Application Load Balancer (ALB)
   │
   ├──► WAF (blocks IP after 10 req/5min)
   │         │
   │         ▼
   │    CloudWatch (WAF logs)
   │         │
   │         ▼
   │    SOC Dashboard (reads WAF logs live)
   │
   ├──► EC2 (admin.py + map.py)
   │         │
   │         ▼
   │    CloudWatch Agent (streams admin.py login logs)
   │
   └──► S3 Bucket — ALB Logs (every 5 min)
              │
              ▼ (S3 trigger)
           Lambda
              │
              ├── reads S3 LB logs → finds HTTP 403 blocked IPs
              └── reads CloudWatch admin.py logs → extracts geolocation
                        │
                        ▼
                   DynamoDB (300s double-check — no duplicate alerts)
                        │
                        ▼
                      SNS → Email Alert to Admin
```

---

## ⚙️ AWS Services Used

| Service | Purpose |
|---|---|
| **Route 53** | DNS — resolves domain to ALB |
| **Application Load Balancer (ALB)** | Entry point, listens on ports 80 / 8080 / 5000 |
| **WAF (Web Application Firewall)** | Rate limiting — blocks IPs after 10 req/5min |
| **EC2** | Runs `admin.py` (login portal) and `map.py` (geo attack map) |
| **CloudWatch** | Stores WAF logs + admin.py login attempt logs via CloudWatch Agent |
| **S3** | Stores ALB access logs every 5 min + hosts SOC Dashboard static site |
| **Lambda** | Triggered by S3, scans for 403s, extracts geo, sends alerts |
| **DynamoDB** | Prevents duplicate alerts — 300 second suppression window per IP |
| **SNS** | Sends email alert to admin with IP, country, state, city |

---

## 📁 File Structure

```
soc-dashboard/
├── admin.py              # Login portal (runs on EC2, port 80)
├── map.py                # Geo attack map generator (runs on EC2, port 8080)
├── lambda_function.py    # Lambda — processes S3 + CloudWatch logs, sends SNS alert
├── soc-dashboard.html    # SOC Dashboard frontend (hosted on S3)
└── README.md
```

---

## 🚀 How It Works — Step by Step

### 1. Attack Detection
- Attacker hits `your-domain.com` login page and tries multiple passwords
- **WAF rule:** if same IP sends **10+ requests in 5 minutes** → block for 5 minutes
- **ALB returns HTTP 403 Forbidden** to the attacker

### 2. Real-Time Visibility (Flow 1)
- WAF logs every block event to **CloudWatch**
- **SOC Dashboard** reads these CloudWatch WAF logs live
- Dashboard updates in real time — blocked IPs, rules triggered, timestamps

### 3. Automated Alerting (Flow 2)
- ALB writes access logs to **S3** every 5 minutes
- New log file → **triggers Lambda automatically**
- Lambda scans S3 logs for **HTTP 403 entries** to find blocked IPs
- Lambda also reads **CloudWatch admin.py logs** to extract geolocation (country, state, city)
- Lambda checks **DynamoDB** — was this IP alerted in last 300 seconds?
  - If yes → skip (no duplicate email)
  - If no → write to DynamoDB, fire SNS alert
- **SNS sends email** to admin with full details

---

## 📧 Alert Email Format

```
🚨 Security Alert

Blocked IP detected!

IP Address:  45.33.32.156
Country:     United States
State:       New York
City:        New York City

You will not receive another alert for this IP for 300 seconds.
```

---

## 🔐 IAM Permissions

### Lambda Execution Role
The Lambda function needs an IAM role with the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::your-alb-log-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:FilterLogEvents",
        "logs:GetLogEvents",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:your-region:your-account-id:log-group:your-log-group-name:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem"
      ],
      "Resource": "arn:aws:dynamodb:your-region:your-account-id:table/BlockedIPCache"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:your-region:your-account-id:your-sns-topic-name"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### EC2 CloudWatch Agent Role
The EC2 instance needs this policy attached to push logs to CloudWatch:

```
CloudWatchAgentServerPolicy   (AWS Managed Policy)
```

---

## 🗄️ DynamoDB Table Setup

| Setting | Value |
|---|---|
| Table Name | `BlockedIPCache` |
| Partition Key | `ip` (String) |
| TTL Attribute | `expires_at` (auto-deletes records after 300s) |
| Billing Mode | On-Demand |

---

## 📬 SNS Setup

1. Go to **SNS → Topics → Create Topic**
2. Type: **Standard**
3. Name: `your-sns-topic-name`
4. Create a **Subscription**:
   - Protocol: **Email**
   - Endpoint: `your-email@example.com`
5. Confirm the subscription from your inbox
6. Copy the **Topic ARN** and paste it into `lambda_function.py`

---

## 🪣 S3 — Enable ALB Access Logs

1. Go to **EC2 → Load Balancers → your ALB → Attributes**
2. Enable **Access logs**
3. Set S3 bucket: `your-alb-log-bucket`
4. Set prefix: `alb-logs/` (optional)
5. Add this **bucket policy** to allow ALB to write:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::your-region-elb-account-id:root"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::your-alb-log-bucket/*"
    }
  ]
}
```

> **Note:** Replace `your-region-elb-account-id` with the ELB account ID for your region.  
> Full list: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/enable-access-logging.html

---

## 🔧 Lambda Configuration

| Setting | Value |
|---|---|
| Runtime | Python 3.12 |
| Trigger | S3 — `your-alb-log-bucket` (all object create events) |
| Memory | 128 MB |
| Timeout | 30 seconds |
| Environment Variables | Set `SNS_TOPIC_ARN`, `DDB_TABLE` here instead of hardcoding |

---

## 🌍 Attack Map (map.py)

The attack map reads from `/var/log/web_honeypot.log` and generates an interactive **Folium map** showing:

- 🔴 Red markers — failed login attempts
- 🟢 Green markers — successful logins
- Popup on each marker: IP, Country, City, Status

Map is saved as `attack_map.html` and served by EC2 on **port 8080** via the Load Balancer.

```
http://your-load-balancer-url:8080/attack_map.html
```

---

## 🛡️ WAF Rule Summary

| Rule | Value |
|---|---|
| Type | Rate-based rule |
| Threshold | 10 requests per 5 minutes |
| Action | Block |
| Block Duration | 5 minutes |
| Scope | Attached to ALB |

---

## 📋 Setup Checklist

- [ ] Launch EC2, install `admin.py` and `map.py`
- [ ] Install and configure **CloudWatch Agent** on EC2
- [ ] Create **ALB** with target group pointing to EC2
- [ ] Attach **WAF** to ALB with rate-based rule
- [ ] Enable **ALB access logs** → S3 bucket
- [ ] Create **DynamoDB** table `BlockedIPCache` with TTL enabled
- [ ] Create **SNS topic** and confirm email subscription
- [ ] Deploy **Lambda** with S3 trigger and correct IAM role
- [ ] Upload `soc-dashboard.html` to **S3 static website bucket**
- [ ] Test — visit your domain and trigger 10+ requests to verify full flow

---

## 🔗 LinkedIn Post

> Built a fully automated SOC Dashboard on AWS that detects brute-force attacks and emails me the attacker's location in under 30 seconds.
>
> Full walkthrough + code on GitHub → [your-github-link]

---

## 📜 License

MIT License — free to use, modify, and deploy.
