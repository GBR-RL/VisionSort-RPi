import multiprocessing
import os
import time
from detection import start_detection  # Import the start_detection function
from sorter import Sorter
from conveyor import ConveyorBelt

# Named Pipe (FIFO) Path
FIFO_PATH = "/tmp/detection_fifo"

def start_sorter(conveyor):
    """Start sorter process and read from FIFO."""
    sorter = Sorter(conveyor=conveyor)
    sorter.process_detections()

def start_conveyor():
    """Start the conveyor belt process."""
    conveyor = ConveyorBelt()
    conveyor.start()
    return conveyor

if __name__ == "__main__":
    # Ensure the named pipe (FIFO) exists
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)

    # Start conveyor process
    conveyor = start_conveyor()

    # Create processes for detection and sorter
    detection_process = multiprocessing.Process(target=start_detection)
    sorter_process = multiprocessing.Process(target=start_sorter, args=(conveyor,))

    # Start the detection and sorter processes
    detection_process.start()
    sorter_process.start()

    try:
        while True:
            time.sleep(1)  # Keep the main script running
    except KeyboardInterrupt:
        print("\nStopping all processes...")
        # Gracefully terminate the detection, sorter, and conveyor processes
        detection_process.terminate()
        sorter_process.terminate()
        conveyor.stop()
        detection_process.join()
        sorter_process.join()
        print("Processes stopped successfully.")
