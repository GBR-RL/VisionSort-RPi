import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import hailo
from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

# Named Pipe (FIFO) Path
FIFO_PATH = "/tmp/detection_fifo"

# Ensure the named pipe exists
if not os.path.exists(FIFO_PATH):
    os.mkfifo(FIFO_PATH)

# Class Mapping
CLASS_MAPPING = {
    "bolt": "bolt",
    "nut": "nut",
    "screw_body": "bolt",
    "screw_head": "bolt"
}

class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()

def app_callback(pad, info, user_data):
    """Callback function that processes detections and writes to FIFO."""
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    print(f"Frame count: {user_data.get_count()}")

    # Get detections
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    detected_objects = []
    for detection in detections:
        label = detection.get_label()
        mapped_label = CLASS_MAPPING.get(label, None)
        if mapped_label:
            detected_objects.append(mapped_label)

    if detected_objects:
        with open(FIFO_PATH, "w") as fifo:
            for obj in detected_objects:
                print(f"Detected: {obj}. Sending to sorter.")
                fifo.write(obj + "\n")

    return Gst.PadProbeReturn.OK

if __name__ == "__main__":
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()
