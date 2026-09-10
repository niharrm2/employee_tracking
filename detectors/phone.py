"""
detectors/phone.py — Mobile Phone Detection
=============================================
Uses YOLOv8n (nano) pretrained on COCO dataset.
COCO class 67 = 'cell phone'. No custom training needed.

NOTE: Detection confidence is affected by:
  - Camera angle and distance
  - Phone orientation (flat on desk vs held up)
  - Partial occlusion, low lighting
  - Sampling interval — phone use between samples is not captured
This provides an *estimate* of phone usage, not an exact measurement.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# COCO class index for 'cell phone'
CELL_PHONE_CLASS_ID = 67


class PhoneDetector:
    """
    YOLOv8n-based mobile phone detector.
    Loads the model once on init and reuses across frames.
    """

    def __init__(self, confidence_threshold: float = 0.5):
        """
        Parameters
        ----------
        confidence_threshold : float
            Minimum YOLO detection confidence to report a phone (0–1).
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError(
                "ultralytics not installed. Run: pip install ultralytics"
            )

        logger.info("Loading YOLOv8n model for phone detection (CPU)...")
        # yolov8n.pt is auto-downloaded on first use to ~/.cache/ultralytics/
        self.model = YOLO("yolov8n.pt")
        self.confidence_threshold = confidence_threshold
        logger.info("YOLOv8n model ready.")

    def detect_phones(
        self, frame: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Detect mobile phones in a single BGR frame.

        Returns
        -------
        List of dicts:
          - bbox: [x1, y1, x2, y2]
          - confidence: float
        """
        if frame is None or frame.size == 0:
            return []

        try:
            # Run inference on CPU explicitly; verbose=False suppresses YOLO logs
            results = self.model(
                frame,
                device="cpu",
                classes=[CELL_PHONE_CLASS_ID],
                conf=self.confidence_threshold,
                verbose=False,
            )
        except Exception as exc:
            logger.warning("YOLOv8n inference error: %s", exc)
            return []

        phones = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                if cls_id != CELL_PHONE_CLASS_ID:
                    continue
                conf = float(box.conf[0])
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                phones.append({"bbox": [x1, y1, x2, y2], "confidence": conf})

        return phones


def find_nearest_employee(
    phone_bbox: List[int],
    known_faces: List[Dict[str, Any]],
    max_distance_px: int = 300,
) -> Optional[str]:
    """
    Heuristically attribute a detected phone to the nearest known face.

    Uses Euclidean distance between bbox centres. Returns employee_id
    of the nearest face within max_distance_px, or None.

    NOTE: This is a rough spatial estimate — multiple people in frame
    may lead to wrong attribution, especially at wide camera angles.
    """
    if not known_faces:
        return None

    px, py = _bbox_center(phone_bbox)
    best_id = None
    best_dist = float("inf")

    for face in known_faces:
        fx, fy = _bbox_center(face["bbox"])
        dist = ((px - fx) ** 2 + (py - fy) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_id = face["employee_id"]

    if best_dist <= max_distance_px:
        return best_id
    return None


def _bbox_center(bbox: List[int]) -> Tuple[float, float]:
    """Return the (cx, cy) centre of a [x1, y1, x2, y2] bbox."""
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
