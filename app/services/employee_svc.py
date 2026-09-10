"""
app/services/employee_svc.py — Employee Enrollment & Biometrics Service
========================================================================
Manages employee onboarding, photo validation, ArcFace embeddings, and RBAC user provisioning.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import hash_password
from app.db.repositories.employee_repo import EmployeeRepository
from detectors.face_id import FaceDetector

logger = logging.getLogger(__name__)


class EmployeeService:
    def __init__(self, employee_repo: Optional[EmployeeRepository] = None):
        self.repo = employee_repo or EmployeeRepository()

    def list_employees(self, active_only: bool = True) -> List[Dict[str, Any]]:
        return self.repo.get_all(active_only=active_only)

    def get_employee(self, employee_id: str) -> Dict[str, Any]:
        emp = self.repo.get_by_id(employee_id)
        if not emp:
            raise NotFoundError(f"Employee {employee_id} not found")
        return emp

    def deactivate_employee(self, employee_id: str) -> None:
        emp = self.repo.get_by_id(employee_id)
        if not emp:
            raise NotFoundError(f"Employee {employee_id} not found")
        self.repo.deactivate(employee_id)
        logger.info("Employee %s deactivated", employee_id)

    async def enroll_from_photos(
        self,
        employee_id: str,
        name: str,
        department: str,
        photo_bytes_list: List[bytes],
    ) -> Dict[str, Any]:
        """
        Processes 3-5 face photos, extracts ArcFace 512-dim embeddings,
        normalizes and averages them into an enrolled biometric profile.
        """
        if len(photo_bytes_list) < 3:
            raise ValidationError("At least 3 clear facial photos are required for biometric enrollment")
        if len(photo_bytes_list) > 5:
            raise ValidationError("Maximum 5 photos allowed per enrollment request")

        detector = FaceDetector(model_name="buffalo_s")
        embeddings = []
        best_face_frame = None
        best_score = -1.0

        for b in photo_bytes_list:
            nparr = np.frombuffer(b, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            faces = detector.detect_faces(frame)
            valid = [f for f in faces if f["det_score"] >= 0.5]
            if len(valid) == 1:
                score = float(valid[0]["det_score"])
                embeddings.append(valid[0]["embedding"])
                if score > best_score:
                    best_score = score
                    best_face_frame = frame

        if len(embeddings) < 3:
            raise ValidationError(
                f"Only {len(embeddings)} valid single-subject face(s) found in uploaded photos. "
                "Ensure each photo contains only one clearly illuminated face."
            )

        avg_emb = np.mean(np.stack(embeddings), axis=0).astype(np.float32)
        norm = np.linalg.norm(avg_emb)
        if norm > 0:
            avg_emb = avg_emb / norm

        # Persist high-resolution reference avatar to disk
        from pathlib import Path
        profile_photo_path = None
        if best_face_frame is not None:
            profile_dir = Path("snapshots/profiles")
            profile_dir.mkdir(parents=True, exist_ok=True)
            saved_path = profile_dir / f"{employee_id}.jpg"
            cv2.imwrite(str(saved_path), best_face_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            profile_photo_path = str(saved_path).replace("\\", "/")

        self.repo.upsert(employee_id, name, department, avg_emb, photo_path=profile_photo_path)
        logger.info("Enrolled employee %s (%s) with %d photos (photo_path=%s)", name, employee_id, len(embeddings), profile_photo_path)
        return {
            "message": "Biometric profile enrolled successfully",
            "employee_id": employee_id,
            "name": name,
            "department": department,
            "photos_used": len(embeddings),
            "photo_url": f"/api/employees/{employee_id}/photo",
        }

    def create_api_user(self, username: str, password: str, role: str = "employee", employee_id: Optional[str] = None) -> None:
        hashed = hash_password(password)
        self.repo.create_api_user(username, hashed, role, employee_id)
        logger.info("Created API user '%s' with role '%s'", username, role)