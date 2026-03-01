import folium
import json

# ─── CONFIGURATION ───────────────────────────────────────────
LOG_FILE = "/var/log/admin.log"   # Path to your honeypot log file on EC2
OUTPUT   = "attack_map.html"             # Output map file name
# ─────────────────────────────────────────────────────────────

print("Regenerating map...")

m = folium.Map(location=[20, 0], zoom_start=2)

with open(LOG_FILE) as f:
    for line in f:
        try:
            data = json.loads(line[line.index("{"):])
            geo  = data.get("geo", {})
            lat  = geo.get("latitude")
            lon  = geo.get("longitude")

            if lat and lon:
                color = "red" if data["login_status"] == "FAILED" else "green"

                popup = f"""
                    IP: {data['ip']}<br>
                    Country: {geo.get('country')}<br>
                    City: {geo.get('city')}<br>
                    Status: {data['login_status']}
                """

                folium.CircleMarker(
                    location=[float(lat), float(lon)],
                    radius=5,
                    color=color,
                    fill=True,
                    fill_opacity=0.7,
                    popup=popup
                ).add_to(m)

        except Exception:
            continue

m.save(OUTPUT)
print(f"Map saved to {OUTPUT}")

#bind your map on port 8080- run below command
#python3 -m http.server 8080 --bind 0.0.0.0

# Access the map via your Load Balancer:
# http://your-load-balancer-url:8080/attack_map.html
