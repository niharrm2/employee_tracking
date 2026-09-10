"""
app/api/v1/employees.py — Employee Registry & Management Router
================================================================
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.deps import get_employee_service, require_admin, require_admin_or_hr, require_admin_hr_manager, TokenData
from app.services.employee_svc import EmployeeService

router = APIRouter(prefix="/employees", tags=["employees"])


from pathlib import Path
from fastapi.responses import FileResponse, Response

class EmployeeOut(BaseModel):
    employee_id: str
    name: str
    department: Optional[str] = None
    enrolled_at: str
    active: bool
    photo_url: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "employee"
    employee_id: Optional[str] = None


@router.get("", response_model=List[EmployeeOut])
async def list_employees(
    active_only: bool = True,
    svc: EmployeeService = Depends(get_employee_service),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    emps = svc.list_employees(active_only=active_only)
    return [
        EmployeeOut(
            employee_id=e["employee_id"],
            name=e["name"],
            department=e.get("department"),
            enrolled_at=e["enrolled_at"],
            active=bool(e["active"]),
            photo_url=f"/api/employees/{e['employee_id']}/photo",
        )
        for e in emps
    ]


@router.get("/{employee_id}/photo")
async def get_employee_photo(
    employee_id: str,
    svc: EmployeeService = Depends(get_employee_service),
):
    """Serve employee's reference facial photo or dynamic avatar."""
    emp = svc.get_employee(employee_id)
    photo_path = emp.get("photo_path")
    if photo_path and Path(photo_path).exists():
        return FileResponse(photo_path, media_type="image/jpeg")

    # Fallback paths
    fallback_path = Path("snapshots/profiles") / f"{employee_id}.jpg"
    if fallback_path.exists():
        return FileResponse(str(fallback_path), media_type="image/jpeg")

    # Check photos directory (e.g. photos/sarah/photo_1.jpg)
    name_parts = emp["name"].lower().split()
    for part in name_parts:
        for cand in Path("photos").rglob(f"*{part}*"):
            if cand.is_file() and cand.suffix.lower() in (".jpg", ".jpeg", ".png"):
                return FileResponse(str(cand), media_type="image/jpeg")

    # Dynamic SVG placeholder avatar with initials
    initials = "".join([p[0] for p in emp["name"].split() if p])[:2].upper() or "EM"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
        <rect width="120" height="120" rx="60" fill="#1e293b"/>
        <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="44" font-weight="700" fill="#818cf8">{initials}</text>
    </svg>'''
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: str,
    svc: EmployeeService = Depends(get_employee_service),
    current_user: TokenData = Depends(require_admin_hr_manager),
):
    e = svc.get_employee(employee_id)
    return EmployeeOut(
        employee_id=e["employee_id"],
        name=e["name"],
        department=e.get("department"),
        enrolled_at=e["enrolled_at"],
        active=bool(e["active"]),
        photo_url=f"/api/employees/{e['employee_id']}/photo",
    )


@router.post("/enroll", status_code=status.HTTP_201_CREATED)
async def enroll_employee(
    employee_id: str = Form(...),
    name: str = Form(...),
    department: str = Form(""),
    photos: List[UploadFile] = File(...),
    svc: EmployeeService = Depends(get_employee_service),
    current_user: TokenData = Depends(require_admin_or_hr),
):
    photo_bytes = []
    for p in photos:
        b = await p.read()
        photo_bytes.append(b)

    return await svc.enroll_from_photos(employee_id, name, department, photo_bytes)


@router.delete("/{employee_id}")
async def deactivate_employee(
    employee_id: str,
    svc: EmployeeService = Depends(get_employee_service),
    current_user: TokenData = Depends(require_admin),
):
    svc.deactivate_employee(employee_id)
    return {"message": f"Employee {employee_id} deactivated"}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    req: CreateUserRequest,
    svc: EmployeeService = Depends(get_employee_service),
    current_user: TokenData = Depends(require_admin),
):
    svc.create_api_user(req.username, req.password, req.role, req.employee_id)
    return {"message": f"User {req.username} created with role {req.role}"}