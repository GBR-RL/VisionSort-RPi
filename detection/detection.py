import gi
from gpiozero import Servo
from time import sleep
import threading
import lgpio
import time
import os
from collections import deque

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import cv2
import hailo


from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

# Servo Setup
SERVO_PIN = 12
servo = Servo(SERVO_PIN)
servo.value = None
sleep(1)
# Main loop (detection logic)
servo_thread = None

DELAY = 7

#detection queue and lock
detection_queue = deque()
queue_lock = threading.Lock()

# Function to control the servo (clockwise or counterclockwise)
def control_servo(label):  # Ensure that only one thread controls the servo at a time
        if label == "nut":
            print("Rotating to maximum clockwise position...")
            servo.max()
            sleep(0.15)
            # Stop Servo
            servo.value = None
            sleep(8)
            # Back to Home Position (CCW)
            servo.min()
            sleep(0.2)
            # Stop Servo
            servo.value = None
            sleep(1)


        elif label == "bolt":
            print("Rotating to maximum counter clockwise position...")
            servo.min()
            sleep(0.2)
            # Stop Servo
            servo.value = None
            sleep(8)
            # Back to Home Position (CCW)
            servo.max()
            sleep(0.2)
            # Stop Servo
            servo.value = None
            sleep(1)

def servo_actuation_worker():
    while True:
        current_time = time.time()
        with queue_lock:
            while detection_queue:
                label, timestamp = detection_queue[0]
                if current_time - timestamp >= DELAY:
                    detection_queue.popleft()
                    print(f"[Servo Queue] Actuating servo for: {label}")
                    threading.Thread(target=control_servo, args=(label,), daemon=True).start()
                    #print(f"[Servo Queue] Skipping actuation for: {label} (Test mode)")
                else:
                    break  # Wait for delay to be reached
        time.sleep(0.1)

# User-defined class
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()

        # Initialize state variables for debouncing
        self.detection_counter_nut = 0   # Count frames with detections of nut
        self.detection_counter_bolt = 0  # Count frames with detections of bolt

        self.last_queue_time = 0
        self.cooldown_period = 8       # Servo dwell time.

# Callback function

def app_callback(pad, info, user_data):
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK
    
    user_data.increment()
    string_to_print = f"Frame count: {user_data.get_count()}\n"
    format, width, height = get_caps_from_pad(pad)
    frame = None
    if user_data.use_frame and format and width and height:
        frame = get_numpy_from_buffer(buffer, format, width, height)
    
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    # Track if we've seen objects of interest this frame
    object_detected = False
    
    for detection in detections:
        label = detection.get_label()
        confidence = detection.get_confidence()

        if (label == "nut" or label == "bolt") and confidence > 0.8:
            object_detected = True
            break

    if object_detected:

        if label == "nut":
            user_data.detection_counter_nut += 1

        elif label == "bolt":
            user_data.detection_counter_bolt += 1
                
    # Start the servo control in a new thread for clockwise rotation
    current_time = time.time()
    if user_data.detection_counter_nut >= 15 and current_time - user_data.last_queue_time >= user_data.cooldown_period:
        with queue_lock:
            detection_queue.append(("nut", time.time()))
            print("[Detection Confirmed] Nut added to queue")
            print("[Queue Status]", list(detection_queue))
        user_data.detection_counter_nut = 0
        user_data.detection_counter_bolt = 0
        user_data.last_queue_time = current_time
            
    # Start the servo control in a new thread for counterclockwise rotation
    elif user_data.detection_counter_bolt >= 15 and current_time - user_data.last_queue_time >= user_data.cooldown_period:
        with queue_lock:
            detection_queue.append(("bolt", time.time()))
            print("[Detection Confirmed] Bolt added to queue")
            print("[Queue Status]", list(detection_queue))
        user_data.detection_counter_nut = 0
        user_data.detection_counter_bolt = 0
        user_data.last_queue_time = current_time


                
    if user_data.use_frame and frame is not None:
        cv2.putText(frame, f"Detections: {len(detections)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        user_data.set_frame(frame)
    
    #print(string_to_print)
    return Gst.PadProbeReturn.OK

class Conveyor:
    def __init__(self, step_pin=17, dir_pin=27, en_pin=22, speed=6.0):
        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.en_pin = en_pin
        self.speed = speed
        self.steps_per_meter = 1000
        self.pulse_interval = 1 / (speed * self.steps_per_meter)
        self.running = False

        # Open and set up GPIO
        self.h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self.h, self.step_pin)
        lgpio.gpio_claim_output(self.h, self.dir_pin)
        lgpio.gpio_claim_output(self.h, self.en_pin)
        lgpio.gpio_write(self.h, self.step_pin, 0)
        lgpio.gpio_write(self.h, self.dir_pin, 1)  # Forward direction
        lgpio.gpio_write(self.h, self.en_pin, 0)   # Enable motor

    def start(self):
        self.running = True
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while self.running:
            lgpio.gpio_write(self.h, self.step_pin, 1)
            time.sleep(self.pulse_interval / 2)
            lgpio.gpio_write(self.h, self.step_pin, 0)
            time.sleep(self.pulse_interval / 2)

    def stop(self):
        self.running = False
        time.sleep(0.1)
        lgpio.gpio_write(self.h, self.en_pin, 1)
        lgpio.gpiochip_close(self.h)



if __name__ == "__main__":
    conveyor = Conveyor()
    try:
        conveyor.start()
        user_data = user_app_callback_class()
        app = GStreamerDetectionApp(app_callback, user_data)
        threading.Thread(target=servo_actuation_worker, daemon=True).start()
        app.run()
        # Run continuously until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        conveyor.stop()
        servo.detach()
        servo.value = None
        sleep(1) 