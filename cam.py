"""
Environment Scanner - Continuous vision safety subsystem.
Runs independently, detecting hazards via YOLO every 500ms.
"""

import cv2
import time
import asyncio
import logging
import os
import json
from datetime import datetime
from collections import deque
from dataclasses import dataclass
from typing import Dict
from ultralytics import YOLO
import math
import base64

from audio_manager import audio_manager, AudioPriority

logging.getLogger("ultralytics").setLevel(logging.ERROR)
logger = logging.getLogger("RAVEN.Vision")

@dataclass
class Detection:
    timestamp: float
    obj_class: str
    bbox_area_ratio: float
    is_center: bool
    conf: float
    priority: int

class EnvironmentScanner:
    def __init__(self):
        self._running = False
        self._task = None
        self.model = None
        self.cap = None
        
        self.latest_frame = None  # To share with LLM without fighting for camera access
        
        self.memory: deque = deque()
        self.last_alert_time: Dict[str, float] = {}
        
        self.FRAME_WIDTH = 640
        self.FRAME_HEIGHT = 480
        self.FRAME_AREA = self.FRAME_WIDTH * self.FRAME_HEIGHT
        
        self.P0_CLASSES = {"car", "motorbike", "bus", "train", "truck", "bicycle"}
        self.P1_CLASSES = {"person", "traffic light", "stop sign", "fire hydrant", "dog", "horse", "cow"}
        
        self.P0_COOLDOWN = 3.0
        self.P1_COOLDOWN = 8.0
        
        # Setup Vision Logger
        os.makedirs("vision_logs", exist_ok=True)
        self.log_file = f"vision_logs/vision_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        self.log_buffer = []
        
    async def start(self):
        if self._running: return
        self._running = True
        logger.info("Starting EnvironmentScanner background task")
        await asyncio.to_thread(self._init_model)
        self._task = asyncio.create_task(self._scan_loop())
        
    def _init_model(self):
        if not self.model:
            logger.info("Loading YOLOv8 model for vision loop...")
            self.model = YOLO("yolov8n.pt")
            
    async def stop(self):
        self._running = False
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.flush_logs()
            
    async def _scan_loop(self):
        self.cap = await asyncio.to_thread(cv2.VideoCapture, 0)
        if not self.cap.isOpened():
            logger.error("Vision: No camera found!")
            self._running = False
            return
            
        await asyncio.to_thread(self.cap.set, 3, self.FRAME_WIDTH)
        await asyncio.to_thread(self.cap.set, 4, self.FRAME_HEIGHT)
        
        try:
            while self._running:
                start_time = time.time()
                
                success, img, results = await asyncio.to_thread(self._process_frame, self.cap)
                
                if success and results:
                    self.latest_frame = img.copy()  # Save frame for LLM tools
                    self._analyze_threats(results[0])
                    
                self._clean_memory()
                
                elapsed = time.time() - start_time
                sleep_time = max(0.1, 0.5 - elapsed)
                await asyncio.sleep(sleep_time)
        except Exception as e:
            logger.error(f"Vision loop error: {e}")
        finally:
            if self.cap:
                await asyncio.to_thread(self.cap.release)
                self.cap = None

    def _process_frame(self, cap):
        success, img = cap.read()
        if not success:
            return False, None, None
        results = self.model(img, stream=False, verbose=False)
        return True, img, results
        
    def _clean_memory(self):
        current_time = time.time()
        while self.memory and current_time - self.memory[0].timestamp > 10.0:
            self.memory.popleft()
            
    def _analyze_threats(self, result):
        current_time = time.time()
        person_count = 0
        
        log_entry = {
            "timestamp": current_time,
            "datetime": datetime.now().isoformat(),
            "detections": []
        }
        
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            obj_class = result.names[cls_id]
            
            bbox_area = (x2 - x1) * (y2 - y1)
            area_ratio = bbox_area / self.FRAME_AREA
            
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            is_center_x = (self.FRAME_WIDTH * 0.25) < center_x < (self.FRAME_WIDTH * 0.75)
            is_center_y = (self.FRAME_HEIGHT * 0.25) < center_y < (self.FRAME_HEIGHT * 0.75)
            is_center = is_center_x and is_center_y
            
            if obj_class in self.P0_CLASSES:
                priority = 0
            elif obj_class in self.P1_CLASSES:
                priority = 1
            else:
                priority = 2
                
            if obj_class == "person":
                person_count += 1
                
            det = Detection(current_time, obj_class, area_ratio, is_center, conf, priority)
            self.memory.append(det)
            
            # Add to log entry
            log_entry["detections"].append({
                "class": obj_class,
                "confidence": round(conf, 3),
                "area_ratio": round(area_ratio, 3),
                "is_center": is_center,
                "priority": priority
            })
            
            if priority == 2:
                # Informational only, log it
                if area_ratio < 0.1:
                    logger.debug(f"Vision [P2]: Small {obj_class} (Conf: {conf:.2f})")
                else:
                    logger.debug(f"Vision [P2]: {obj_class} at area {area_ratio:.2f}")
                continue
            
            # P0 Checks
            if priority == 0:
                if area_ratio > 0.15 and is_center:
                    self._trigger_alert(f"{obj_class.capitalize()} approaching ahead!", 0)
                elif area_ratio > 0.3:
                    self._trigger_alert(f"Large {obj_class} nearby!", 0)
                elif area_ratio > 0.1:
                    logger.info(f"Vision [Monitor]: {obj_class.capitalize()} spotted.")
                    
            # P1 Checks (non-person obstacles)
            elif priority == 1 and obj_class != "person":
                if area_ratio > 0.25 and is_center:
                    self._trigger_alert(f"Obstacle ahead: {obj_class}", 0)  # Upgraded to immediate due to proximity
                    
        # Buffer log entries to prevent SD card wear
        if log_entry["detections"]:
            self.log_buffer.append(json.dumps(log_entry) + "\n")
            if len(self.log_buffer) >= 50:
                self.flush_logs()
                
        # Escalation for persons (P1)
        if person_count >= 4:
            if person_count > 7:
                self._trigger_alert("High density area ahead.", 1)
            else:
                self._trigger_alert("Crowded area ahead.", 1)
                
    def _trigger_alert(self, message: str, priority: int):
        current_time = time.time()
        cooldown = self.P0_COOLDOWN if priority == 0 else self.P1_COOLDOWN
        last_time = self.last_alert_time.get(message, 0)
        
        if current_time - last_time > cooldown:
            logger.warning(f"VISION ALERT [{priority}]: {message}")
            if priority == 0:
                audio_manager.speak_critical(message)
            elif priority == 1:
                audio_manager.speak(message, AudioPriority.HIGH)
            self.last_alert_time[message] = current_time

    def flush_logs(self):
        if not self.log_buffer: return
        try:
            with open(self.log_file, "a") as f:
                f.writelines(self.log_buffer)
            self.log_buffer.clear()
        except Exception as e:
            logger.error(f"Failed to write vision log: {e}")

    def get_latest_frame_b64(self) -> str:
        if self.latest_frame is None:
            return ""
        ret, buf = cv2.imencode(".jpg", self.latest_frame)
        if ret:
            return base64.b64encode(buf).decode("utf-8")
        return ""

env_scanner = EnvironmentScanner()

if __name__ == "__main__":
    async def test_vision():
        # Setup logging to see everything during test
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        logger.setLevel(logging.DEBUG)
        
        print("Starting Audio Manager for alerts...")
        audio_manager.start()
        
        print("Starting Vision Subsystem...")
        scanner = EnvironmentScanner()
        await scanner.start()
        
        print("Vision scanner is now running independently! Point your camera at objects.")
        print("Press Ctrl+C to stop.")
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            await scanner.stop()
            audio_manager.stop()

    asyncio.run(test_vision())
