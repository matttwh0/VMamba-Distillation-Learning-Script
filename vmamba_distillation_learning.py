# -*- coding: utf-8 -*-
"""VMamba Distillation Learning.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1NJYBLtAd16MSdxy-IPQ8Xr9jhFbrHZUA

Utilized memory by reducing dataset image size to 16x16, batch size to 1

this did heavily impact accuracy, but at least I was able to run the distillation model
"""

# CREATE TRAINING AND VALIDATION DATASETS
import kagglehub
import os
import shutil
from sklearn.model_selection import train_test_split

# Download the dataset
path = kagglehub.dataset_download("mukaffimoin/potato-diseases-datasets")
print("Path to dataset files:", path)  # Should be: /root/.cache/kagglehub/datasets/mukaffimoin/potato-diseases-datasets/versions/3

# Define source and destination paths
source_dir = os.path.join(path, '')  # Update if needed based on your dataset structure
output_dir = '/content'
train_dir = os.path.join(output_dir, 'train')
test_dir = os.path.join(output_dir, 'val')

# Create train and test directories
os.makedirs(train_dir, exist_ok=True)
os.makedirs(test_dir, exist_ok=True)

# Get category folders
categories = os.listdir(source_dir)

# Loop over each category to split data
for category in categories:
    # Path for each category
    category_path = os.path.join(source_dir, category)
    if os.path.isdir(category_path):  # Confirm it’s a folder
        images = os.listdir(category_path)

        # Split data into train and test sets (80-20 split)
        train_images, test_images = train_test_split(images, test_size=0.2, random_state=42)

        # Create directories for each category in train and test folders
        os.makedirs(os.path.join(train_dir, category), exist_ok=True)
        os.makedirs(os.path.join(test_dir, category), exist_ok=True)

        # Move files to train and test directories
        for image in train_images:
            shutil.copy(os.path.join(category_path, image), os.path.join(train_dir, category, image))
        for image in test_images:
            shutil.copy(os.path.join(category_path, image), os.path.join(test_dir, category, image))

print("Data split into training and testing sets successfully.")

# Step 1: Clone the VMamba repository from GitHub.
# (Run this cell only once; for example, in a Colab notebook you can use the !git command.)
!git clone https://github.com/MzeroMiko/VMamba.git

!ls -R VMamba/classification/configs/vssm

# Commented out IPython magic to ensure Python compatibility.
#LOAD TEACHER AND STUDENT MODEL
# %cd VMamba
!pip install -r requirements.txt

import sys
import torch

# Add VMamba to Python path
sys.path.append('.')

# ===============================
# 2) Imports from VMamba
# ===============================
from classification.config import get_config
from classification.models import build_model

# ===============================
# 3) Fake single-GPU "distributed"
#    so main scripts won't complain
# ===============================
import os
os.environ["RANK"] = "0"
os.environ["WORLD_SIZE"] = "1"
os.environ["LOCAL_RANK"] = "0"

# ===============================
# 4) Define two DummyArgs classes
#    - one for the small model
#    - one for the tiny model
# ===============================
class ArgsSmall:
    # Path to the "small" YAML config
    # Adjust if the actual file name differs
    cfg = "classification/configs/vssm/vmambav2_small_224.yaml"

    # You can override config keys via opts if needed.
    # For example: ["MODEL.PRETRAINED", "/content/vmambav2_small_224.pth"]
    opts = []

    batch_size = None
    data_path = ''
    zip = False
    cache_mode = 'part'
    pretrained = ''
    resume = ''
    accumulation_steps = None
    use_checkpoint = False
    disable_amp = False
    output = ''
    tag = 'default'
    eval = False
    throughput = False
    traincost = False
    enable_amp = True
    fused_layernorm = False
    optim = None

class ArgsTiny:
    # Path to the "tiny" YAML config
    cfg = "classification/configs/vssm/vmambav2_tiny_224.yaml"
    opts = []
    batch_size = None
    data_path = ''
    zip = False
    cache_mode = 'part'
    pretrained = ''
    resume = ''
    accumulation_steps = None
    use_checkpoint = False
    disable_amp = False
    output = ''
    tag = 'default'
    eval = False
    throughput = False
    traincost = False
    enable_amp = True
    fused_layernorm = False
    optim = None

# ===============================
# 5) Load the configs
# ===============================
args_small = ArgsSmall()
args_tiny  = ArgsTiny()

config_small = get_config(args_small)
config_tiny  = get_config(args_tiny)

print("Teacher Model Name:", config_small.MODEL.NAME)
print("Student Model Name:", config_tiny.MODEL.NAME)

# ===============================
# 6) Build both models
# ===============================
teacher_model = build_model(config_small)
student_model = build_model(config_tiny)

# ===============================
# 7) Move them to GPU (if available)
# ===============================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
teacher_model.to(device)
student_model.to(device)

teacher_model.eval()
student_model.eval()

print("Teacher model (Small) loaded on device:", device)
print(teacher_model)

print("Student model (Tiny) loaded on device:", device)
print(student_model)

#PREPARE DATASET
import torch
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader

# Path to your dataset (already split into train/val folders)
train_dir = "/content/train"
val_dir   = "/content/val"

# Basic transforms (resize to 224, convert to tensor, optionally normalize)
transform = transforms.Compose([
    transforms.Resize((16, 16)),
    transforms.ToTensor(),
    # Example normalization if desired:
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225])
])

train_dataset = torchvision.datasets.ImageFolder(root=train_dir, transform=transform)
val_dataset   = torchvision.datasets.ImageFolder(root=val_dir,   transform=transform)

train_loader = DataLoader(train_dataset, batch_size=1, shuffle=True,  num_workers=2)
val_loader   = DataLoader(val_dataset,   batch_size=1, shuffle=False, num_workers=2)

print(f"Train samples: {len(train_dataset)}, Val samples: {len(val_dataset)}")
print("Classes:", train_dataset.classes)

#DEFINE DISTILLATION LOSS FUNCTION
import torch.nn.functional as F

def distillation_loss(
    student_logits, teacher_logits, labels,
    alpha=0.5, temperature=4.0
):
    """
    student_logits: [batch_size, num_classes]
    teacher_logits: [batch_size, num_classes]
    labels: [batch_size] with class indices
    alpha: weight for the ground truth CE vs. distillation KL
    temperature: temperature for softening the teacher’s and student’s logits
    """
    # 1) Standard cross-entropy with ground truth
    ce_loss = F.cross_entropy(student_logits, labels)

    # 2) Distillation loss: KL divergence between teacher & student distributions
    #    We'll soften both teacher & student with T
    #    Convert logits to log probabilities for KL
    student_soft = F.log_softmax(student_logits / temperature, dim=1)
    teacher_soft = F.softmax(teacher_logits / temperature, dim=1)
    kl_loss = F.kl_div(student_soft, teacher_soft, reduction='batchmean') * (temperature ** 2)

    # 3) Combine
    loss = alpha * ce_loss + (1 - alpha) * kl_loss
    return loss

#RUN MODEL
for param in teacher_model.parameters():
    param.requires_grad = False

# A simple Adam optimizer for the student
optimizer = torch.optim.Adam(student_model.parameters(), lr=1e-4)

def train_distillation(num_epochs=10, alpha=0.5, temperature=4.0):
    student_model.train()
    teacher_model.eval()  # Teacher stays in eval mode

    for epoch in range(num_epochs):
        running_loss = 0.0
        correct = 0
        total = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            # Forward pass teacher & student
            with torch.no_grad():
                teacher_outputs = teacher_model(images)
            student_outputs = student_model(images)

            # Distillation loss
            loss = distillation_loss(
                student_outputs, teacher_outputs, labels,
                alpha=alpha, temperature=temperature
            )

            # Backprop
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # Track stats
            running_loss += loss.item() * images.size(0)
            _, predicted = student_outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)

        epoch_loss = running_loss / total
        epoch_acc = 100.0 * correct / total

        print(f"Epoch [{epoch+1}/{num_epochs}] - Loss: {epoch_loss:.4f}, "
              f"Train Accuracy: {epoch_acc:.2f}%")

    print("Distillation training complete!")

train_distillation(num_epochs=10, alpha=0.5, temperature=4.0)

def evaluate(model, loader):
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            _, predicted = outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)
    return 100.0 * correct / total

student_model.eval()
val_acc = evaluate(student_model, val_loader)
print(f"Final Student Model Accuracy on Validation Set: {val_acc:.2f}%")