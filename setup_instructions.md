# 📋 Detailed Setup Instructions

## Prerequisites

- Python 3.9 or higher
- pip package manager  
- Arduino IDE
- Webcam (USB or built-in)
- Arduino Uno with components

## Step 1: Python Environment

### Option A: Anaconda (Recommended)
```bash
conda create -n traffic-ai python=3.9
conda activate traffic-ai
```

### Option B: venv
```bash
python -m venv traffic-env
# Windows:
traffic-env\Scripts\activate
# Linux/Mac:
source traffic-env/bin/activate
```

## Step 2: Install YOLOv5
```bash
git clone https://github.com/ultralytics/yolov5
cd yolov5  
pip install -r requirements.txt
cd ..
```

## Step 3: Install Project Dependencies
```bash
pip install -r requirements.txt
```

## Step 4: Model Setup

### If you have a trained model:
1. Place your `best.pt` file in `models/` folder
2. Update `MODEL_PATH` in the code

### If training from scratch:
1. Collect 500-1000 car images
2. Label using Roboflow or LabelImg
3. Train YOLOv5:
```bash
cd yolov5
python train.py --img 640 --batch 16 --epochs 50 --data your_data.yaml --weights yolov5s.pt
```

## Step 5: Arduino Setup

1. Open Arduino IDE
2. File → Open → `arduino_code/traffic_light_controller.ino`
3. Tools → Board → Arduino Uno
4. Tools → Port → Select your Arduino port
5. Upload

## Step 6: Hardware Assembly

[See main README for wiring diagram]

## Step 7: Test Run
```bash
python python_code/traffic_light_system.py
```

Watch console for:
```
INFO: YOLOv5 model loaded successfully
INFO: Connected to Arduino on COM4
INFO: Camera opened successfully
```

## Common Issues

### "No module named 'torch'"
```bash
pip install torch torchvision
```

### "Camera not found"
- Check camera index (0, 1, 2...)
- Close other apps using camera

### "Arduino not responding"  
- Check COM port
- Re-upload Arduino code
- Try different USB cable

## Configuration Tips

### Adjust Sensitivity
```python
CONFIDENCE_THRESHOLD = 0.70  # Higher = fewer false positives
DETECTION_CONFIRMATION_TIME = 3  # Longer = more stable
```

### Camera Settings
```python
SOURCE = 1  # USB camera
# For IP camera:
SOURCE = "http://192.168.1.100:8080/video"
```

### Traffic Thresholds
```python
HIGH_TRAFFIC_THRESHOLD = 8  # Cars to trigger high traffic mode
HIGH_TRAFFIC_TIMER = 30  # Seconds for each direction
```