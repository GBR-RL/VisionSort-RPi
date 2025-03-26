import RPi.GPIO as GPIO
import time
import threading
import os

FIFO_PATH = "/tmp/detection_fifo"  # FIFO path for communication

class ConveyorBelt:
    def __init__(self, step_pin=17, dir_pin=27, max_speed=10.0):
        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.max_speed = max_speed
        self.running = False
        self.speed = 0.5  # Default speed in m/s (starts at 0.5 m/s)
        self.pulse_interval = 1 / (self.speed * 100)  # Initial pulse interval
        self.lock = threading.Lock()  # For thread-safe speed updates
        self.direction = GPIO.HIGH  # Fixed direction (CLOCKWISE)
        
        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.step_pin, GPIO.OUT)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        GPIO.output(self.step_pin, GPIO.LOW)
        GPIO.output(self.dir_pin, self.direction)

        # Create FIFO for speed updates
        if not os.path.exists(FIFO_PATH):
            os.mkfifo(FIFO_PATH)

    def set_speed(self, speed):
        """Set the speed of the conveyor belt (in m/s)."""
        with self.lock:
            if speed < 0.5 or speed > self.max_speed:
                print(f"Speed must be between 0.5 m/s and {self.max_speed} m/s.")
                return
            self.speed = speed
            self.pulse_interval = 1 / (self.speed * 100)  # Calculate the pulse interval based on speed
            print(f"Conveyor speed set to {self.speed:.2f} m/s.")
            self.send_speed_to_fifo()

    def adjust_speed(self, step):
        """Adjust the speed in 1 m/s increments."""
        new_speed = self.speed + step
        if 0.5 <= new_speed <= self.max_speed:
            self.set_speed(new_speed)
        else:
            print(f"Speed adjustment out of range. Speed must be between 0.5 m/s and {self.max_speed} m/s.")

    def send_speed_to_fifo(self):
        """Send the current speed to the FIFO."""
        with open(FIFO_PATH, "w") as fifo:
            fifo.write(f"Speed: {self.speed}\n")

    def start(self):
        """Start the conveyor belt by sending step pulses continuously."""
        if not self.running:
            print("Starting conveyor belt...")
            self.running = True
            threading.Thread(target=self.send_steps, daemon=True).start()
        else:
            print("Conveyor belt is already running.")

    def stop(self):
        """Stop the conveyor belt."""
        if self.running:
            print("Stopping conveyor belt...")
            self.running = False
        else:
            print("Conveyor belt is already stopped.")

    def send_steps(self):
        """Generate step pulses to control motor movement continuously."""
        while self.running:
            # Send steps continuously at the current speed
            for _ in range(int(self.speed * 1000)):  # Steps per second (speed * 1000)
                GPIO.output(self.step_pin, GPIO.HIGH)
                time.sleep(0.0001)  # Pulse width (short time)
                GPIO.output(self.step_pin, GPIO.LOW)
                time.sleep(0.0001)  # Pulse width (short time)

    def cleanup(self):
        """Clean up GPIO pins."""
        self.stop()
        GPIO.cleanup()


def control_loop(conveyor):
    """Listen for user input to control the conveyor belt."""
    print("Controls: 's' - Start, 'e' - Stop, '+' - Increase Speed (1 m/s), '-' - Decrease Speed (1 m/s), 'q' - Quit")
    while True:
        command = input("Enter command: ").strip().lower()
        if command == "s":
            conveyor.start()
        elif command == "e":
            conveyor.stop()
        elif command == "+":
            conveyor.adjust_speed(1)  # Increase speed by 1 m/s
        elif command == "-":
            conveyor.adjust_speed(-1)  # Decrease speed by 1 m/s
        elif command == "q":
            conveyor.cleanup()
            print("Exiting conveyor system.")
            break
        else:
            print("Invalid command. Try again.")


# Example usage:
if __name__ == "__main__":
    conveyor = ConveyorBelt()
    try:
        control_loop(conveyor)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        conveyor.cleanup()
