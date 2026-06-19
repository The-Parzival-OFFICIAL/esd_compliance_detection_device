# Fast Response ESD Compliance Monitor

## Overview

The Fast Response ESD Compliance Monitor is a Raspberry Pi-based industrial safety system designed to enforce Electrostatic Discharge (ESD) compliance at electronics assembly and testing workstations.

The system combines human presence detection using the HLK-LD2410C mmWave radar with ESD wrist-strap compliance monitoring. When a person is detected at the workstation and an ESD fault condition exists, an audible alarm is generated to alert the operator.

---

## Features

- Real-time human presence detection using HLK-LD2410C mmWave radar
- ESD wrist-strap compliance monitoring
- Low-latency fault detection and alarm generation
- Presence filtering to reduce false detections
- Analog signal acquisition through MCP3008 ADC
- Flask-based REST API for remote control
- Raspberry Pi deployment
- Systemd service support
- Modular software architecture

---

## System Architecture

![System Architecture](architecture.jpeg)

The system continuously monitors workstation occupancy and ESD compliance status. Presence information from the LD2410C radar and ESD status information from the monitoring circuit are processed by the Raspberry Pi. If a person is detected and an ESD fault condition exists, the buzzer alarm is activated.

---

## Hardware Schematic

![Hardware Schematic](schematic.png)

---

## System Components

| Component | Function |
|------------|------------|
| Raspberry Pi 4 Model B | Main processing unit |
| HLK-LD2410C | Human presence detection |
| MCP3008 | Analog-to-digital converter |
| Active Buzzer | Audible alarm indication |
| ESD Monitor | Wrist-strap compliance monitoring |
| Flask Server | Remote monitoring and control |

---

## Hardware Interfaces

| Interface | Connected Device |
|------------|------------------|
| UART | HLK-LD2410C Radar |
| SPI | MCP3008 ADC |
| GPIO | Active Buzzer |
| Analog Input | ESD Monitoring Signal |

---

## Software Architecture

```text
┌──────────────────────────────┐
│      Flask Web Server        │
│                              │
│  /health                     │
│  /status                     │
│  /start                      │
│  /stop                       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      Application Layer       │
│                              │
│  Presence Detection Filter   │
│  Compliance Engine           │
│  Alarm Controller            │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      Hardware Drivers        │
│                              │
│  LD2410 UART Driver          │
│  MCP3008 SPI Driver          │
│  GPIO Buzzer Driver          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│          Hardware            │
│                              │
│  HLK-LD2410C Radar           │
│  MCP3008 ADC                 │
│  ESD Monitor                 │
│  Active Buzzer               │
└──────────────────────────────┘
```

---

## Detection Logic

### Presence Detection

The HLK-LD2410C radar continuously provides:

- Motion distance
- Motion energy
- Stationary distance
- Stationary energy
- Gate motion energy values

Presence is determined using the motion energy from the configured gates.

```python
motion_score = gate0_motion + gate1_motion

human_present = (
    motion_score > MOTION_THRESHOLD
)
```

A presence filter is applied to reduce false triggers and improve stability.

---

### ESD Compliance Verification

The ESD monitor output is connected to the MCP3008 ADC.

When a person is present, the ADC value is evaluated against a predefined threshold.

```python
esd_ok = adc_value <= ADC_THRESHOLD
```

If the threshold is exceeded, the workstation is classified as non-compliant.

---

### Alarm Logic

```text
Read Radar Data
       │
       ▼
Human Present ?
    │      │
   No     Yes
    │       │
    ▼       ▼
Alarm OFF  Read ADC
               │
               ▼
      ADC > Threshold ?
           │       │
          No      Yes
           │       │
           ▼       ▼
        ESD OK  ESD Fault
           │       │
           ▼       ▼
      Alarm OFF Alarm ON
```

---

## LD2410 Configuration

The radar is configured for workstation monitoring with:

- Engineering mode enabled
- Fast response operation
- Reduced detection range
- 0.2 m gate resolution
- Optimized gate sensitivity settings
- Presence-focused detection

---

## REST API

### Health Check

```http
GET /health
```

Response:

```json
{
    "status": "healthy",
    "service": "esd-control-server"
}
```

---

### Service Status

```http
GET /status
```

Returns the current status of the ESD monitoring service.

---

### Start Monitoring

```http
POST /start
```

Required Header:

```http
X-API-KEY: esd_secure_key
```

---

### Stop Monitoring

```http
POST /stop
```

Required Header:

```http
X-API-KEY: esd_secure_key
```

---

## Project Structure

```text
Fast-Response-ESD-Monitor/
│
├── compliance.py
├── server.py
│
├── templates/
│   └── main.html
│
├── architecture.png
├── schematic.png
│
├── README.md
├── requirements.txt
└── LICENSE
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/<username>/Fast-Response-ESD-Monitor.git

cd Fast-Response-ESD-Monitor
```

### Install Dependencies

```bash
sudo apt update

sudo apt install python3-pip

pip install pyserial
pip install spidev
pip install RPi.GPIO
pip install flask
pip install flask-limiter
```

---

## Running the Compliance Monitor

```bash
python3 compliance.py
```

---

## Running the Control Server

```bash
python3 server.py
```

The web interface will be available at:

```text
http://<raspberry-pi-ip>:8008
```

---

## Example Output

### Normal Operation

```text
Human=YES | Dist=45cm | G0=34 | G1=29 | ADC=250.3 | V=0.81V | ESD=OK
```

### ESD Fault Condition

```text
Human=YES | Dist=48cm | G0=39 | G1=33 | ADC=365.8 | V=1.18V | ESD=FAULT
```

---

## Applications

- Electronics manufacturing
- PCB assembly lines
- Electronics testing laboratories
- ESD protected workstations
- Industrial production environments
- Quality assurance stations

---

## Future Improvements

- Event logging
- Historical compliance reports
- Database integration
- MQTT support
- Email notifications
- SMS alerts
- Multi-workstation deployment
- Grafana dashboard integration
- Cloud monitoring support

---

## Author

Joseph Mathew

Electronics and Communication Engineering

Embedded Systems | IoT | Industrial Automation

---

## License

This project is licensed under the MIT License.

See the LICENSE file for additional details.