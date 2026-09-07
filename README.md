# 🚘 Driver Vigilance & Safety System

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MediaPipe](https://img.shields.io/badge/AI-Google%20MediaPipe-orange.svg)](https://developers.google.com/mediapipe)
[![OpenCV](https://img.shields.io/badge/Computer%20Vision-OpenCV-red.svg)](https://opencv.org/)
[![Tests](https://img.shields.io/badge/tests-100%25%20passing-brightgreen.svg)](tests/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

An open-source, edge-computing automotive safety platform engineered to prevent vehicular crashes caused by driver drowsiness, microsleeps, and compromised sitting ergonomics.

The system fuses high-precision **ocular dynamics** (Eye Aspect Ratio & Mouth Aspect Ratio) and **skeletal posture geometry** into an intelligent decision matrix. When critical fatigue or the joint multi-factor condition occurs, the system triggers an urgent **acoustic siren**, announces spoken **voice guidance**, automatically detects the driver's **real-time GPS coordinates**, and builds a **1-click Google Maps turn-by-turn driving route** to the nearest petrol pump or safe rest area.

---

## 📑 Table of Contents
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Technical Documentation (PDF)](#-technical-documentation-pdf)
- [Quick Start & Installation](#-quick-start--installation)
- [Interactive Cockpit Modes & Hotkeys](#-interactive-cockpit-modes--hotkeys)
- [Algorithmic Specifications](#-algorithmic-specifications)
- [Repository Structure](#-repository-structure)
- [Automated Test Suite](#-automated-test-suite)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Key Features

### 1. Facial & Ocular Dynamics (`core/vision.py`)
- **Eye Aspect Ratio (EAR)**: Sub-millisecond tracking of 6 eyelid landmarks using Google MediaPipe FaceLandmarker. Detects blinks, eye closure, and prolonged microsleep episodes ($\ge 1.2\text{s}$).
- **Mouth Aspect Ratio (MAR)**: Monitors vertical lip aperture relative to mouth width to detect yawning episodes ($MAR > 0.65$) and tracks yawn frequency.
- **PERCLOS Tracking**: Computes cumulative Percentage of Eye Closure over a 60-frame sliding window.
- **3D Head Pose Estimation**: Employs `cv2.solvePnP` to estimate 3D head pitch (nodding), yaw (inattention), and roll (tilt).

### 2. Seat Posture & Ergonomics Detector (`core/posture.py`)
- Analyzes upper-body skeletal landmarks (nose tip, shoulders, spinal midpoint) against an attentive driving baseline:
  - **`ACTIVE_ATTENTIVE`**: Upright, centered, attentive driving posture.
  - **`HEAD_DROPPED_FORWARD`**: Chin sinking towards chest (classic microsleep nodding sign).
  - **`SLOUCHING`**: Spinal compression and downward collapse in seat.
  - **`LATERAL_LEAN`**: Lateral leaning against vehicle door or center console.

### 3. Multi-Factor Fusion Engine (`core/fusion.py`)
- Computes a composite **Vigilance Risk Index (VRI)**:
  $$\text{VRI} = 0.60 \cdot S_{\text{ocular}} + 0.40 \cdot S_{\text{posture}}$$
- **Joint Trigger ("ALL CONDITIONS TRIGGERED")**: Immediately escalates to emergency alarm when:
  $$\text{Ocular Fatigue (Microsleep / Yawning)} \land \text{Compromised Posture (Head Drop / Slouch)}$$
- **Emergency Override**: Sustained eye closure $\ge 2.0\text{s}$ triggers maximum alert immediately, regardless of posture.

### 4. Driver GPS Tracking & Petrol Pump / Rest Area Routing (`core/gps_locator.py`)
- **Real-Time GPS Resolution**: Resolves exact driver coordinates (Latitude & Longitude) in a daemon background thread.
- **Nearest Petrol Pump / Rest Area Discovery**: Queries local fuel stations (IndianOil, BP, Shell, HP, highway travel plazas) within a $15\text{ km}$ bounding box.
- **Great-Circle Haversine Distance & ETA**: Computes spherical distance and driving ETA dynamically based on current vehicle speed.
- **1-Click Google Maps Navigation**: Generates direct turn-by-turn driving route links (`https://www.google.com/maps/dir/?api=1&origin={lat},{lon}&destination={lat},{lon}&travelmode=driving`).
- **Acoustic Siren & Spoken Voice**: Alternating dual-frequency siren ($1250\text{ Hz} \leftrightarrow 1750\text{ Hz}$) and native Windows SAPI spoken guidance directing the driver to the nearest safe haven.

### 5. Dual Cockpit Display Modes
- **Desktop Cockpit Dashboard (`ui/dashboard.py`)**: Dark-themed automotive dashboard (Tkinter) with live video canvas, telemetry gauge cards, simulation test bench, driver GPS badge, and 1-click Google Maps route button.
- **Heads-Up Display HUD (`ui/hud_renderer.py`)**: High-performance OpenCV HUD overlay featuring real-time EAR/MAR meters, posture wireframe, and high-visibility flashing alert modal.
- **Synthetic Cabin Simulator (`core/synthetic_driver.py`)**: Built-in animated driver avatar for 100% functional testing without physical cameras.

---

## 🏛 System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    APPLICATION LAYER                                    |
|   Cockpit Dashboard (Tkinter / ttk)        |     High-Performance Direct HUD (OpenCV)   |
|   - Real-time video canvas (Pillow/PIL)     |     - Dynamic EAR/MAR live graphical bars  |
|   - Real-time telemetry gauge cards        |     - High-visibility flashing alert modal |
|   - 1-Click Google Maps navigation dispatch|     - Seat posture wireframe overlay       |
+-----------------------------------------------------------------------------------------+
|                                  CORE PROCESSING ENGINE                                 |
|   Vision Module (core/vision.py)           |     Posture Module (core/posture.py)       |
|   - MediaPipe FaceLandmarker (468 points)  |     - Head pitch, roll, and spinal ratio   |
|   - EAR & MAR landmark geometry            |     - Posture state classification         |
+-----------------------------------------------------------------------------------------+
|                                   MULTI-FACTOR FUSION                                   |
|   Fusion Engine (core/fusion.py)                                                        |
|   - Joint Trigger: (Eyes Closed / Microsleep) AND (Head Dropped Forward / Slouching)   |
|   - Emergency Override: Sustained eye closure >= 2.0s                                   |
+-----------------------------------------------------------------------------------------+
|                                SAFETY ESCALATION & ROUTING                              |
|   Acoustic & Voice Alert (core/alert.py)   |     GPS & POI Locator (core/gps_locator.py)|
|   - Multi-frequency siren (1250-1750 Hz)   |     - Network driver GPS coordinate lookup |
|   - Native Windows SAPI text-to-speech     |     - Bounded OSM Nominatim fuel discovery |
|   - Safe stopping guidance                 |     - Haversine distance & Google Maps URL |
+-----------------------------------------------------------------------------------------+
```

---

## 📄 Technical Documentation (PDF)

A balanced, publication-grade 5-page technical specification and operational manual is included in the root directory:
- **`Driver_Vigilance_System_Documentation.pdf`**
- Rebuildable via: `python build_documentation_pdf.py`

Covers executive architecture, dependency analysis, mathematical equations, POI routing protocols, cockpit hotkeys, and test verification results.

---

## 🚀 Quick Start & Installation

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14+
- Windows 10 / 11 (or Linux/macOS for core vision/posture logic)
- Standard USB webcam or built-in camera (optional: synthetic driver simulator works offline)

### 1. Clone the Repository
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/driver-vigilance-system.git
cd driver-vigilance-system
```

### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Launch the System

**Method 1 (1-Click Launch on Windows):**
Double-click `run.bat` in the project root directory.

**Method 2 (Cockpit Desktop Dashboard):**
```bash
python main.py
```

**Method 3 (Direct High-Performance OpenCV HUD):**
```bash
python main.py --mode opencv
```

---

## 🎮 Interactive Cockpit Modes & Hotkeys

When running in OpenCV HUD mode (`--mode opencv`), you can trigger real-time simulated conditions directly via keyboard:

| Hotkey | Action | Operational Description |
| :---: | :--- | :--- |
| **`a`** | 🚨 **TRIGGER ALL CONDITIONS** | Simulates joint eye closure + head-drop forward; fires siren, voice alert, GPS, and nearest petrol pump route. |
| **`c`** | **Toggle Eye Closure** | Forces EAR below $0.22$; accumulates eye closure duration; triggers microsleep after $1.2\text{s}$. |
| **`y`** | **Toggle Yawn** | Spikes MAR above $0.65$; records yawn frequency episode. |
| **`p`** | **Toggle Inactive Posture** | Tilts head down $28^\circ$; triggers `HEAD_DROPPED_FORWARD` seat posture. |
| **`r`** | **Reset to Active Nominal** | Silences siren, clears fatigue overrides, and returns avatar to alert state. |
| **`m`** | **Toggle Mute** | Mutes / unmutes acoustic square-wave siren beeper. |
| **`q`** | **Quit Application** | Safely shuts down background threads and releases camera hardware. |

---

## 📐 Algorithmic Specifications

### Eye Aspect Ratio (EAR)
$$\text{EAR} = \frac{\|p_2 - p_6\| + \|p_3 - p_5\|}{2 \cdot \|p_1 - p_4\|}$$
- **Alert Eye**: $\text{EAR} \ge 0.28$
- **Eye Closed**: $\text{EAR} < 0.22$
- **Microsleep**: $\text{Closure Duration} \ge 1.2\text{ seconds}$

### Mouth Aspect Ratio (MAR)
$$\text{MAR} = \frac{\|p_{\text{upper}} - p_{\text{lower}}\|}{\|p_{\text{left}} - p_{\text{right}}\|}$$
- **Nominal Mouth**: $\text{MAR} \approx 0.15 - 0.25$
- **Yawn Episode**: $\text{MAR} > 0.65$ sustained for $> 1.0\text{ second}$

### Great-Circle Haversine Distance
$$d = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
- Computes accurate spherical surface distance in kilometers between driver coordinates and POI.

---

## 📁 Repository Structure

```
driver-vigilance-system/
├── core/
│   ├── alert.py            # Non-blocking siren loop, voice alerts, guidance coordinator
│   ├── fusion.py           # Multi-factor Vigilance Risk Index & joint trigger logic
│   ├── gps_locator.py      # Real-time driver GPS coordinate resolution & OSM fuel POI finder
│   ├── mock_data.py        # Safe stopping havens & rest stop catalog
│   ├── posture.py          # Upper-body ergonomics & head-drop pitch classifier
│   ├── synthetic_driver.py # Interactive animated cockpit driver simulator
│   ├── vision.py           # MediaPipe FaceLandmarker, EAR, MAR, 3D head pose
│   └── __init__.py         # Package entry
├── models/
│   ├── face_landmarker.task       # MediaPipe Face Landmarker model asset (3.75 MB)
│   └── pose_landmarker_lite.task  # MediaPipe Pose Landmarker model asset (5.77 MB)
├── ui/
│   ├── dashboard.py        # Modern dark Tkinter cockpit dashboard
│   ├── hud_renderer.py     # Real-time OpenCV automotive HUD overlay
│   └── __init__.py         # UI package entry
├── tests/
│   ├── test_fusion.py      # Multi-factor fusion & override tests
│   ├── test_gps.py         # Haversine distance, GPS lookup & route tests
│   ├── test_telemetry.py   # Posture classification & rest stop sorting tests
│   ├── test_vision.py      # EAR and MAR computation tests
│   └── __init__.py         # Test package entry
├── .gitignore              # Git ignore rules for Python, IDEs, and OS files
├── build_documentation_pdf.py  # ReportLab script generating balanced 5-page PDF
├── CONTRIBUTING.md         # Guidelines for open-source contributors
├── Driver_Vigilance_System_Documentation.pdf  # 5-Page Technical PDF Manual
├── LICENSE                 # MIT Open-Source License
├── main.py                 # Multi-mode CLI / GUI application entry point
├── README.md               # Project documentation
├── requirements.txt        # Production dependency specifications
└── run.bat                 # 1-Click Windows batch launcher
```

---

## 🧪 Automated Test Suite

Run the full automated test suite using Python's standard `unittest`:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

**Output:**
```
Ran 10 tests in 1.86s
OK
```

All 10 tests validate:
- Nominal attentive baseline ($VRI < 30\%$).
- Joint trigger ("ALL CONDITIONS TRIGGERED") upon simultaneous eye closure and slouching/head drop.
- Emergency override firing upon $\ge 2.0\text{s}$ eye closure.
- Haversine distance formula against known geographic benchmarks.
- Driver network GPS resolution and Google Maps turn-by-turn route URL generation.
- Seat posture state classification (`ACTIVE_ATTENTIVE`, `HEAD_DROPPED_FORWARD`, `LATERAL_LEAN`).
- EAR and MAR dynamic metric updates.

---

## 🤝 Contributing

Contributions are very welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on code formatting, branch naming, and pull request procedures.

1. Fork the repo.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'feat: add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
