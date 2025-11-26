# src/pulmoscan/inference/gradcam.py

import torch
import numpy as np
import cv2
from typing import Optional
from PIL import Image


class GradCAM:
    """
    GradCAM implementation compatible with TorchTBNet architecture
    """
    def __init__(self, model: torch.nn.Module, target_layer: Optional[torch.nn.Module] = None):
        self.model = model
        self.target_layer = target_layer
        self.activations = None
        self.gradients = None
        self._hook_handles = []
        self._grad_handle = None

    def _find_target_layer(self):
        """
        Find the last convolutional layer in the model
        For TorchTBNet, this should be conv3
        """
        if self.target_layer is not None:
            return self.target_layer

        # For TorchTBNet, explicitly look for conv3
        if hasattr(self.model, 'conv3'):
            return self.model.conv3
        
        # Fallback: search for last Conv2d layer
        conv_layers = []
        for name, module in self.model.named_modules():
            if isinstance(module, torch.nn.Conv2d):
                conv_layers.append((name, module))
        
        if conv_layers:
            print(f"Using layer: {conv_layers[-1][0]} for GradCAM")
            return conv_layers[-1][1]
        
        raise RuntimeError("No Conv2d layer found for GradCAM.")

    def _save_activation(self, module, input, output):
        """Hook to save forward pass activations"""
        self.activations = output.detach()

    def _save_gradient(self, module, grad_input, grad_output):
        """Hook to save backward pass gradients"""
        self.gradients = grad_output[0].detach()

    def _register_hooks(self, target_layer):
        """Register forward and backward hooks"""
        self.remove_hooks()
        
        # Forward hook
        forward_handle = target_layer.register_forward_hook(self._save_activation)
        self._hook_handles.append(forward_handle)
        
        # Backward hook
        backward_handle = target_layer.register_full_backward_hook(self._save_gradient)
        self._hook_handles.append(backward_handle)

    def remove_hooks(self):
        """Remove all registered hooks"""
        for handle in self._hook_handles:
            try:
                handle.remove()
            except:
                pass
        self._hook_handles.clear()
        
        self.activations = None
        self.gradients = None

    def __call__(self, x: torch.Tensor, target_class: Optional[int] = None):
        """
        Generate GradCAM heatmap
        
        Args:
            x: Input tensor [B, C, H, W]
            target_class: Target class index (None for predicted class)
            
        Returns:
            heatmap: numpy array [H, W] with values in [0, 1]
        """
        target_layer = self._find_target_layer()
        self._register_hooks(target_layer)

        # Ensure model is in eval mode but gradients are enabled
        self.model.eval()
        x.requires_grad_(True)
        
        # Forward pass
        logits = self.model(x)
        
        # Determine which class to use
        if target_class is None:
            if logits.shape[-1] == 1:
                # Binary classification with single output
                score = logits[:, 0]
            else:
                # Multi-class
                pred = torch.argmax(logits, dim=1)
                score = logits[0, pred]
        else:
            if logits.shape[-1] == 1:
                score = logits[:, 0]
            else:
                score = logits[0, target_class]

        # Backward pass
        self.model.zero_grad()
        score.backward(retain_graph=False)

        # Check if hooks captured data
        if self.gradients is None or self.activations is None:
            self.remove_hooks()
            raise RuntimeError("GradCAM failed to capture gradients or activations.")

        # Get gradients and activations
        grads = self.gradients  # [B, C, H, W]
        acts = self.activations  # [B, C, H, W]

        # Global average pooling of gradients
        weights = grads.mean(dim=(2, 3), keepdim=True)  # [B, C, 1, 1]

        # Weighted combination of activation maps
        cam = (acts * weights).sum(dim=1)  # [B, H, W]
        
        # Get first batch item
        cam = cam[0].cpu().numpy()  # [H, W]

        # Apply ReLU to focus on positive influences
        cam = np.maximum(cam, 0)
        
        # Normalize to [0, 1]
        if cam.max() > 0:
            cam = cam / cam.max()
        
        self.remove_hooks()
        return cam

    def __del__(self):
        """Cleanup hooks on deletion"""
        self.remove_hooks()


def overlay_heatmap_on_image(heatmap: np.ndarray, image_pil: Image.Image, alpha=0.4):
    """
    Overlay heatmap on original image
    
    Args:
        heatmap: numpy array [H, W] with values in [0, 1]
        image_pil: PIL Image
        alpha: transparency factor for heatmap
        
    Returns:
        overlayed image as numpy array [H, W, 3]
    """
    # Resize heatmap to match image size
    heatmap_resized = cv2.resize(heatmap, image_pil.size, interpolation=cv2.INTER_LINEAR)
    
    # Convert to uint8
    hm_uint8 = np.uint8(255 * heatmap_resized)
    
    # Apply colormap (JET: blue=low, red=high)
    hm_color = cv2.applyColorMap(hm_uint8, cv2.COLORMAP_JET)
    hm_color = cv2.cvtColor(hm_color, cv2.COLOR_BGR2RGB)

    # Convert PIL image to numpy array
    img_array = np.array(image_pil.convert("RGB"))
    
    # Blend images
    overlayed = cv2.addWeighted(img_array, 1 - alpha, hm_color, alpha, 0)
    
    return overlayed


def generate_heatmap_visualization(
    heatmap: np.ndarray,
    image_pil: Image.Image,
    save_path: str = None,
    alpha: float = 0.4,
    show_original: bool = True
):
    """
    Generate and optionally save heatmap visualization
    
    Args:
        heatmap: numpy array [H, W]
        image_pil: PIL Image
        save_path: path to save the visualization
        alpha: transparency of heatmap overlay
        show_original: if True, show side-by-side comparison
        
    Returns:
        visualization as numpy array
    """
    overlay = overlay_heatmap_on_image(heatmap, image_pil, alpha)
    
    if show_original:
        # Create side-by-side visualization
        original = np.array(image_pil.convert("RGB"))
        combined = np.hstack([original, overlay])
    else:
        combined = overlay
    
    if save_path:
        # Save as RGB image
        cv2.imwrite(save_path, cv2.cvtColor(combined, cv2.COLOR_RGB2BGR))
    
    return combined