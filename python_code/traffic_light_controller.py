
"""
AI-Powered Dual Traffic Light System
Author: Your Name
Description: YOLOv5-based car detection with Arduino traffic light control
"""
import torch
import cv2
import serial
import time
import logging
import os
from datetime import datetime
from typing import Optional

# === [CONFIG] ===
SOURCE = 1 # Change to your camera index
COM_PORT = 'COM4'   #Change to your Arduino port
BAUD_RATE = 9600
CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence for detections
MODEL_PATH = 'models/best.pt'  # Put your trained model here

# Traffic light timing
YELLOW_DURATION = 2  # Yellow light duration in seconds
HIGH_TRAFFIC_TIMER = 30  # Timer when >=8 cars detected
HIGH_TRAFFIC_THRESHOLD = 8  # Car count threshold for emergency mode (changed from 10 to 8)
LOW_TRAFFIC_THRESHOLD = 6  # Car count threshold to return to normal

# Detection confirmation settings
DETECTION_CONFIRMATION_TIME = 3  # Seconds to confirm car detection before changing light
DETECTION_HISTORY_SIZE = 10  # Number of frames to average for stable detection

# Training data collection
ENABLE_TRAINING_DATA = False  # Set to True to enable automatic dataset collection
# Use absolute path - Update this to your yolov5 folder location!
DATASET_SAVE_PATH = 'dataset'  # Training data collection folder

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DualTrafficLightAI:
    def __init__(self, model_path: str, com_port: str, baud_rate: int = 9600):
        self.model_path = model_path
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.model = None
        self.arduino = None
        self.cap = None
        
        # Traffic light states
        self.light_a = 'R'  # AI-controlled light (starts Red - no cars)
        self.light_b = 'G'  # Opposite light (starts Green - cross traffic)
        
        # Timing variables
        self.yellow_start_time = None
        self.high_traffic_start_time = None
        self.is_yellow_transition = False
        self.is_high_traffic_mode = False
        self.high_traffic_direction = 'B'  # Track which direction has green in high traffic mode
        self.last_command_time = 0
        
        # FPS calculation
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0
        
        # Training data collection
        self.last_save_time = 0
        if ENABLE_TRAINING_DATA:
            # Use custom path or default
            self.dataset_path = os.path.abspath(DATASET_SAVE_PATH)
            os.makedirs(f"{self.dataset_path}/cars", exist_ok=True)
            os.makedirs(f"{self.dataset_path}/empty", exist_ok=True)
            logger.info("=" * 60)
            logger.info("Training data collection ENABLED")
            logger.info(f"Images will be saved to: {self.dataset_path}")
            logger.info(f"  - Cars: {self.dataset_path}/cars/")
            logger.info(f"  - Empty: {self.dataset_path}/empty/")
            logger.info("=" * 60)
            # Open folder in file explorer (Windows only)
            try:
                import subprocess
                subprocess.Popen(f'explorer "{self.dataset_path}"')
                logger.info("📁 Opened dataset folder in File Explorer")
            except:
                pass
        
        # Detection confirmation system
        self.detection_history = []  # Store recent car counts
        self.confirmed_car_count = 0  # Stable car count after confirmation
        self.last_state_change_time = time.time()  # Track when we last confirmed a state change
        self.pending_car_count = 0  # Count we're trying to confirm
        
    def load_model(self):
        """Load YOLOv5 model"""
        try:
            self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=self.model_path)
            self.model.conf = CONFIDENCE_THRESHOLD
            
            # Customize label appearance - smaller text and thinner boxes
            self.model.amp = False  # Disable automatic mixed precision for consistency
            
            logger.info("YOLOv5 model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def setup_arduino(self):
        """Connect to Arduino"""
        try:
            self.arduino = serial.Serial(self.com_port, self.baud_rate, timeout=1)
            time.sleep(2)  # Wait for connection
            logger.info(f"Connected to Arduino on {self.com_port}")
        except Exception as e:
            logger.error(f"Could not connect to Arduino: {e}")
            raise
    
    def setup_camera(self, source):
        """Open webcam"""
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise Exception(f"Cannot open camera source: {source}")
        logger.info(f"Camera opened successfully")
    
    def count_cars(self, detections):
        """Count cars from YOLO detections"""
        car_count = sum(1 for det in detections if int(det[-1]) == 0)
        return car_count
    
    def get_confirmed_car_count(self, current_count):
        """
        Get confirmed car count with temporal smoothing to avoid false detections.
        Only updates the confirmed count if the detection is stable for DETECTION_CONFIRMATION_TIME seconds.
        """
        current_time = time.time()
        
        # Add current count to history
        self.detection_history.append(current_count)
        
        # Keep only recent history
        if len(self.detection_history) > DETECTION_HISTORY_SIZE:
            self.detection_history.pop(0)
        
        # Calculate average of recent detections
        avg_count = sum(self.detection_history) / len(self.detection_history)
        # Round to nearest integer for car count
        smoothed_count = round(avg_count)
        
        # Check if we need to change state
        # For high traffic threshold, be more responsive
        if smoothed_count >= HIGH_TRAFFIC_THRESHOLD:
            # High traffic detected - confirm faster or immediately
            state_changed = True
            new_state = smoothed_count
        elif self.confirmed_car_count == 0 and smoothed_count >= 1:
            # Trying to transition from 0 cars to 1+ cars
            state_changed = True
            new_state = smoothed_count
        elif self.confirmed_car_count >= 1 and smoothed_count == 0:
            # Trying to transition from 1+ cars to 0 cars
            state_changed = True
            new_state = 0
        elif abs(smoothed_count - self.confirmed_car_count) > 0:
            # Car count changed but not crossing 0 boundary
            state_changed = True
            new_state = smoothed_count
        else:
            state_changed = False
            new_state = self.confirmed_car_count
        
        # If state is trying to change
        if state_changed:
            # Check if this is a new pending change
            if new_state != self.pending_car_count:
                # New change detected, start confirmation timer
                self.pending_car_count = new_state
                self.last_state_change_time = current_time
                logger.debug(f"New detection pending: {new_state} cars (waiting {DETECTION_CONFIRMATION_TIME}s)")
            else:
                # Still the same pending change, check if enough time has passed
                time_elapsed = current_time - self.last_state_change_time
                
                # Reduce confirmation time for high traffic (urgent)
                required_time = DETECTION_CONFIRMATION_TIME
                if new_state >= HIGH_TRAFFIC_THRESHOLD:
                    required_time = 1.5  # Only 1.5 seconds for high traffic (faster response)
                    logger.debug(f"High traffic pending: {new_state} cars (waiting {required_time}s)")
                
                if time_elapsed >= required_time:
                    # Confirmed! Update the official count
                    self.confirmed_car_count = new_state
                    logger.info(f"Detection CONFIRMED: {self.confirmed_car_count} cars (stable for {time_elapsed:.1f}s)")
                    # Reset pending
                    self.pending_car_count = self.confirmed_car_count
        else:
            # State hasn't changed, maintain current confirmed count
            self.pending_car_count = self.confirmed_car_count
        
        return self.confirmed_car_count
    
    def calculate_fps(self):
        """Calculate current FPS"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.fps_start_time >= 1.0:  # Update every second
            self.current_fps = self.fps_counter
            self.fps_counter = 0
            self.fps_start_time = current_time
    
    def save_training_frame(self, frame, car_count):
        """Automatically save images for future training"""
        if not ENABLE_TRAINING_DATA:
            return
        
        current_time = time.time()
        
        if car_count > 0:
            # Save image when cars are detected (not too frequently)
            if current_time - self.last_save_time >= 2:  # Save every 2 seconds max
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{self.dataset_path}/cars/{timestamp}_cars_{car_count}.jpg"
                cv2.imwrite(filename, frame)
                logger.info(f"💾 Saved: {filename}")
                self.last_save_time = current_time
        else:
            # Save occasional empty frames to help balance dataset
            if current_time - self.last_save_time >= 10:  # Save every ~10s when no cars
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{self.dataset_path}/empty/{timestamp}_empty.jpg"
                cv2.imwrite(filename, frame)
                logger.info(f"💾 Saved: {filename}")
                self.last_save_time = current_time
    
    def send_commands(self, light_a, light_b, high_traffic_alert=False):
        """Send commands to Arduino for both traffic lights"""
        try:
            # Only send if state actually changed or high traffic alert
            if self.light_a == light_a and self.light_b == light_b and not high_traffic_alert:
                return  # No change needed
            
            # Send format: "A[command]B[command]" e.g., "AGBR" = A=Green, B=Red
            command = f"A{light_a}B{light_b}"
            
            # Add high traffic alert flag if needed
            if high_traffic_alert:
                command += "H"  # Add 'H' flag for high traffic mode
            
            self.arduino.write(command.encode())
            
            light_names = {'R': 'RED', 'G': 'GREEN', 'Y': 'YELLOW'}
            if high_traffic_alert:
                logger.info(f"HIGH TRAFFIC ALERT - Traffic A: {light_names.get(light_a)}, Traffic B: {light_names.get(light_b)}")
            else:
                logger.info(f"CHANGED - Traffic A: {light_names.get(light_a)}, Traffic B: {light_names.get(light_b)}")
            
            self.light_a = light_a
            self.light_b = light_b
            self.last_command_time = time.time()
            
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
    
    def get_opposite_light(self, light):
        """Get opposite traffic light state"""
        if light == 'G':
            return 'R'
        elif light == 'R':
            return 'G'
        else:  # Yellow
            return 'R'  # When one is yellow, other stays red
    
    def update_traffic_lights(self, car_count):
        """Update traffic light states based on car count and timing"""
        current_time = time.time()
        
        # Handle yellow light transition
        if self.is_yellow_transition:
            if current_time - self.yellow_start_time >= YELLOW_DURATION:
                # Yellow transition complete, determine next state
                if self.is_high_traffic_mode:
                    # In high traffic mode, complete the direction switch
                    if self.high_traffic_direction == 'A':
                        self.send_commands('G', 'R')  # A gets green
                    else:
                        self.send_commands('R', 'G')  # B gets green
                    
                    # Restart the 30-second timer for the new direction
                    self.high_traffic_start_time = current_time
                    logger.info(f"✅ High traffic alternation complete - Direction {self.high_traffic_direction} gets 30 seconds")
                
                elif car_count >= HIGH_TRAFFIC_THRESHOLD:
                    # Entering high traffic mode after yellow - BUZZ ALERT!
                    if self.high_traffic_direction == 'A':
                        self.send_commands('G', 'R', high_traffic_alert=True)
                    else:
                        self.send_commands('R', 'G', high_traffic_alert=True)
                    self.is_high_traffic_mode = True
                    self.high_traffic_start_time = current_time
                    logger.info(f"✅ Entered high traffic mode - Direction {self.high_traffic_direction} gets 30 seconds")
                
                elif car_count == 0:
                    # No cars - cross traffic gets green
                    self.send_commands('R', 'G')
                    logger.info("Yellow transition complete - Cross traffic active")
                else:
                    # Cars detected - AI gets green
                    self.send_commands('G', 'R')
                    logger.info(f"Yellow transition complete - AI control active ({car_count} cars)")
                
                self.is_yellow_transition = False
            return
        
        # Handle high traffic mode (>=8 cars)
        if car_count >= HIGH_TRAFFIC_THRESHOLD:
            if not self.is_high_traffic_mode:
                # Start transition to give other direction green light
                if self.light_a == 'G':
                    # A is green, needs yellow transition to red, then B will get green
                    self.send_commands('Y', 'R')
                    self.is_yellow_transition = True
                    self.yellow_start_time = current_time
                    self.high_traffic_direction = 'B'  # B will get green after transition
                    logger.info(f"High traffic detected ({car_count} cars) - Starting yellow transition")
                elif self.light_a == 'R':
                    # A already red, start high traffic mode with B getting green - BUZZ ALERT!
                    if self.light_b != 'G':
                        self.send_commands('R', 'G', high_traffic_alert=True)
                    else:
                        # Already in correct state, just set high traffic mode with alert
                        self.arduino.write(b'H\n')  # Send just high traffic alert
                    self.is_high_traffic_mode = True
                    self.high_traffic_start_time = current_time
                    self.high_traffic_direction = 'B'  # B gets the green first
                    logger.info(f"High traffic detected ({car_count} cars) - Activating high traffic mode")
            else:
                # Already in high traffic mode, check if timer expired
                if current_time - self.high_traffic_start_time >= HIGH_TRAFFIC_TIMER:
                    # Timer expired - check if traffic cleared to 0
                    if car_count == 0:
                        # Traffic cleared completely, exit high traffic mode
                        self.is_high_traffic_mode = False
                        self.send_commands('R', 'G')  # Default: cross traffic gets green when no cars
                        logger.info("High traffic mode ended - No cars detected, returning to normal")
                    else:
                        # Still has traffic (even if below threshold), alternate directions
                        current_green = self.high_traffic_direction
                        
                        # Switch to opposite direction
                        if self.high_traffic_direction == 'A':
                            self.high_traffic_direction = 'B'
                        else:
                            self.high_traffic_direction = 'A'
                        
                        # Start yellow transition to switch directions
                        if current_green == 'A':
                            # A was green, start A yellow transition
                            self.send_commands('Y', 'R')
                        else:
                            # B was green, start B yellow transition  
                            self.send_commands('R', 'Y')
                        
                        self.is_yellow_transition = True
                        self.yellow_start_time = current_time
                        logger.info(f"High traffic alternation - {car_count} cars remain, switching to direction {self.high_traffic_direction}")
                        
                        # Don't restart high traffic timer yet - wait for yellow to complete
        
        # Normal traffic mode (<8 cars but not 0) OR exiting high traffic
        else:
            if self.is_high_traffic_mode:
                # Was in high traffic mode, traffic reduced below threshold
                # Only exit when car count reaches 0
                if car_count == 0:
                    # Exit high traffic mode completely
                    self.is_high_traffic_mode = False
                    self.send_commands('R', 'G')  # Cross traffic gets green
                    logger.info("Exiting high traffic mode - No cars detected")
                else:
                    # Car count dropped below 8 but not 0 yet
                    # Continue alternating until it reaches 0
                    if current_time - self.high_traffic_start_time >= HIGH_TRAFFIC_TIMER:
                        # Timer expired, alternate even though below threshold
                        current_green = self.high_traffic_direction
                        
                        # Switch to opposite direction
                        if self.high_traffic_direction == 'A':
                            self.high_traffic_direction = 'B'
                        else:
                            self.high_traffic_direction = 'A'
                        
                        # Start yellow transition to switch directions
                        if current_green == 'A':
                            self.send_commands('Y', 'R')
                        else:
                            self.send_commands('R', 'Y')
                        
                        self.is_yellow_transition = True
                        self.yellow_start_time = current_time
                        logger.info(f"High traffic mode continuing - {car_count} cars (below threshold but not 0), switching to direction {self.high_traffic_direction}")
            else:
                # Normal AI control logic
                if car_count == 0:
                    # No cars detected - give cross traffic the green
                    if self.light_a == 'G':
                        # Need to transition from green to red with yellow buffer
                        self.send_commands('Y', 'R')
                        self.is_yellow_transition = True
                        self.yellow_start_time = current_time
                        logger.info("No cars detected - Starting yellow transition to cross traffic")
                    elif self.light_a == 'R':
                        # Already red, just make sure B is green
                        if self.light_b != 'G':
                            self.send_commands('R', 'G')
                
                elif car_count >= 1:
                    # Any cars detected (1-7) - give AI side the green
                    if self.light_a == 'R':
                        # Need to transition from red to green - first yellow B, then switch
                        if self.light_b == 'G':
                            # B needs to go from green to red via yellow
                            self.send_commands('R', 'Y')
                            self.is_yellow_transition = True
                            self.yellow_start_time = current_time
                            logger.info(f"Cars detected ({car_count}) - Starting yellow transition to AI control")
                        else:
                            # B already not green, can switch A to green
                            self.send_commands('G', 'R')
                    elif self.light_a == 'G':
                        # Already green, just make sure B is red
                        if self.light_b != 'R':
                            self.send_commands('G', 'R')
    
    def draw_interface(self, frame, car_count, confirmed_count):
        """Draw all interface elements on frame"""
        current_time = time.time()
        
        # Draw raw car count (what's currently detected)
        cv2.putText(frame, f"Detected Now: {car_count}", (10, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 2)
        
        # Draw confirmed car count (what the system uses for decisions)
        cv2.putText(frame, f"Confirmed Cars: {confirmed_count}", (10, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        # Show if detection is pending confirmation
        if car_count != confirmed_count:
            time_elapsed = current_time - self.last_state_change_time
            remaining = DETECTION_CONFIRMATION_TIME - time_elapsed
            if remaining > 0:
                cv2.putText(frame, f"Confirming... {remaining:.1f}s", (10, 75), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
        
        # Draw FPS
        cv2.putText(frame, f"FPS: {self.current_fps}", (10, 95), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw traffic light states
        light_colors = {'G': (0, 255, 0), 'Y': (0, 255, 255), 'R': (0, 0, 255)}
        light_names = {'G': 'GREEN', 'Y': 'YELLOW', 'R': 'RED'}
        
        # Traffic Light A (AI-controlled)
        color_a = light_colors.get(self.light_a, (255, 255, 255))
        cv2.putText(frame, f"Traffic A (AI): {light_names.get(self.light_a)}", (10, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_a, 2)
        
        # Traffic Light B (Opposite)
        color_b = light_colors.get(self.light_b, (255, 255, 255))
        cv2.putText(frame, f"Traffic B: {light_names.get(self.light_b)}", (10, 145), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_b, 2)
        
        # Draw mode and timing info
        if self.is_yellow_transition:
            remaining = YELLOW_DURATION - (current_time - self.yellow_start_time)
            cv2.putText(frame, f"YELLOW TRANSITION: {remaining:.1f}s", (10, 170), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        elif self.is_high_traffic_mode:
            remaining = HIGH_TRAFFIC_TIMER - (current_time - self.high_traffic_start_time)
            direction_name = "AI Side (A)" if self.high_traffic_direction == 'A' else "Cross Traffic (B)"
            cv2.putText(frame, f"HIGH TRAFFIC: {direction_name} - {remaining:.1f}s", (10, 170), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 100, 255), 1)
        
        elif confirmed_count >= HIGH_TRAFFIC_THRESHOLD:
            cv2.putText(frame, f"HIGH TRAFFIC DETECTED!", (10, 170), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        else:
            cv2.putText(frame, "NORMAL MODE", (10, 170), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Draw threshold info
        cv2.putText(frame, f"AI Control: >=1 car | Cross Traffic: 0 cars | High Traffic: >=8 cars", (10, 195), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Draw confirmation info
        cv2.putText(frame, f"Detection Delay: {DETECTION_CONFIRMATION_TIME}s (reduces false positives)", (10, 215), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        # Draw controls
        cv2.putText(frame, "Controls: 'q' = quit, 'r' = reset", (10, frame.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Draw traffic light visualization
        self.draw_traffic_lights(frame)
    
    def draw_traffic_lights(self, frame):
        """Draw visual traffic light representation"""
        # Position for traffic lights
        start_x = frame.shape[1] - 200
        start_y = 50
        
        # Draw background boxes for traffic lights
        cv2.rectangle(frame, (start_x - 10, start_y - 10), (start_x + 50, start_y + 90), (50, 50, 50), -1)
        cv2.rectangle(frame, (start_x + 70, start_y - 10), (start_x + 130, start_y + 90), (50, 50, 50), -1)
        
        # Traffic Light A
        cv2.putText(frame, "Traffic A", (start_x - 10, start_y - 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw circles for A
        colors_a = {'R': (64, 64, 64), 'Y': (64, 64, 64), 'G': (64, 64, 64)}
        if self.light_a == 'R':
            colors_a['R'] = (0, 0, 255)
        elif self.light_a == 'Y':
            colors_a['Y'] = (0, 255, 255)
        elif self.light_a == 'G':
            colors_a['G'] = (0, 255, 0)
        
        cv2.circle(frame, (start_x + 20, start_y + 15), 12, colors_a['R'], -1)  # Red
        cv2.circle(frame, (start_x + 20, start_y + 40), 12, colors_a['Y'], -1)  # Yellow
        cv2.circle(frame, (start_x + 20, start_y + 65), 12, colors_a['G'], -1)  # Green
        
        # Add white borders
        cv2.circle(frame, (start_x + 20, start_y + 15), 12, (255, 255, 255), 2)
        cv2.circle(frame, (start_x + 20, start_y + 40), 12, (255, 255, 255), 2)
        cv2.circle(frame, (start_x + 20, start_y + 65), 12, (255, 255, 255), 2)
        
        # Traffic Light B
        cv2.putText(frame, "Traffic B", (start_x + 70, start_y - 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw circles for B
        colors_b = {'R': (64, 64, 64), 'Y': (64, 64, 64), 'G': (64, 64, 64)}
        if self.light_b == 'R':
            colors_b['R'] = (0, 0, 255)
        elif self.light_b == 'Y':
            colors_b['Y'] = (0, 255, 255)
        elif self.light_b == 'G':
            colors_b['G'] = (0, 255, 0)
        
        cv2.circle(frame, (start_x + 100, start_y + 15), 12, colors_b['R'], -1)  # Red
        cv2.circle(frame, (start_x + 100, start_y + 40), 12, colors_b['Y'], -1)  # Yellow
        cv2.circle(frame, (start_x + 100, start_y + 65), 12, colors_b['G'], -1)  # Green
        
        # Add white borders
        cv2.circle(frame, (start_x + 100, start_y + 15), 12, (255, 255, 255), 2)
        cv2.circle(frame, (start_x + 100, start_y + 40), 12, (255, 255, 255), 2)
        cv2.circle(frame, (start_x + 100, start_y + 65), 12, (255, 255, 255), 2)
    
    def draw_custom_detections(self, frame, detections):
        """Draw custom detection boxes with smaller text and thinner lines"""
        for _, det in detections.iterrows():
            if det['name'] == 'car':
                x1, y1, x2, y2 = int(det['xmin']), int(det['ymin']), int(det['xmax']), int(det['ymax'])
                confidence = det['confidence']
                
                # Draw thinner bounding box (thickness=1 instead of default 2-3)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 1)  # Thinner blue box
                
                # Draw smaller label text
                label = f"car {confidence:.2f}"
                
                # Smaller font size (0.3 instead of default 0.5)
                font_scale = 0.3
                thickness = 1
                
                # Get text size for background
                (text_width, text_height), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
                )
                
                # Draw background rectangle for text (smaller)
                cv2.rectangle(frame, 
                            (x1, y1 - text_height - baseline - 2), 
                            (x1 + text_width, y1), 
                            (255, 0, 0), -1)
                
                # Draw text (smaller)
                cv2.putText(frame, label, 
                          (x1, y1 - baseline - 2), 
                          cv2.FONT_HERSHEY_SIMPLEX, 
                          font_scale, 
                          (255, 255, 255), 
                          thickness)
        
        return frame
    
    def run(self, source):
        """Main detection loop"""
        try:
            # Initialize components
            self.load_model()
            self.setup_arduino()
            self.setup_camera(source)
            
            # Initialize traffic lights
            self.send_commands('R', 'G')  # Start with A=Red (no cars), B=Green (cross traffic)
            
            logger.info("Starting Dual Traffic Light AI System...")
            
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logger.error("Failed to grab frame")
                    break
                
                # Calculate FPS
                self.calculate_fps()
                
                # Run YOLO detection
                results = self.model(frame)
                detections = results.xyxy[0]
                
                # Count cars (raw detection)
                raw_car_count = self.count_cars(detections)
                
                # Get confirmed car count (with temporal smoothing)
                car_count = self.get_confirmed_car_count(raw_car_count)
                
                # Debug logging for high traffic
                if raw_car_count >= HIGH_TRAFFIC_THRESHOLD or car_count >= HIGH_TRAFFIC_THRESHOLD:
                    logger.info(f"⚠️  Raw: {raw_car_count} cars, Confirmed: {car_count} cars, High Traffic Mode: {self.is_high_traffic_mode}")
                
                # Save training data if enabled (use raw count for actual detections)
                self.save_training_frame(frame, raw_car_count)
                
                # Update traffic light logic (use confirmed count)
                self.update_traffic_lights(car_count)
                
                # Get rendered frame with detections
                display_frame = results.render()[0].copy()
                
                # Optional: Draw custom smaller labels if you want even more control
                # Uncomment the next line and comment the above line for custom rendering
                # display_frame = self.draw_custom_detections(frame.copy(), results.pandas().xyxy[0])
                
                # Draw interface (show both raw and confirmed counts)
                self.draw_interface(display_frame, raw_car_count, car_count)
                
                # Show frame
                cv2.imshow('Dual Traffic Light AI System', display_frame)
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    logger.info("Quit requested by user")
                    break
                elif key == ord('r'):
                    # Reset to normal mode (no cars detected)
                    self.light_a = 'R'
                    self.light_b = 'G'
                    self.is_yellow_transition = False
                    self.is_high_traffic_mode = False
                    self.high_traffic_direction = 'B'
                    self.send_commands('R', 'G')
                    logger.info("System reset - Cross traffic mode (no cars)")
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        if self.arduino:
            self.arduino.close()
        logger.info("Cleanup complete")

# === [MAIN EXECUTION] ===
if __name__ == "__main__":
    print("=== Dual Traffic Light AI System ===")
    print("Features:")
    print("- 0 cars: Traffic A = RED, Traffic B = GREEN (cross traffic)")
    print("- 1-7 cars: Traffic A = GREEN, Traffic B = RED (AI control)")
    print("- >=8 cars: Alternating mode - each direction gets 30 seconds until traffic clears to 0")
    print("- Yellow buffer: 2 seconds for ALL Green→Red transitions")
    print("- Real-time FPS display")
    print("- BUZZER: Only sounds when entering high traffic mode (>=8 cars)")
    print(f"- DETECTION DELAY: {DETECTION_CONFIRMATION_TIME}s confirmation time (reduces false positives)")
    if ENABLE_TRAINING_DATA:
        print("- TRAINING DATA COLLECTION: Enabled (saving to dataset/ folder)")
    print() 
    
    try:
        # Create and run the system
        traffic_system = DualTrafficLightAI(MODEL_PATH, COM_PORT, BAUD_RATE)
        traffic_system.run(SOURCE)
        
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"Error: {e}")