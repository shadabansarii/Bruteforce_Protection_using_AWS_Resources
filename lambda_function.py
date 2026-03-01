import gzip
import json
import base64
import boto3
import urllib.parse
import time

# AWS Clients
sns      = boto3.client('sns')
s3       = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# ─── CONFIGURATION ───────────────────────────────────────────
# Replace these with your own values before deploying
SNS_TOPIC_ARN        = "arn:aws:sns:your-region:your-account-id:your-sns-topic-name"
DDB_TABLE            = "BlockedIPCache"
BLOCK_WINDOW_SECONDS = 300   # 300 second suppression per IP (no duplicate alerts)
# ─────────────────────────────────────────────────────────────

table = dynamodb.Table(DDB_TABLE)


def lambda_handler(event, context):

    # ===== Trigger 1: S3 (ALB access logs every 5 min) =====
    if "Records" in event:
        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key    = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

            response = s3.get_object(Bucket=bucket, Key=key)
            content  = gzip.decompress(response["Body"].read()).decode("utf-8")

            for line in content.splitlines():
                process_s3_log(line)

    # ===== Trigger 2: CloudWatch Logs (admin.py login logs) =====
    elif "awslogs" in event:
        compressed_payload   = base64.b64decode(event['awslogs']['data'])
        uncompressed_payload = gzip.decompress(compressed_payload)
        log_data             = json.loads(uncompressed_payload)

        for log_event in log_data['logEvents']:
            process_cloudwatch_log(log_event['message'])

    return {
        "statusCode": 200,
        "body": "Processing complete"
    }


def process_s3_log(line):
    parts = line.split()
    if len(parts) > 8 and parts[8] == "403":
        ip = parts[3].split(":")[0]
        handle_blocked_ip(ip, "Unknown", "Unknown", "Unknown")


def process_cloudwatch_log(message):
    try:
        json_start = message.find("{")
        if json_start == -1:
            return
        log_json  = json.loads(message[json_start:])
        ip        = log_json.get("ip")
        geo       = log_json.get("geo", {})
        ip_status = log_json.get("ip_status", "")
        if ip and ip_status == "BLOCKED":
            handle_blocked_ip(
                ip,
                geo.get("country", "Unknown"),
                geo.get("state",   "Unknown"),
                geo.get("city",    "Unknown")
            )
    except Exception as e:
        print("CloudWatch parse error:", e)


def handle_blocked_ip(ip, country, state, city):
    if country == "Unknown" and state == "Unknown" and city == "Unknown":
        print(f"{ip} geo unknown — skipping SNS")
        return

    now = int(time.time())

    try:
        response = table.get_item(Key={"ip": ip})
    except Exception as e:
        print("DynamoDB read error:", e)
        return

    if "Item" in response:
        last_alert = response["Item"].get("last_alert", 0)
        if now - last_alert < BLOCK_WINDOW_SECONDS:
            print(f"{ip} inside 300s window — skipping SNS")
            return

    try:
        table.put_item(Item={"ip": ip, "last_alert": now, "expires_at": now + 300})
    except Exception as e:
        print("DynamoDB write error:", e)
        return

    send_alert(ip, country, state, city)


def send_alert(ip, country, state, city):
    message = f"""
🚨 Security Alert

Blocked IP detected!

IP Address: {ip}
Country: {country}
State: {state}
City: {city}


"""
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject="Security Alert - Blocked IP", Message=message)
        print(f"SNS alert sent for {ip}")
    except Exception as e:
        print("SNS error:", e)
