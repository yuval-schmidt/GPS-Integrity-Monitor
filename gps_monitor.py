import socket
import math
import requests
import ipaddress
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string
import threading

# הגדרות חיבור
UDP_IP = "0.0.0.0"
UDP_PORT = 5000

# משתנה לשמירת נקודה קודמת
last_local = None

latest_analysis = {
    "final_score": 0,
    "penalties": {},
    "ip": "",
    "peak_score": 0,
    "lowest_score": 100
}


def get_dist(lat1, lon1, lat2, lon2):
    """ חישוב מרחק אווירי במטרים """
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    
    a = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c * 1000

def get_net_info(ip):
    """ בדיקת מיקום לפי IP """
    if ipaddress.ip_address(ip).is_private:
        return "local"
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=2)
        res = r.json()
        if res['status'] == 'success':
            return res
    except:
        pass
    return None

def parse_line(line):
    """ פירוק משפט ה-GNGGA """
    if not line.startswith("$GNGGA"):
        return None
    
    parts = line.split(',')
    if len(parts) < 10 or parts[6] == '0':
        return None
    
    try:
        # המרה לפורמט עשרוני
        raw_lat = float(parts[2])
        lat = int(raw_lat/100) + (raw_lat%100)/60
        if parts[3] == 'S': lat = -lat
        
        raw_lon = float(parts[4])
        lon = int(raw_lon/100) + (raw_lon%100)/60
        if parts[5] == 'W': lon = -lon
        
        return {
            "time": parts[1],
            "lat": lat, "lon": lon,
            "sats": int(parts[7]), 
            "hdop": float(parts[8]), 
            "alt": float(parts[9]),
            "link": f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
        }
    except:
        return None

def get_trust_score(curr, last, ip):
    score = 100.0
    penalties = {
        "time": 0,
        "satellites": 0,
        "hdop": 0,
        "jump": 0,
        "ip": 0
    }

    # Timestamp
    try:
        gps_h = int(curr['time'][0:2])
        gps_m = int(curr['time'][2:4])
        gps_s = int(curr['time'][4:6])

        now = datetime.now(timezone.utc)
        gps_total = gps_h * 3600 + gps_m * 60 + gps_s
        now_total = now.hour * 3600 + now.minute * 60 + now.second

        delta = abs(now_total - gps_total)
        delta = min(delta, 86400 - delta)

        if delta > 15:
            penalties["time"] = -40
            score += penalties["time"]
    except:
        pass

    # Satellites
    if curr['sats'] < 10:
        penalties["satellites"] = -(10 - curr['sats']) * 4
        score += penalties["satellites"]

    # HDOP
    if curr['hdop'] > 1.5:
        penalties["hdop"] = -(curr['hdop'] - 1.5) * 12
        score += penalties["hdop"]

    # Jump
    if last:
        d = get_dist(last['lat'], last['lon'], curr['lat'], curr['lon'])
        if d > 45:
            penalties["jump"] = -60
            score += penalties["jump"]

    # IP
    net = get_net_info(ip)
    if net and net != "local":
        dist_ip = get_dist(curr['lat'], curr['lon'], net['lat'], net['lon']) / 1000
        if dist_ip > 120:
            penalties["ip"] = -35
            score += penalties["ip"]

    score = max(0, min(100, score))

    return {
        "final_score": int(score),
        "penalties": penalties
    }

def main():
    global last_local
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Server listening on port {UDP_PORT}...")
    
    while True:
        raw_data, addr = sock.recvfrom(1024)
        ip = addr[0]
        text = raw_data.decode('utf-8').strip()
        
        if text.startswith("$GNGGA"):
            gps = parse_line(text)
            if gps:
                analysis = get_trust_score(gps, last_local, ip)
                trust = analysis["final_score"]

                latest_analysis["final_score"] = trust
                latest_analysis["penalties"] = analysis["penalties"]
                latest_analysis["ip"] = ip

                # עדכון Peak ו-Lowest
                if trust > latest_analysis["peak_score"]:
                    latest_analysis["peak_score"] = trust

                if trust < latest_analysis["lowest_score"]:
                    latest_analysis["lowest_score"] = trust

                last_local = gps
                
                print(f"\n--- Update from {ip} ---")
                print(f"Trust: {trust}% | Sats: {gps['sats']} | HDOP: {gps['hdop']}")
                print(f"Google Maps: {gps['link']}")
                print(f"Peak: {latest_analysis['peak_score']}% | Lowest: {latest_analysis['lowest_score']}%")

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>GPS Integrity Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body {
    background-color: #0f172a;
    color: #00f5ff;
    font-family: Arial;
    text-align: center;
}
h1 {
    margin-top: 20px;
    letter-spacing: 2px;
}
canvas {
    margin-top: 30px;
    box-shadow: 0 0 20px #00f5ff;
    border-radius: 10px;
}
#scoreText {
    font-size: 28px;
    margin-top: 10px;
}
#statsText {
    color: #38bdf8;
    margin-top: 5px;
    font-size: 18px;
}
#ipText {
    margin-top: 15px;
    color: #94a3b8;
    font-size: 14px;
}
</style>
</head>
<body>

<h1>GPS Integrity Monitor</h1>
<h2 id="scoreText">Trust Score: 0%</h2>
<h3 id="statsText">Peak: 0% | Lowest: 0%</h3>
<p id="ipText">Source IP: -</p>

<canvas id="gaugeChart" width="300" height="300"></canvas>
<canvas id="barChart" width="600" height="300"></canvas>

<script>
const gaugeCtx = document.getElementById('gaugeChart');
const barCtx = document.getElementById('barChart');

let gaugeChart = new Chart(gaugeCtx, {
    type: 'doughnut',
    data: {
        labels: ['Score', 'Remaining'],
        datasets: [{
            data: [0, 100],
            backgroundColor: ['#00ff99', '#1e293b'],
            borderWidth: 0
        }]
    },
    options: {
        rotation: -90,
        circumference: 180,
        cutout: '70%',
        plugins: { legend: { display: false } }
    }
});

let barChart = new Chart(barCtx, {
    type: 'bar',
    data: {
        labels: [],
        datasets: [{
            label: 'Penalty Impact',
            data: [],
            backgroundColor: '#ff006e'
        }]
    },
    options: {
        scales: {
            y: { 
                beginAtZero: true,
                ticks: { color: '#00f5ff' }
            },
            x: {
                ticks: { color: '#00f5ff' }
            }
        },
        plugins: {
            legend: {
                labels: { color: '#00f5ff' }
            }
        }
    }
});

async function fetchData() {
    const res = await fetch('/data');
    const data = await res.json();

    document.getElementById("scoreText").innerText =
        "Trust Score: " + data.final_score + "%";

    document.getElementById("statsText").innerText =
        "Peak: " + data.peak_score + "% | Lowest: " + data.lowest_score + "%";

    document.getElementById("ipText").innerText =
        "Source IP: " + data.ip;

    // צבע דינמי למחוג
    let color = "#00ff99";
    if (data.final_score < 50) {
        color = "#ff0040";
    } else if (data.final_score < 80) {
        color = "#ffaa00";
    }

    gaugeChart.data.datasets[0].backgroundColor[0] = color;
    gaugeChart.data.datasets[0].data = [data.final_score, 100 - data.final_score];
    gaugeChart.update();

    barChart.data.labels = Object.keys(data.penalties);
    barChart.data.datasets[0].data =
        Object.values(data.penalties).map(x => Math.abs(x));
    barChart.update();
}

setInterval(fetchData, 2000);
</script>

</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route("/data")
def data():
    return jsonify(latest_analysis)

def run_dashboard():
    # הוספנו use_reloader=False כדי למנוע כפילויות של התוכנית
    app.run(host="0.0.0.0", port=8080, use_reloader=False)

if __name__ == "__main__":
    # אנחנו מפעילים את שרת ה-Web (Flask) ברקע (Daemon)
    web_thread = threading.Thread(target=run_dashboard, daemon=True)
    web_thread.start()
    
    # הלולאה הראשית של ה-UDP רצה ב-Main Thread.
    # זה מבטיח שהיא תקבל את המידע מהטלפון ללא הפרעות.
    try:
        main() 
    except KeyboardInterrupt:
        print("\nסוגר את השרת...")