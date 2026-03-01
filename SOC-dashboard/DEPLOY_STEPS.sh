# SENTINEL Dashboard — Step-by-Step Deployment
# =============================================
# Run each block exactly as shown.
# Everything marked  LOCAL   → run on your laptop
# Everything marked  EC2     → run after SSH-ing into EC2

# ══════════════════════════════════════════════
# PHASE 1 — UPLOAD FILES TO EC2
# ══════════════════════════════════════════════

# ── [LOCAL] Open a terminal on your laptop ──
# Windows: press Win+R → type "cmd" → Enter
# Mac:     press Cmd+Space → type "terminal" → Enter

# ── [LOCAL] Go to where you downloaded the files ──
cd ~/Downloads                          # Mac/Linux
# cd C:\Users\YourName\Downloads        # Windows

# ── [LOCAL] Upload backend to EC2 ──
# Replace:  my-key.pem  →  your actual .pem key filename
# Replace:  52.66.x.x   →  your EC2 public IP
scp -i my-key.pem -r final-dashboard ubuntu@52.66.x.x:~/

# ── [LOCAL] SSH into EC2 ──
ssh -i my-key.pem ubuntu@52.66.x.x

# ════════════════════════════════════════════════════
# PHASE 2 — BACKEND SETUP  (you are now inside EC2)
# ════════════════════════════════════════════════════

# ── [EC2] Install Python packages ──
cd ~/final-dashboard/backend
pip3 install -r requirements.txt --break-system-packages

# ── [EC2] Find your WAF log group name ──
aws logs describe-log-groups --region ap-south-1 | grep -i waf
# You'll see something like:
#   "logGroupName": "aws-waf-logs-threshholdACL"
# Copy that name exactly!

# ── [EC2] Open app.py and paste your log group name ──
nano app.py
# Find line 12:  LOG_GROUP_NAME  = "aws-waf-logs-threshholdACL"
# Replace the value with YOUR log group name from the step above
# Save: Ctrl+X → Y → Enter

# ── [EC2] Quick test — make sure backend responds ──
python3 app.py &                        # start in background
sleep 3
curl http://localhost:8080/api/health   # should return {"status":"ok",...}
curl http://localhost:8080/api/stats    # should return JSON with numbers
kill %1                                 # stop test server

# ── [EC2] Create systemd service so backend runs forever ──
sudo tee /etc/systemd/system/sentinel.service > /dev/null <<'EOF'
[Unit]
Description=Sentinel WAF Dashboard Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/final-dashboard/backend
ExecStart=/usr/bin/python3 /home/ubuntu/final-dashboard/backend/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# ── [EC2] Start the service ──
sudo systemctl daemon-reload
sudo systemctl enable sentinel
sudo systemctl start sentinel

# ── [EC2] Verify it's running ──
sudo systemctl status sentinel
# You should see:  Active: active (running)

# ── [EC2] Get your EC2 public IP (you'll need this next) ──
curl -s http://169.254.169.254/latest/meta-data/public-ipv4
# Copy the IP it prints — e.g.  52.66.188.27

# ════════════════════════════════════════════════════
# PHASE 3 — UPDATE FRONTEND WITH YOUR EC2 IP
# ════════════════════════════════════════════════════

# ── [EC2] Open the dashboard HTML and set your EC2 IP ──
nano ~/final-dashboard/frontend/index.html
# Press Ctrl+W to search, type:  YOUR_EC2_IP  → press Enter
# Replace:  http://YOUR_EC2_IP:8080
# With:     http://52.66.188.27:8080  (your actual IP)
# Save: Ctrl+X → Y → Enter

# ════════════════════════════════════════════════════
# PHASE 4 — DEPLOY FRONTEND TO S3
# ════════════════════════════════════════════════════

# ── [EC2] Create an S3 bucket ──
# Change "sentinel-dashboard-2026" to any unique name (lowercase only)
BUCKET=sentinel-dashboard-2026
aws s3 mb s3://$BUCKET --region ap-south-1

# ── [EC2] Upload the dashboard ──
aws s3 cp ~/final-dashboard/frontend/index.html s3://$BUCKET/index.html

# ── [EC2] Enable static website hosting ──
aws s3 website s3://$BUCKET/ --index-document index.html

# ── [EC2] Make the bucket publicly readable ──
aws s3api put-bucket-ownership-controls \
  --bucket $BUCKET \
  --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerPreferred}]'

aws s3api put-public-access-block \
  --bucket $BUCKET \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

aws s3api put-bucket-policy --bucket $BUCKET --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [{
    \"Sid\": \"PublicRead\",
    \"Effect\": \"Allow\",
    \"Principal\": \"*\",
    \"Action\": \"s3:GetObject\",
    \"Resource\": \"arn:aws:s3:::$BUCKET/*\"
  }]
}"

# ── [EC2] Print your dashboard URL ──
echo "Your dashboard is live at:"
echo "http://$BUCKET.s3-website.ap-south-1.amazonaws.com"

# ════════════════════════════════════════════════════
# PHASE 5 — OPEN PORT 8080 ON EC2 (AWS Console)
# ════════════════════════════════════════════════════
# 1. Go to AWS Console → EC2 → Security Groups
# 2. Click the security group attached to your EC2
# 3. Click "Edit inbound rules"
# 4. Click "Add rule"
#    Type:   Custom TCP
#    Port:   8080
#    Source: 0.0.0.0/0
# 5. Click "Save rules"

# ════════════════════════════════════════════════════
# PHASE 6 — OPEN DASHBOARD IN BROWSER
# ════════════════════════════════════════════════════
# Open this URL in your browser:
# http://sentinel-dashboard-2026.s3-website.ap-south-1.amazonaws.com
# (use the URL printed in Phase 4)

# ════════════════════════════════════════════════════
# TROUBLESHOOTING
# ════════════════════════════════════════════════════

# Dashboard shows "—" everywhere:
sudo journalctl -u sentinel -n 50        # read backend logs
curl http://localhost:8080/api/stats     # test backend directly

# Wrong log group name:
aws logs describe-log-groups --region ap-south-1
nano ~/final-dashboard/backend/app.py   # fix LOG_GROUP_NAME
sudo systemctl restart sentinel

# S3 bucket says "Access Denied":
# → Redo the public-access-block and bucket-policy steps above

# Restart backend anytime:
sudo systemctl restart sentinel

# Watch live backend logs:
sudo journalctl -u sentinel -f

# Re-upload frontend after changes:
aws s3 cp ~/final-dashboard/frontend/index.html s3://$BUCKET/index.html
