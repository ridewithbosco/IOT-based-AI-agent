# RAVEN - Raspberry Pi 4 Setup Guide

Deploy RAVEN AI Navigation Assistant on Raspberry Pi 4 using `uv` package manager.

---

## Hardware Requirements

| Component | Purpose |
|-----------|---------|
| Raspberry Pi 4 (4GB+) | Main compute |
| USB to 3.5mm Audio Adapter | CRITICAL: Pi 3.5mm jack is output-only! |
| Wired Earphones | Mic input and TTS output via USB adapter |
| Pi Camera (USB) | YOLOv8 continuous vision safety |
| NEO-6M/NEO-8M GPS | Location tracking (UART) |

---

## 1. Initial Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y git portaudio19-dev python3-pyaudio alsa-utils
```

---

## 2. Install uv

```bash
# Install uv (Rust-based Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add to ~/.bashrc)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify
uv --version
```

---

## 3. Clone & Setup Project

```bash
cd ~
git clone <your-repo-url> raven
cd raven

# Install dependencies with uv
uv sync
```

---

## 4. Environment Variables

```bash
nano .env
```

Add:
```
GOOGLE_MAPS_API_KEY=your_key
GROQ_API_KEY=your_key
GOOGLE_API_KEY=your_gemini_key
```

---

## 5. Audio Setup

```bash
# List audio devices (Optional check)
arecord -l
```

**Auto-Detection:** You do **not** need to manually configure the device index in the code. The `stt2.py` script contains a `get_best_microphone()` function that will automatically bypass Linux ALSA virtual loops and lock onto any device with "usb" or "mic" in the name. Just plug in your USB adapter and start the app!

---

## 6. GPS Setup (UART)

```bash
# Enable serial
sudo raspi-config
# Interface Options → Serial Port
# Login shell: NO | Hardware: YES
```

### Wiring
| GPS | Pi Pin |
|-----|--------|
| VCC | Pin 2 (5V) |
| GND | Pin 6 |
| TX | Pin 10 (RXD) |

### Test
```bash
cat /dev/serial0
# Should show NMEA sentences
```

---

## 7. Run RAVEN

```bash
cd ~/raven

# With GPS hardware (Auto-detects /dev/serial0 on Pi)
uv run main.py --gps

# Without GPS (mock mode for testing)
uv run main.py
```

---

## 8. Auto-Start on Boot

```bash
sudo nano /etc/systemd/system/raven.service
```

```ini
[Unit]
Description=RAVEN AI Navigation
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/raven
ExecStart=/home/pi/.local/bin/uv run main.py --gps --port=/dev/serial0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable raven.service
sudo systemctl start raven.service

# Check logs
journalctl -u raven.service -f
```

---

## Troubleshooting

### Audio Issues
```bash
arecord -l                    # List devices
pulseaudio -k && pulseaudio --start  # Restart audio
```

### GPS Issues
```bash
sudo usermod -a -G dialout $USER  # Add permissions
# Logout and login
```

### API Rate Limits
Switch to Groq LLM in `agent_graph.py`:
```python
from langchain_groq import ChatGroq
llm = ChatGroq(model="llama-3.1-70b-versatile")
```

---

## Quick Commands

```bash
# Run with Live GPS
uv run main.py --gps

# Run Mock mode
uv run main.py

# Check background service
sudo systemctl status raven.service
```
