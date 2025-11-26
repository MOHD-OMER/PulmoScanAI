# main.py
from fastapi import FastAPI, File, UploadFile, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import torch
import numpy as np
from PIL import Image
import io
import uuid
from datetime import datetime
import traceback

# --------------------------------------------------------
# APP INITIALIZATION
# --------------------------------------------------------
app = FastAPI(title="PulmoScan AI")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
HEATMAPS_DIR = BASE_DIR / "heatmaps"
REPORTS_DIR = BASE_DIR / "reports"
MODELS_DIR = BASE_DIR / "saved_models"
MODEL_PATH = MODELS_DIR / "tbnet_model_best.pth"

HEATMAPS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

print("🔍 BASE DIR:", BASE_DIR)
print("🔍 FRONTEND DIR:", FRONTEND_DIR)
print("🔍 HEATMAPS DIR:", HEATMAPS_DIR)
print("🔍 REPORTS DIR:", REPORTS_DIR)
print("🔍 MODEL PATH:", MODEL_PATH)

# --------------------------------------------------------
# MODEL LOADING
# --------------------------------------------------------
MODEL_LOADED = False
model = None
device = None

try:
    from pulmoscan.models.tbnet_model import TorchTBNet
    from pulmoscan.inference.inference_core import (
        predict_from_pil,
        predict_with_heatmap,
        load_model
    )
    from pulmoscan.utils.report_generator import generate_pdf_report

    if MODEL_PATH.exists():
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # instantiate and load using load_model helper where possible
        try:
            model, device = load_model(str(MODEL_PATH), device=device)
        except Exception:
            # fallback manual load (compat)
            model = TorchTBNet(num_classes=1).to(device)
            ckpt = torch.load(MODEL_PATH, map_location=device)
            if isinstance(ckpt, dict) and "model_state" in ckpt:
                model.load_state_dict(ckpt["model_state"])
            elif isinstance(ckpt, dict) and "state_dict" in ckpt:
                model.load_state_dict(ckpt["state_dict"])
            else:
                model.load_state_dict(ckpt)
            model.eval()

        MODEL_LOADED = True
        print(f"✅ Model loaded successfully on {device}")
    else:
        print(f"⚠️ Model missing: {MODEL_PATH}")
        print("   Mock mode enabled.")
except Exception as e:
    print(f"⚠️ Model import/load failed: {e}")
    print(traceback.format_exc())
    print("   Using mock predictions.")


# --------------------------------------------------------
# PRECAUTIONARY ADVICE DATABASE
# --------------------------------------------------------
PRECAUTIONARY_DB = {
    "TB_POSITIVE": {
        "recommendation": "⚠️ Tuberculosis detected. Please follow these precautionary steps and seek medical evaluation.",
        "precautions": [
            "Avoid close contact with others until medically cleared.",
            "Wear a well-fitting mask (N95/FFP2 if available) in public spaces.",
            "Cover mouth and nose when coughing or sneezing; dispose tissues safely.",
            "Keep living spaces well-ventilated (open windows when possible).",
            "Seek prompt evaluation from a healthcare professional or pulmonologist."
        ]
    },
    "TB_NEGATIVE": {
        "recommendation": "✅ No signs of tuberculosis detected. Continue maintaining a healthy lifestyle.",
        "precautions": [
            "Maintain a balanced and nutritious diet.",
            "Exercise regularly to strengthen immunity.",
            "Avoid smoking and exposure to polluted air.",
            "Schedule periodic medical checkups as appropriate.",
            "If you are in a high-risk group, continue to monitor symptoms."
        ]
    }
}


@app.get("/")
async def root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(404, "Frontend not found")


@app.post("/api/predict")
async def predict_endpoint(file: UploadFile = File(...)):
    """
    Main prediction endpoint.
    Returns:
      - TB Prediction (text)
      - raw_label (TB_POSITIVE/TB_NEGATIVE)
      - confidence % (string)
      - severity_score (0..1)
      - severity_category (Mild/Moderate/Severe)
      - precautionary_advice (recommendation + list)
      - heatmap_url
    """
    try:
        # Validate file
        if not file.content_type.startswith("image/"):
            raise HTTPException(400, "File must be an image")

        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        # default heatmap filename (may be overwritten by real func)
        heatmap_filename = f"heatmap_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

        # ------------------------------
        # REAL MODEL
        # ------------------------------
        if MODEL_LOADED and model is not None:
            try:
                result = predict_with_heatmap(
                    model=model,
                    device=device,
                    img=image,
                    heatmap_dir=str(HEATMAPS_DIR)
                )

                label = result["label"]  # TB_POSITIVE / TB_NEGATIVE
                prob = result["probability"]
                severity_score = result.get("severity_score", None)
                severity_category = result.get("severity_category", None)
                heatmap_filename = result["heatmap_filename"]

                print(f"✅ Real prediction: {label} ({prob:.4f}) sev={severity_score:.4f}")

            except Exception as e:
                print("❌ Prediction error:", e)
                print(traceback.format_exc())
                # fallback to safe defaults
                label = "TB_NEGATIVE"
                prob = 0.5
                severity_score = 0.5
                severity_category = "Moderate"

                # create a mock heatmap file so frontend has something
                mock_path = HEATMAPS_DIR / heatmap_filename
                image.resize((224, 224)).save(str(mock_path))

        else:
            # ------------------------------
            # MOCK MODEL (fallback)
            # ------------------------------
            label = "TB_POSITIVE" if np.random.random() > 0.5 else "TB_NEGATIVE"
            prob = float(round(np.random.uniform(0.75, 0.95), 4))
            # compute a mock logit -> severity (approx)
            mock_logit = np.log(prob / (1.0 - prob)) if (0 < prob < 1) else 0.0
            severity_score = float(1.0 / (1.0 + np.exp(-2.0 * mock_logit)))
            severity_category = ("Mild" if severity_score < 0.33 else
                                 "Moderate" if severity_score < 0.66 else "Severe")

            # Create a mock heatmap image
            mock_path = HEATMAPS_DIR / heatmap_filename
            img_small = image.resize((224, 224))
            img_small.save(str(mock_path))

            print(f"ℹ️ Mock prediction: {label} ({prob:.4f})")

        # Precautionary lookup
        precaution = PRECAUTIONARY_DB.get(label, PRECAUTIONARY_DB["TB_NEGATIVE"])

        return JSONResponse({
            "success": True,
            "prediction": "TB Detected" if label == "TB_POSITIVE" else "No TB Detected",
            "raw_label": label,
            "confidence": f"{prob * 100:.1f}%",
            "probability": prob,
            "severity_score": severity_score,
            "severity_category": severity_category,
            "precautionary_advice": precaution,
            "heatmap_filename": heatmap_filename,
            "heatmap_url": f"/heatmaps/{heatmap_filename}",
            "timestamp": datetime.now().isoformat(),
            "model_used": "TBNet" if MODEL_LOADED else "Mock Model"
        })

    except Exception as e:
        print("❌ Endpoint crash:", e)
        print(traceback.format_exc())
        raise HTTPException(500, f"Internal Error: {e}")


@app.post("/api/report")
async def generate_report_endpoint(payload: dict = Body(...)):
    """
    Generate a PDF report from a prediction payload.
    Expected payload keys (recommended):
      - patient_name (optional)
      - patient_id (optional)
      - prediction, raw_label, confidence, probability
      - severity_score, severity_category
      - precautionary_advice (dict: recommendation + precautions or medicines list)
      - heatmap_filename (the filename saved in /heatmaps)
      - original_filename (optional path or filename if available in static/images)
      - model_used (optional)
      - notes (optional)
    """
    try:
        # Basic validation
        required = ["raw_label", "prediction", "confidence", "probability", "heatmap_filename"]
        for r in required:
            if r not in payload:
                raise HTTPException(400, f"Missing required field: {r}")

        # Resolve image paths
        heatmap_fname = payload.get("heatmap_filename")
        heatmap_path = HEATMAPS_DIR / heatmap_fname if heatmap_fname else None

        original_fname = payload.get("original_filename")
        original_path = None
        if original_fname:
            cand = BASE_DIR / "static" / "images" / original_fname
            if cand.exists():
                original_path = str(cand)
            else:
                # also accept a full path
                if Path(original_fname).exists():
                    original_path = str(Path(original_fname))

        # Generate output pdf path
        pdf_name = f"report_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        out_pdf = REPORTS_DIR / pdf_name

        # Build precaution dict fallback
        prec = payload.get("precautionary_advice") or payload.get("treatment") or {}

        # Call generate_pdf_report
        generate_pdf_report(
            str(out_pdf),
            original_image_path=original_path,
            heatmap_image_path=str(heatmap_path) if heatmap_path and heatmap_path.exists() else None,
            patient_name=payload.get("patient_name"),
            patient_id=payload.get("patient_id"),
            prediction=payload.get("prediction"),
            raw_label=payload.get("raw_label"),
            confidence_str=payload.get("confidence"),
            probability=float(payload.get("probability", 0.0)),
            severity_score=payload.get("severity_score"),
            severity_category=payload.get("severity_category"),
            precautionary_advice=prec,
            model_used=payload.get("model_used"),
            notes=payload.get("notes"),
            timestamp=payload.get("timestamp")
        )

        return JSONResponse({
            "success": True,
            "pdf_filename": pdf_name,
            "pdf_url": f"/reports/{pdf_name}"
        })

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Report generation error:", e)
        print(traceback.format_exc())
        raise HTTPException(500, f"Report generation failed: {e}")


@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": MODEL_LOADED,
        "model_path": str(MODEL_PATH),
        "exists": MODEL_PATH.exists(),
        "device": str(device),
        "timestamp": datetime.now().isoformat()
    }


# --------------------------------------------------------
# STATIC MOUNTS
# --------------------------------------------------------
app.mount("/heatmaps", StaticFiles(directory=str(HEATMAPS_DIR)), name="heatmaps")
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# --------------------------------------------------------
# MAIN ENTRY
# --------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting PulmoScan AI at http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)