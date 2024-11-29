import time
import numpy as np
from flask import Flask, Response, render_template
import threading
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
import cflib.crtp  # Crazyflie drivers

# Initialize Flask App
app = Flask(__name__)

# Global variables
frequencies = np.linspace(2400, 2480, 1024)  # Frequency range for spectrum (in MHz)
spectrum = np.zeros(1024)  # Placeholder for spectrum data
URI = "radio://0/80/2M/E7E7E7E7F2"
lock = threading.Lock()  # Thread lock for spectrum data

# Callback function for RSSI logging
def log_rssi_callback(timestamp, data, logconf):
    global spectrum
    rssi = data["radio.rssi"]

    # Update spectrum with new RSSI data
    with lock:
        spectrum = np.roll(spectrum, -1)  # Shift spectrum data
        spectrum[-1] = max(-140, rssi)  # Append latest RSSI value with limits

# Function to monitor RSSI from the Crazyflie
def monitor_drone(uri):
    cflib.crtp.init_drivers()  # Initialize Crazyflie drivers
    with SyncCrazyflie(uri, cf=Crazyflie()) as scf:
        print("Connected to Crazyflie.")

        # Configure RSSI logging
        log_config = LogConfig(name="RSSI", period_in_ms=100)
        log_config.add_variable("radio.rssi", "int8_t")  # Add RSSI variable

        # Set logging callback
        scf.cf.log.add_config(log_config)
        log_config.data_received_cb.add_callback(log_rssi_callback)

        # Start logging
        log_config.start()
        print("Monitoring RSSI. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("Stopping monitoring...")
        finally:
            log_config.stop()

# Flask route to serve the HTML page
@app.route("/")
def index():
    return render_template("index.html")

# Flask route for Server-Sent Events (SSE) to stream RSSI data
@app.route("/stream")
def stream():
    def generate():
        while True:
            with lock:
                # Send spectrum data as JSON
                yield f"data: {list(spectrum)}\n\n"
            time.sleep(0.1)

    return Response(generate(), content_type="text/event-stream")

# Start monitoring thread
threading.Thread(target=monitor_drone, args=(URI,), daemon=True).start()

# Run Flask server
if __name__ == "__main__":
    app.run(debug=True)
