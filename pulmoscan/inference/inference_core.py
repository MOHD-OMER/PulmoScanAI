# pulmoscan/inference/inference_core.py
import os
import uuid
import cv2
import numpy as np
import torch
from PIL import Image
from typing import Tuple, Dict
from torchvision import transforms

from pulmoscan.models.tbnet_model import TorchTBNet
from pulmoscan.inference.gradcam import GradCAM, overlay_heatmap_on_image


DEFAULT_SIZE = 224

INFER_TRANSFORM = transforms.Compose([
    transforms.Resize((DEFAULT_SIZE, DEFAULT_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# ----------------------------------------------------------
#  MODEL LOADING
# ----------------------------------------------------------
def load_model(path: str, device: torch.device = None) -> Tuple[TorchTBNet, torch.device]:
    """
    Load the TBNet model from checkpoint.
    
    Args:
        path: Path to model checkpoint file
        device: Target device (defaults to CUDA if available, else CPU)
    
    Returns:
        Tuple of (model, device)
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = TorchTBNet().to(device)

    ckpt = torch.load(path, map_location=device)
    
    # Handle both direct state dict and wrapped checkpoint formats
    if isinstance(ckpt, dict) and "model_state" in ckpt:
        model.load_state_dict(ckpt["model_state"])
    else:
        model.load_state_dict(ckpt)

    model.eval()
    return model, device


# ----------------------------------------------------------
# BASIC PREDICTION (returns label + probability)
# ----------------------------------------------------------
def predict_from_pil(model: TorchTBNet, device: torch.device, img: Image.Image) -> Tuple[str, float]:
    """
    Perform basic prediction on a PIL Image.
    
    Args:
        model: Loaded TBNet model
        device: Torch device
        img: PIL Image to analyze
    
    Returns:
        Tuple of (label, probability)
        label: "TB_POSITIVE" or "TB_NEGATIVE"
        probability: Float between 0 and 1
    """
    x = INFER_TRANSFORM(img).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(x)  # shape: (B, 1)
        
        # Handle different output shapes
        if logits.dim() == 1:
            logit_value = logits[0]
        else:
            logit_value = logits[0, 0]
        
        # Binary single-logit -> sigmoid for probability
        prob = torch.sigmoid(logit_value).item()

    label = "TB_POSITIVE" if prob >= 0.5 else "TB_NEGATIVE"
    return label, float(prob)


# ----------------------------------------------------------
# LOGIT-BASED SEVERITY (S2): severity_score = sigmoid(logit * 2)
# ----------------------------------------------------------
def _compute_severity_from_logit(logit_tensor: torch.Tensor) -> Tuple[float, str]:
    """
    Compute severity score and category from model logit using S2 scheme.
    
    S2 Formula: severity_score = sigmoid(logit × 2)
    
    Category thresholds:
        < 0.33  -> Mild
        0.33-0.66 -> Moderate
        > 0.66  -> Severe
    
    Args:
        logit_tensor: Scalar PyTorch tensor containing the raw logit value
    
    Returns:
        Tuple of (severity_score, category)
        severity_score: Float between 0 and 1
        category: "Mild", "Moderate", or "Severe"
    """
    with torch.no_grad():
        # Scale logit by 2 for sensitivity
        scaled = logit_tensor * 2.0
        severity_score = torch.sigmoid(scaled).item()

    # Map continuous score to categorical severity
    if severity_score < 0.33:
        category = "Mild"
    elif severity_score < 0.66:
        category = "Moderate"
    else:
        category = "Severe"

    return float(severity_score), category


# ----------------------------------------------------------
# HEATMAP + PREDICTION IN ONE FUNCTION (API USES THIS)
# ----------------------------------------------------------
def predict_with_heatmap(
    model: TorchTBNet,
    device: torch.device,
    img: Image.Image,
    heatmap_dir: str
) -> Dict:
    """
    MAIN function used by API.
    Performs prediction, generates severity scores, and creates GradCAM heatmap.
    
    Args:
        model: Loaded TBNet model
        device: Torch device
        img: PIL Image to analyze
        heatmap_dir: Directory to save heatmap overlay
    
    Returns:
        Dictionary containing:
            - label: "TB_POSITIVE" or "TB_NEGATIVE"
            - probability: Classification probability (0-1)
            - severity_score: Severity score (0-1)
            - severity_category: "Mild", "Moderate", or "Severe"
            - heatmap_path: Full path to saved heatmap image
            - heatmap_filename: Filename of saved heatmap
    """
    os.makedirs(heatmap_dir, exist_ok=True)

    # ---------------------------
    # Forward pass for prediction
    # ---------------------------
    x = INFER_TRANSFORM(img).unsqueeze(0).to(device)  # (1, C, H, W)
    model.eval()

    # Get logits (needed for both probability and severity)
    with torch.no_grad():
        logits = model(x)  # expect shape (1, 1)
    
    # Handle different output shapes
    if logits.dim() == 1:
        logit_scalar = logits[0]
    else:
        logit_scalar = logits[0, 0]

    # Classification probability (sigmoid of logit)
    prob = float(torch.sigmoid(logit_scalar).item())
    label = "TB_POSITIVE" if prob >= 0.5 else "TB_NEGATIVE"

    # Severity score via S2 scheme
    severity_score, severity_category = _compute_severity_from_logit(logit_scalar)

    # ---------------------------
    # GradCAM using preferred layer (conv3 if available)
    # ---------------------------
    overlay = None
    try:
        # Target the third convolutional layer for best visualization
        if hasattr(model, "conv3"):
            target_layer = model.conv3
        else:
            # Fallback to any available conv layer
            target_layer = None

        cam = GradCAM(model, target_layer)
        heatmap = cam(x)  # returns 2D numpy array [H, W] normalized 0..1
        overlay = overlay_heatmap_on_image(heatmap, img)
        cam.remove_hooks()
        
    except Exception as e:
        # On GradCAM failure, create a neutral overlay
        print(f"GradCAM generation failed: {e}. Creating fallback overlay.")
        try:
            # Create blank heatmap for overlay
            blank_heatmap = np.zeros((DEFAULT_SIZE, DEFAULT_SIZE), dtype=np.float32)
            overlay = overlay_heatmap_on_image(blank_heatmap, img)
        except Exception:
            # Final fallback: use original resized image
            img_resized = img.resize((DEFAULT_SIZE, DEFAULT_SIZE))
            overlay = cv2.cvtColor(np.array(img_resized), cv2.COLOR_RGB2BGR)

    # ---------------------------
    # Save heatmap overlay
    # ---------------------------
    file_id = uuid.uuid4().hex
    heatmap_name = f"heatmap_{file_id}.jpg"
    out_path = os.path.join(heatmap_dir, heatmap_name)

    # Save the overlay image
    try:
        # overlay should be RGB numpy array, convert to BGR for OpenCV
        if overlay is not None:
            cv2.imwrite(out_path, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        else:
            # Emergency fallback
            img_array = np.array(img.resize((DEFAULT_SIZE, DEFAULT_SIZE)))
            cv2.imwrite(out_path, cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))
    except Exception as e:
        print(f"Image save error: {e}. Attempting alternative save.")
        # Try saving without color conversion
        try:
            cv2.imwrite(out_path, overlay)
        except Exception:
            # Last resort: save as PIL
            img.resize((DEFAULT_SIZE, DEFAULT_SIZE)).save(out_path)

    return {
        "label": label,
        "probability": prob,
        "severity_score": severity_score,
        "severity_category": severity_category,
        "heatmap_path": out_path,
        "heatmap_filename": heatmap_name
    }


# ----------------------------------------------------------
# Standalone: generate and save heatmap only
# ----------------------------------------------------------
def generate_and_save_heatmap(
    model: TorchTBNet, 
    device: torch.device, 
    img: Image.Image, 
    out_dir: str, 
    basename: str = None
) -> str:
    """
    Backwards-compatible helper function.
    Generates heatmap and returns path to saved file.
    
    Args:
        model: Loaded TBNet model
        device: Torch device
        img: PIL Image to analyze
        out_dir: Directory to save heatmap
        basename: Optional custom basename (not used, kept for compatibility)
    
    Returns:
        Path to saved heatmap file
    """
    res = predict_with_heatmap(model, device, img, out_dir)
    return res["heatmap_path"]