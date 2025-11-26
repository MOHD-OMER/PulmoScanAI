"""
PulmoScan AI - Tuberculosis Detection System
"""

__version__ = "1.0.0"
__author__ = "PulmoScan AI Team"

from pulmoscan.models.tbnet_model import TorchTBNet
from pulmoscan.inference.inference_core import (
    load_model,
    predict_from_pil,
    generate_and_save_heatmap,
    predict_with_heatmap
)
from pulmoscan.inference.gradcam import GradCAM, overlay_heatmap_on_image

__all__ = [
    "TorchTBNet",
    "load_model",
    "predict_from_pil",
    "generate_and_save_heatmap",
    "predict_with_heatmap",
    "GradCAM",
    "overlay_heatmap_on_image"
]