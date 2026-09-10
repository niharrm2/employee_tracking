"""
detectors/fire_smoke.py — Fire & Smoke Detection
==================================================
⚠️  SAFETY DISCLAIMER — READ THIS BEFORE ENABLING  ⚠️
This module is a supplementary EARLY-WARNING signal ONLY.
It is NOT a certified fire alarm and must NOT replace physical
fire detection hardware (smoke detectors, sprinkler systems, etc.).
False positives (e.g. orange lighting, steamy kitchens) and false
negatives are both possible. Always maintain certified fire safety
equipment as the primary detection system.

Default implementation: OpenCV HSV colour heuristics.
  - Fire:  Orange/red/yellow high-saturation regions above a minimum area.
  - Smoke: Large low-saturation, low-edge-density grey/white haze regions.

Extension point: Set fire_smoke.model_path in config.yaml to a trained
YOLOv8 .pt file to swap in a more reliable model (e.g. fine-tuned on a
public fire/smoke dataset from Roboflow Universe). The code will load
the YOLOv8 model automatically when model_path is not None.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heuristic-based detector (default, no model download required)
# ---------------------------------------------------------------------------

# HSV colour ranges for fire-like pixels (orange / red / yellow flames)
# Hue is 0-179 in OpenCV; fire typically spans ~0-30 (red-orange-yellow)
FIRE_HSV_LOWER1 = np.array([0,   120, 120])   # red-orange low
FIRE_HSV_UPPER1 = np.array([30,  255, 255])   # orange-yellow high
FIRE_HSV_LOWER2 = np.array([160, 120, 120])   # wrapped-around red
FIRE_HSV_UPPER2 = np.array([179, 255, 255])


def detect_fire_heuristic(
    frame: np.ndarray,
    min_area_ratio: float = 0.01,
) -> Tuple[bool, float]:
    """
    HSV colour heuristic for fire detection.

    NOTE: High false-positive rate in environments with orange/red
    lighting, warm-toned decor, or direct sunlight. Tune min_area_ratio
    upward to reduce false positives in those environments.

    Parameters
    ----------
    frame : np.ndarray
        BGR image.
    min_area_ratio : float
        Fraction of total frame area that must contain fire-like pixels
        before an alert is raised (default 1%).

    Returns
    -------
    (detected: bool, confidence: float)
        confidence is the fire-pixel area ratio (0–1), not a model score.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, FIRE_HSV_LOWER1, FIRE_HSV_UPPER1)
    mask2 = cv2.inRange(hsv, FIRE_HSV_LOWER2, FIRE_HSV_UPPER2)
    fire_mask = cv2.bitwise_or(mask1, mask2)

    # Morphological cleanup to remove noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_OPEN, kernel)
    fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_DILATE, kernel)

    fire_px = int(np.sum(fire_mask > 0))
    total_px = frame.shape[0] * frame.shape[1]
    ratio = fire_px / total_px

    detected = ratio >= min_area_ratio
    return detected, round(ratio, 4)


def detect_smoke_heuristic(
    frame: np.ndarray,
    min_area_ratio: float = 0.05,
) -> Tuple[bool, float]:
    """
    Low-saturation / low-edge-density heuristic for smoke detection.

    Smoke typically appears as a large, greyed-out hazy region with:
      - Low colour saturation (HSV S channel)
      - Low edge density (smoke softens edges)
      - Moderate brightness (not pitch black, not over-exposed)

    NOTE: This heuristic will raise false alerts in:
      - Foggy/misty outdoor cameras
      - Steamy kitchen areas
      - Overcast backlit windows
    It is a rough signal only — combine with physical smoke detectors.

    Parameters
    ----------
    frame : np.ndarray
        BGR image.
    min_area_ratio : float
        Fraction of frame area that must be "hazy" to raise alert.

    Returns
    -------
    (detected: bool, confidence: float)
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    s_channel = hsv[:, :, 1]
    v_channel = hsv[:, :, 2]

    # Low saturation (grey/white) + moderate brightness
    low_sat_mask = (s_channel < 40) & (v_channel > 80) & (v_channel < 240)

    # Low edge density in those regions — smoke blurs contours
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    # Dilate edges so low-edge zones are larger than single pixels
    kernel = np.ones((15, 15), np.uint8)
    edge_dilated = cv2.dilate(edges, kernel)
    no_edge_mask = edge_dilated == 0

    smoke_mask = low_sat_mask & no_edge_mask
    smoke_px = int(np.sum(smoke_mask))
    total_px = frame.shape[0] * frame.shape[1]
    ratio = smoke_px / total_px

    detected = ratio >= min_area_ratio
    return detected, round(ratio, 4)


# ---------------------------------------------------------------------------
# YOLOv8 model-based detector (optional — activated via config model_path)
# ---------------------------------------------------------------------------

class YOLOFireSmokeDetector:
    """
    Optional YOLOv8-based fire/smoke detector.
    Used when a trained .pt model path is provided in config.

    To activate: set fire_smoke.model_path in config.yaml to a
    fine-tuned YOLOv8n or YOLOv8s checkpoint trained on fire/smoke data.
    Public datasets are available on Roboflow Universe and Kaggle.

    This class is only instantiated when model_path is set — otherwise
    the heuristic functions above are used.
    """

    def __init__(self, model_path: str, confidence_threshold: float = 0.4):
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError("ultralytics required for YOLOv8 fire/smoke detection.")

        logger.info("Loading custom fire/smoke YOLOv8 model from %s ...", model_path)
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        logger.info("Fire/smoke YOLOv8 model ready.")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run fire/smoke detection using the trained YOLOv8 model.

        Returns list of dicts: {alert_type, confidence, bbox}
        """
        if frame is None or frame.size == 0:
            return []
        try:
            results = self.model(
                frame, device="cpu",
                conf=self.confidence_threshold, verbose=False
            )
        except Exception as exc:
            logger.warning("Fire/smoke YOLOv8 inference error: %s", exc)
            return []

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = self.model.names.get(cls_id, "unknown").lower()
                alert_type = None
                if "fire" in label:
                    alert_type = "fire"
                elif "smoke" in label:
                    alert_type = "smoke"
                else:
                    continue
                conf = float(box.conf[0])
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                detections.append({
                    "alert_type": alert_type,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                })
        return detections


# ---------------------------------------------------------------------------
# Unified interface used by pipeline.py
# ---------------------------------------------------------------------------

class FireSmokeDetector:
    """
    Unified fire/smoke detector.
    Uses heuristics by default; loads YOLOv8 model if model_path is set.

    ⚠️  NOT a certified fire alarm — supplementary signal only.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        fire_min_area: float = 0.01,
        smoke_min_area: float = 0.05,
        yolo_confidence: float = 0.4,
    ):
        self.use_model = model_path is not None
        self.fire_min_area = fire_min_area
        self.smoke_min_area = smoke_min_area

        if self.use_model:
            self.yolo_detector = YOLOFireSmokeDetector(model_path, yolo_confidence)
            logger.info("FireSmokeDetector: using YOLOv8 model at %s", model_path)
        else:
            self.yolo_detector = None
            logger.info(
                "FireSmokeDetector: using HSV heuristics "
                "(no trained model — supplementary signal only)."
            )

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect fire and/or smoke in a frame.

        Returns
        -------
        List of dicts: {alert_type: 'fire'|'smoke', confidence: float}
        Empty list if nothing detected.
        """
        if self.use_model and self.yolo_detector is not None:
            return self.yolo_detector.detect(frame)

        alerts = []

        fire_detected, fire_conf = detect_fire_heuristic(frame, self.fire_min_area)
        if fire_detected:
            logger.warning(
                "FIRE heuristic triggered (area_ratio=%.3f) - "
                "[WARNING] NOT a certified alarm, verify physically.", fire_conf
            )
            alerts.append({"alert_type": "fire", "confidence": fire_conf})

        smoke_detected, smoke_conf = detect_smoke_heuristic(frame, self.smoke_min_area)
        if smoke_detected:
            logger.warning(
                "SMOKE heuristic triggered (area_ratio=%.3f) - "
                "[WARNING] NOT a certified alarm, verify physically.", smoke_conf
            )
            alerts.append({"alert_type": "smoke", "confidence": smoke_conf})

        return alerts
