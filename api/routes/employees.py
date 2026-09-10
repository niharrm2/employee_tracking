"""
api/routes/employees.py — Employee Management Endpoints
"""
import os
import tempfile
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel

import database as db
from api.auth import require_admin, require_admin_or_hr, require_admin_hr_manager, TokenData

router = APIRouter(prefix="/api/employees", tags=["employees"])


class EmployeeOut(BaseModel):
    employee_id: str
    name: str
    department: Optional[str]
    enrolled_at: str
    active: bool


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "employee"
    employee_id: Optional[str] = None


@router.get("", response_model=List[EmployeeOut])
async def list_employees(
    active_only: bool = True,
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    """List all enrolled employees."""
    employees = db.get_all_employees(active_only=active_only)
    return [
        EmployeeOut(
            employee_id=e["employee_id"],
            name=e["name"],
            department=e.get("department"),
            enrolled_at=e["enrolled_at"],
            active=bool(e["active"]),
        )
        for e in employees
    ]


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: str,
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    emp = db.get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return EmployeeOut(
        employee_id=emp["employee_id"],
        name=emp["name"],
        department=emp.get("department"),
        enrolled_at=emp["enrolled_at"],
        active=bool(emp["active"]),
    )


@router.post("/enroll", status_code=status.HTTP_201_CREATED)
async def enroll_employee(
    employee_id: str = Form(...),
    name: str = Form(...),
    department: str = Form(""),
    photos: List[UploadFile] = File(..., description="3-5 face photos"),
    current_user: TokenData = Depends(require_admin_or_hr),
):
    """
    Enroll a new employee via photo upload.
    Accepts 3-5 images, extracts face embeddings, stores averaged embedding.
    """
    if len(photos) < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 photos required for enrollment."
        )
    if len(photos) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 photos allowed for enrollment."
        )

    # Lazy import to avoid loading model at module import time
    import cv2
    import numpy as np
    from detectors.face_id import FaceDetector

    detector = FaceDetector(model_name="buffalo_s")
    embeddings = []

    for photo in photos:
        content = await photo.read()
        nparr = np.frombuffer(content, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            continue

        faces = detector.detect_faces(frame)
        valid = [f for f in faces if f["det_score"] >= 0.5]
        if len(valid) == 1:
            embeddings.append(valid[0]["embedding"])

    if len(embeddings) < 3:
        raise HTTPException(
            status_code=422,
            detail=f"Only {len(embeddings)} valid single-face photo(s) found. Need at least 3."
        )

    avg_emb = np.mean(np.stack(embeddings), axis=0).astype(np.float32)
    norm = np.linalg.norm(avg_emb)
    if norm > 0:
        avg_emb = avg_emb / norm

    db.upsert_employee(employee_id, name, department, avg_emb)
    return {"message": "Enrolled successfully", "employee_id": employee_id, "photos_used": len(embeddings)}


@router.delete("/{employee_id}")
async def deactivate_employee(
    employee_id: str,
    current_user: TokenData = Depends(require_admin),
):
    """Soft-delete (deactivate) an employee. Requires admin role."""
    emp = db.get_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.deactivate_employee(employee_id)
    return {"message": f"Employee {employee_id} deactivated"}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_api_user(
    req: CreateUserRequest,
    current_user: TokenData = Depends(require_admin),
):
    """Create a new API user with login credentials. Admin only."""
    from api.auth import hash_password
    hashed = hash_password(req.password)
    db.create_api_user(
        username=req.username,
        hashed_password=hashed,
        role=req.role,
        employee_id=req.employee_id,
    )
    return {"message": f"User '{req.username}' created with role '{req.role}'"}
