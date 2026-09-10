"""
detectors/emotion.py — Emotion/Expression Detection
=====================================================
⚠️  DISABLED BY DEFAULT — Read before enabling  ⚠️

This feature uses the FER library (CNN trained on FER-2013) to classify
facial expressions into 7 categories: angry, disgust, fear, happy,
sad, surprise, neutral.

WHY IT'S OFF BY DEFAULT:
  1. Accuracy limitations: FER-2013-trained models achieve ~65-70%
     accuracy under ideal conditions (frontal face, good lighting, neutral
     background). On compressed, low-resolution, sampled CCTV frames,
     accuracy is substantially lower.
  2. Proxy problem: Facial expressions are a weak proxy for emotional
     state. People mask emotions, have resting expressions that differ
     from their mood, and cultural expression norms vary.
  3. Privacy & trust: Tracking employee emotional states via camera
     raises significant trust, ethical, and legal concerns. Many
     jurisdictions restrict biometric data collection beyond attendance.
  4. Legal risk: In some regions (EU AI Act, CCPA, GDPR), automated
     emotion inference in workplaces is prohibited or heavily regulated.

BEFORE ENABLING:
  - Consult HR and legal counsel.
  - Disclose the feature to all employees.
  - Verify compliance with local surveillance and privacy laws.
  - Consider whether the business value justifies the trust cost.

To enable: set features.emotion_detection: true in config.yaml.
"""

import logging
from typing import List, Dict, Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmotionDetector:
    """
    FER-based facial expression classifier.
    Uses TensorFlow-CPU — no GPU required.

    Only instantiated when emotion_detection feature is enabled in config.
    The pipeline.py checks the toggle before constructing this class.
    """

    EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

    def __init__(self, min_confidence: float = 0.5, use_mtcnn: bool = False):
        """
        Parameters
        ----------
        min_confidence : float
            Minimum score for dominant emotion to be reported.
        use_mtcnn : bool
            Use MTCNN for face detection (more accurate, slower) instead
            of OpenCV Haar cascades (faster, less accurate at angles).
            False recommended for CPU performance.
        """
        try:
            from fer import FER
        except ImportError:
            raise ImportError(
                "fer not installed. Run: pip install fer tensorflow-cpu"
            )

        logger.info(
            "Loading FER emotion detector (mtcnn=%s) — "
            "EXPERIMENTAL, off by default. See module docstring for caveats.",
            use_mtcnn,
        )
        # mtcnn=False uses faster Haar cascade face detection
        self.detector = FER(mtcnn=use_mtcnn)
        self.min_confidence = min_confidence
        logger.info("FER emotion detector ready.")

    def detect_emotions(
        self, frame: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Detect faces and classify emotions in a BGR frame.

        NOTE: FER expects BGR or RGB (it converts internally). Results
        are affected heavily by image quality, lighting, and face size.
        Small faces (< ~48px) may return unreliable results.

        Returns
        -------
        List of dicts:
          - bbox: [x, y, w, h] (FER format)
          - dominant_emotion: str
          - confidence: float
          - all_scores: dict {emotion: score}
        """
        if frame is None or frame.size == 0:
            return []

        try:
            fer_results = self.detector.detect_emotions(frame)
        except Exception as exc:
            logger.warning("FER inference error: %s", exc)
            return []

        results = []
        for face_data in fer_results:
            emotions = face_data.get("emotions", {})
            if not emotions:
                continue

            dominant_emotion = max(emotions, key=emotions.get)
            confidence = emotions[dominant_emotion]

            if confidence < self.min_confidence:
                continue

            results.append({
                "bbox": face_data.get("box", [0, 0, 0, 0]),   # [x, y, w, h]
                "dominant_emotion": dominant_emotion,
                "confidence": round(confidence, 3),
                "all_scores": {k: round(v, 3) for k, v in emotions.items()},
            })

        return results
