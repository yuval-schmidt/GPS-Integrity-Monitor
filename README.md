# GPS Integrity & Anti-Spoofing Monitor 🛰️🛡️

## Overview
The **GPS Integrity Monitor** is a Python-based system designed to detect and mitigate GPS spoofing, replay attacks, and signal manipulation. As GPS signals become increasingly vulnerable to interference and manipulation by end-users (e.g., Fake GPS apps), relying solely on GNSS data for critical decision-making is a major security risk.

This project solves this problem by cross-referencing incoming NMEA (`$GNGGA`) GPS data with independent network-based context (IP geolocation, latency, and temporal consistency) to generate a dynamic **Trust Score**.

## The Threat Model & Problem it Solves
In modern cyber-physical systems, an attacker with user-level control over their mobile device can easily broadcast fake GPS coordinates. 

**This system detects anomalies such as:**
*   **GPS Spoofing:** Broadcasted coordinates that do not match the physical network origin.
*   **Replay Attacks:** Re-broadcasting old GPS data (detected via timestamp mismatch).
*   **Spatial Inconsistency:** Unrealistic jumps in location or impossible speed vectors.
*   **Signal Degradation:** Poor satellite reception (Low Sats) or high Dilution of Precision (HDOP).

## How it Works (The Logic)
The server listens for incoming UDP packets containing raw GPS sentences. It does not attempt to "block" the spoofing at the hardware level; instead, it identifies inconsistencies:
1.  **Data Parsing:** Extracts Latitude, Longitude, Time, Satellites, and HDOP from the `$GNGGA` sentence.
2.  **Temporal Validation:** Compares the GPS timestamp against the server's UTC time to detect delays or replay attacks.
3.  **Physical Integrity:** Calculates the distance between the current and previous coordinates using the Haversine formula to detect sudden, impossible jumps.
4.  **Network Cross-Referencing:** Resolves the source IP address to a general geographic area and checks if the reported GPS location contradicts the network origin.
5.  **Trust Score Calculation:** Starts at 100% and applies weighted penalties for any detected anomaly.

## Features
*   **Real-Time UDP Server:** Listens continuously for live GPS streams.
*   **Smart Scoring Algorithm:** Computes penalties dynamically based on multiple risk factors.
*   **Flask Web Dashboard:** A built-in, lightweight web interface (using Chart.js) to visualize the Trust Score and specific penalties in real-time.
*   **Multithreading:** The Flask dashboard runs smoothly as a daemon thread alongside the UDP listener.

## Technologies Used
*   **Python 3.x**
*   **Networking:** `socket`, `requests`, `ipaddress`
*   **Math & Geospatial:** `math` (Haversine formula implementation)
*   **Web Dashboard:** `Flask`, `HTML/JS`, `Chart.js`

## Note
This project was developed as a hands-on exploration of network security, protocol analysis, and vulnerability mitigation in location-based systems.