# 🚦 AI-Powered Dual Traffic Light System

An intelligent traffic management system using YOLOv5 for real-time car detection and Arduino for hardware control.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Features

- **Real-time Car Detection**: YOLOv5-based with 70% confidence threshold
- **Dual Traffic Lights**: Coordinated A/B intersection management  
- **Smart High Traffic Mode**: Auto-switches when ≥8 cars detected
- **False Positive Reduction**: 3-second confirmation delay (1.5s for emergencies)
- **Audio Alerts**: Buzzer for high traffic conditions
- **Yellow Buffer**: Safe 2-second transitions

## 📊 Traffic Logic

| Cars | Traffic A | Traffic B | Mode |
|------|-----------|-----------|------|
| 0 | 🔴 Red | 🟢 Green | Cross Traffic |
| 1-7 | 🟢 Green | 🔴 Red | AI Control |
| ≥8 | 🔄 30s alternate | 🔄 30s alternate | High Traffic |

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Clone YOLOv5 (required)
git clone https://github.com/ultralytics/yolov5
cd yolov5
pip install -r requirements.txt
cd ..

# Install project requirements
pip install -r requirements.txt
```

### 2. Get a Model

**Option A: Use Pre-trained**
```bash
# Download YOLOv5s model
wget https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.pt -O models/yolov5s.pt
```

**Option B: Train Your Own**
- Collect car images from your camera
- Label them using [Roboflow](https://roboflow.com)
- Train with YOLOv5
- Place trained `best.pt` in `models/` folder

### 3. Setup Hardware

**Components:**
- Arduino Uno
- 6x LEDs (2 red, 2 yellow, 2 green)
- 6x 220Ω resistors  
- 1x Buzzer
- Breadboard & wires

**Wiring:**
- Traffic A: Red=Pin2, Yellow=Pin3, Green=Pin4
- Traffic B: Red=Pin5, Yellow=Pin6, Green=Pin7
- Buzzer: Pin8

Upload `arduino_code/traffic_light_controller.ino` to your Arduino.

### 4. Configure & Run

Edit `python_code/traffic_light_system.py`:
```python
SOURCE = 0  # Your camera (0, 1, 2...)
COM_PORT = 'COM4'  # Your Arduino port
MODEL_PATH = 'models/best.pt'  # Your model path
```

Run:
```bash
python python_code/traffic_light_system.py
```

## 🎮 Controls

- `q` - Quit
- `r` - Reset to normal mode

## 🛠️ Tech Stack

- **AI/ML**: PyTorch, YOLOv5, OpenCV
- **Hardware**: Arduino Uno
- **Languages**: Python 3.9, C++

## 📖 How It Works

1. Camera captures video
2. YOLOv5 detects cars  
3. System confirms detection (3s delay)
4. Calculates optimal light state
5. Sends commands to Arduino
6. Arduino controls LEDs and buzzer

## 🐛 Troubleshooting

**Camera not found:**
```python
SOURCE = 1  # Try different numbers
```

**Arduino not connecting:**
- Check Device Manager for COM port
- Try different USB port
- Update `COM_PORT` in code

**Low FPS:**
- Reduce camera resolution
- Use GPU if available

## 📈 Future Plans

- [ ] Multi-lane support
- [ ] Emergency vehicle priority
- [ ] Web monitoring dashboard
- [ ] Pedestrian detection

## 📝 License

MIT License - Free for educational use

## 👤 Author

**Your Name**  
[GitHub](https://github.com/yourusername) | [LinkedIn](https://linkedin.com/in/yourprofile)

## 🙏 Credits

- [Ultralytics YOLOv5](https://github.com/ultralytics/yolov5)
- OpenCV & Arduino communities

---

⭐ Star this repo if it helped you!