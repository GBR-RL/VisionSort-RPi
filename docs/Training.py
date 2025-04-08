import os
from ultralytics import YOLO


# Paths
DATA_YAML = "/jupyterlab/BOLTSNUTS/nuts-3/data.yaml"  # Path to your updated dataset.yaml file
MODEL = "/jupyterlab/yolov8n.pt"  # Pretrained YOLOv8 model
EPOCHS = 100  # Number of epochs
IMGSZ = 640  # Image size
BATCH_SIZE = 32  # Batch size
OUTPUT_DIR = "BOLTSandNutsResults"  # Directory to save training results

# Create YOLO model instance
model = YOLO(MODEL)

# Train the model
results = model.train(
    data=DATA_YAML,
    epochs=EPOCHS,
    imgsz=IMGSZ,
    batch=BATCH_SIZE,
    project=OUTPUT_DIR,
    name="Nuts_Bolts_sorting",
    device=0  # Use GPU (set to 'cpu' if using CPU)
)

# Run testing using the test dataset
test_results = model.val(
    data=DATA_YAML,
    split="test",  # Specify the test split
    imgsz=IMGSZ,
    batch=BATCH_SIZE
)

# Display training stats
print("Training Completed!")
print("Results Summary:")
print(results)

# Display testing stats
print("Testing Completed!")
print("Test Results Summary:")
print(test_results)
