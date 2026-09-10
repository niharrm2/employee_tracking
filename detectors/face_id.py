"""
detectors/face_id.py — Face Detection + Recognition
=====================================================
Uses InsightFace buffalo_s model pack (CPU-optimized) via ONNXRuntime
with CPUExecutionProvider.

buffalo_s components:
  - det_10g.onnx : RetinaFace-style face detector
  - w600k_mbf.onnx: MobileFaceNet ArcFace recognition (512-dim embeddings)

NOTE: This is a sampling-based detector. Recognition confidence and
accuracy are affected by:
  - Camera angle, lighting, resolution
  - Sampling interval (faces may enter/leave between samples)
  - Partial occlusion (masks, hats, hands)
Do not treat results as 100% accurate event logs.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)


class FaceDetector:
    """
    Wraps InsightFace FaceAnalysis with buffalo_s for CPU-only inference.
    Loads the model once and reuses it across calls.
    """

    def __init__(self, model_name: str = "buffalo_s", det_size: Tuple[int, int] = (640, 640)):
        """
        Parameters
        ----------
        model_name : str
            InsightFace model pack name. Use 'buffalo_s' for CPU.
            'buffalo_l' is more accurate but much slower without GPU.
        det_size : tuple
            Detection resolution (width, height). Smaller = faster but
            may miss small/distant faces.
        """
        try:
            import insightface
            from insightface.app import FaceAnalysis
        except ImportError:
            raise ImportError(
                "insightface not installed. Run: pip install insightface onnxruntime"
            )

        logger.info("Loading InsightFace model pack '%s' (CPU)...", model_name)
        self.app = FaceAnalysis(
            name=model_name,
            providers=["CPUExecutionProvider"],   # explicit CPU — no GPU fallback
        )
        self.app.prepare(ctx_id=0, det_size=det_size)
        self.det_size = det_size
        logger.info("InsightFace model ready (det_size=%s).", det_size)

    def detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run face detection + embedding extraction on a single BGR frame.

        Returns
        -------
        List of dicts, each containing:
          - bbox: [x1, y1, x2, y2] (ints)
          - embedding: np.ndarray, shape (512,), float32
          - det_score: float — detector confidence (0–1)
          - kps: facial keypoints (optional, for downstream use)
        """
        if frame is None or frame.size == 0:
            return []

        try:
            faces = self.app.get(frame)
        except Exception as exc:
            logger.warning("InsightFace inference error: %s", exc)
            return []

        results = []
        for face in faces:
            if face.embedding is None:
                continue
            results.append({
                "bbox": [int(v) for v in face.bbox],
                "embedding": face.embedding.copy(),   # 512-dim float32
                "det_score": float(face.det_score),
                "kps": face.kps,
            })
        return results


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized embedding vectors."""
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0 or b_norm == 0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


def match_face(
    embedding: np.ndarray,
    enrolled_employees: List[Dict[str, Any]],
    threshold: float = 0.4,
) -> Tuple[Optional[str], float]:
    """
    Find the best-matching enrolled employee for a detected face embedding.

    Uses cosine similarity. The threshold is configurable — lower values
    are stricter (fewer false positives but more false negatives).

    NOTE: With sampling intervals, an employee may not be detected every
    cycle even when present. Do not use single-sighting absence as
    confirmation of absence.

    Parameters
    ----------
    embedding : np.ndarray
        512-dim float32 face embedding from detect_faces().
    enrolled_employees : list
        From database.get_all_employees() — each entry has 'employee_id'
        and 'embedding' (np.ndarray).
    threshold : float
        Minimum cosine similarity to count as a match (default 0.4).

    Returns
    -------
    (employee_id, confidence) or (None, best_score_seen)
    """
    best_id: Optional[str] = None
    best_score: float = -1.0

    for emp in enrolled_employees:
        score = cosine_similarity(embedding, emp["embedding"])
        if score > best_score:
            best_score = score
            best_id = emp["employee_id"]

    if best_score >= threshold:
        return best_id, best_score
    return None, best_score


def process_frame_for_faces(
    frame: np.ndarray,
    detector: FaceDetector,
    enrolled_employees: List[Dict[str, Any]],
    match_threshold: float = 0.4,
    det_score_threshold: float = 0.5,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Detect all faces in a frame and classify as known/unknown.

    Parameters
    ----------
    frame : np.ndarray
        BGR image.
    detector : FaceDetector
        Loaded FaceDetector instance.
    enrolled_employees : list
        From database.get_all_employees().
    match_threshold : float
        Cosine similarity threshold for known-face match.
    det_score_threshold : float
        Minimum detector confidence to process a face.

    Returns
    -------
    known_faces : list of dicts
        Each: {employee_id, confidence, bbox, det_score}
    unknown_faces : list of dicts
        Each: {bbox, det_score}
    """
    detections = detector.detect_faces(frame)
    known_faces = []
    unknown_faces = []

    for det in detections:
        if det["det_score"] < det_score_threshold:
            continue

        employee_id, confidence = match_face(
            det["embedding"], enrolled_employees, match_threshold
        )

        if employee_id is not None:
            known_faces.append({
                "employee_id": employee_id,
                "confidence": confidence,
                "bbox": det["bbox"],
                "det_score": det["det_score"],
                "embedding": det["embedding"],
            })
        else:
            unknown_faces.append({
                "bbox": det["bbox"],
                "det_score": det["det_score"],
                "embedding": det["embedding"],
            })

    return known_faces, unknown_faces
