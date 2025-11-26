# pulmoscan/api/tbnet_api.py
"""
API utilities for TBNet inference
This can be used as an alternative to the main FastAPI app
"""

import torch
from typing import Dict, Tuple, Optional
from pathlib import Path
from PIL import Image
import io

from pulmoscan.models.tbnet_model import TorchTBNet
from pulmoscan.inference.inference_core import (
    load_model,
    predict_from_pil,
    generate_and_save_heatmap
)


class TBNetAPI:
    """
    High-level API wrapper for TBNet inference
    """
    
    def __init__(
        self,
        model_path: str,
        device: Optional[str] = None,
        heatmap_dir: str = "./heatmaps"
    ):
        """
        Initialize TBNet API
        
        Args:
            model_path: Path to trained model checkpoint
            device: Device to use ('cuda', 'cpu', or None for auto)
            heatmap_dir: Directory to save heatmaps
        """
        self.model_path = Path(model_path)
        self.heatmap_dir = Path(heatmap_dir)
        self.heatmap_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        # Load model
        self.model, self.device = load_model(str(self.model_path), self.device)
        print(f"✅ TBNet API initialized on {self.device}")
    
    def predict(
        self,
        image: Image.Image,
        threshold: float = 0.5,
        generate_heatmap: bool = True
    ) -> Dict:
        """
        Predict TB from image
        
        Args:
            image: PIL Image
            threshold: Classification threshold
            generate_heatmap: Whether to generate GradCAM heatmap
            
        Returns:
            Dictionary with prediction results
        """
        # Make prediction
        label, confidence = predict_from_pil(
            self.model,
            self.device,
            image,
            threshold
        )
        
        result = {
            "label": label,
            "confidence": float(confidence),
            "prediction": "TB Detected" if label == "TB_POSITIVE" else "No TB Detected",
            "confidence_percent": f"{confidence * 100:.1f}%"
        }
        
        # Generate heatmap if requested
        if generate_heatmap:
            heatmap_path = generate_and_save_heatmap(
                self.model,
                self.device,
                image,
                str(self.heatmap_dir)
            )
            result["heatmap_path"] = heatmap_path
        
        return result
    
    def predict_from_path(
        self,
        image_path: str,
        threshold: float = 0.5,
        generate_heatmap: bool = True
    ) -> Dict:
        """
        Predict TB from image file path
        
        Args:
            image_path: Path to image file
            threshold: Classification threshold
            generate_heatmap: Whether to generate GradCAM heatmap
            
        Returns:
            Dictionary with prediction results
        """
        image = Image.open(image_path).convert("RGB")
        return self.predict(image, threshold, generate_heatmap)
    
    def predict_from_bytes(
        self,
        image_bytes: bytes,
        threshold: float = 0.5,
        generate_heatmap: bool = True
    ) -> Dict:
        """
        Predict TB from image bytes
        
        Args:
            image_bytes: Image data as bytes
            threshold: Classification threshold
            generate_heatmap: Whether to generate GradCAM heatmap
            
        Returns:
            Dictionary with prediction results
        """
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return self.predict(image, threshold, generate_heatmap)
    
    def batch_predict(
        self,
        images: list,
        threshold: float = 0.5,
        generate_heatmaps: bool = False
    ) -> list:
        """
        Batch prediction on multiple images
        
        Args:
            images: List of PIL Images or image paths
            threshold: Classification threshold
            generate_heatmaps: Whether to generate heatmaps
            
        Returns:
            List of prediction dictionaries
        """
        results = []
        
        for img in images:
            if isinstance(img, (str, Path)):
                result = self.predict_from_path(str(img), threshold, generate_heatmaps)
            elif isinstance(img, Image.Image):
                result = self.predict(img, threshold, generate_heatmaps)
            else:
                raise TypeError(f"Unsupported image type: {type(img)}")
            
            results.append(result)
        
        return results
    
    def get_treatment_recommendation(self, prediction_label: str) -> Dict:
        """
        Get treatment recommendation based on prediction
        
        Args:
            prediction_label: "TB_POSITIVE" or "TB_NEGATIVE"
            
        Returns:
            Treatment recommendation dictionary
        """
        treatment_db = {
            "TB_POSITIVE": {
                "recommendation": "⚠️ TB detected. Immediate consultation with a pulmonologist is recommended.",
                "medicines": [
                    "Isoniazid (INH) - 5mg/kg daily",
                    "Rifampicin (RIF) - 10mg/kg daily",
                    "Pyrazinamide (PZA) - 25mg/kg daily",
                    "Ethambutol (EMB) - 15mg/kg daily",
                    "Note: This is a 6-month standard regimen. Consult a doctor for personalized treatment."
                ],
                "duration": "6 months (intensive phase: 2 months, continuation phase: 4 months)"
            },
            "TB_NEGATIVE": {
                "recommendation": "✅ No signs of TB detected. Routine health monitoring recommended.",
                "medicines": [
                    "No TB-specific medication needed",
                    "Maintain good hygiene and nutrition",
                    "Annual chest X-ray screening if high-risk population"
                ],
                "duration": "N/A"
            }
        }
        
        return treatment_db.get(prediction_label, treatment_db["TB_NEGATIVE"])


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="TBNet API Example")
    parser.add_argument("--model", required=True, help="Path to model checkpoint")
    parser.add_argument("--image", required=True, help="Path to chest X-ray image")
    parser.add_argument("--threshold", type=float, default=0.5, help="Classification threshold")
    parser.add_argument("--no-heatmap", action="store_true", help="Disable heatmap generation")
    
    args = parser.parse_args()
    
    # Initialize API
    api = TBNetAPI(args.model)
    
    # Make prediction
    result = api.predict_from_path(
        args.image,
        threshold=args.threshold,
        generate_heatmap=not args.no_heatmap
    )
    
    # Display results
    print("\n" + "="*60)
    print("Prediction Results")
    print("="*60)
    print(f"Prediction: {result['prediction']}")
    print(f"Confidence: {result['confidence_percent']}")
    
    if "heatmap_path" in result:
        print(f"Heatmap saved to: {result['heatmap_path']}")
    
    # Get treatment recommendation
    treatment = api.get_treatment_recommendation(result['label'])
    print(f"\nRecommendation: {treatment['recommendation']}")
    print("\nMedications:")
    for med in treatment['medicines']:
        print(f"  - {med}")
    print("="*60)