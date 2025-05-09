#!/usr/bin/env python3
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST

# 1) Create a registry and define a gauge for each expected parameter
PARAMETERS = [
    "indoortempf", "indoorhumidity",
    "tempf", "humidity", "dewptf", "windchillf",
    "absbaromin", "baromin",
    "windspeedmph", "windgustmph", "winddir",
    "windspdmph_avg2m", "winddir_avg2m",
    "windgustmph_10m", "windgustdir_10m",
    "rainin", "dailyrainin", "weeklyrainin", "monthlyrainin",
    "solarradiation", "UV"
]

registry = CollectorRegistry()
gauges = {}
for param in PARAMETERS:
    # sanitize metric name: replace non-alpha with underscore
    metric_name = param.lower()
    gauges[param] = Gauge(f"weather_{metric_name}", f"Weather station metric {param}", registry=registry)

class ExporterHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/metrics":
            # Serve Prometheus metrics
            output = generate_latest(registry)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(output)
        else:
            # Treat any other GET as a data push from the WeatherStation
            self.handle_update(parsed)

    def do_POST(self):
        # also accept POSTs (rare for this URI, but safe)
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        self.handle_update(parsed)

    def handle_update(self, parsed):
        if not parsed.path.endswith("/updateweatherstation.php"):
            self.send_response(404)
            self.end_headers()
            return

        query = parse_qs(parsed.query)
        # Update each gauge if present
        for key, gauge in gauges.items():
            if key in query:
                try:
                    # take the first value and convert to float
                    val = float(query[key][0])
                    gauge.set(val)
                except ValueError:
                    pass  # ignore non-numeric

        # respond so station thinks it succeeded
        self.send_response(200)
        self.end_headers()

    # silence default logging
    def log_message(self, fmt, *args):
        return

def run(port: int):
    server = HTTPServer(('', port), ExporterHandler)
    print(f"🚀  Starting weatherstation exporter on :{port}")
    print("   - data pushes: /weatherstation/updateweatherstation.php?...") 
    print("   - metrics scrape: /metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down…")
        server.server_close()

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Weatherstation → Prometheus exporter")
    p.add_argument("-p", "--port", type=int, default=8080,
                   help="Port to listen on (default: 8080)")
    args = p.parse_args()
    run(args.port)
