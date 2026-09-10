"""
enrollment.py — Employee Face Enrollment CLI
=============================================
Registers an employee into the system by:
  1. Reading 3–5 photos from a directory
  2. Extracting face embeddings from each photo (InsightFace buffalo_s)
  3. Averaging the embeddings for robustness to lighting/angle variation
  4. Storing the result in the employees table

Usage:
    python enrollment.py enroll \\
        --employee-id "EMP001" \\
        --name "Jane Smith" \\
        --department "Engineering" \\
        --photos ./photos/jane/

    python enrollment.py list
    python enrollment.py deactivate --employee-id "EMP001"
"""

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import List, Optional

import click
import cv2
import numpy as np
from rich.console import Console
from rich.table import Table

# Local modules
import database as db
from detectors.face_id import FaceDetector

console = Console()
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def load_config():
    """Load config.yaml from the current directory."""
    import yaml
    config_path = Path("config.yaml")
    if not config_path.exists():
        console.print("[red]config.yaml not found in current directory.[/red]")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def extract_embeddings_from_photos(
    photo_paths: List[Path],
    detector: FaceDetector,
    min_det_score: float = 0.5,
) -> List[np.ndarray]:
    """
    Extract one face embedding per photo. Skips photos with 0 or >1 face.

    Returns list of 512-dim float32 embedding arrays.
    """
    embeddings = []
    for photo_path in photo_paths:
        frame = cv2.imread(str(photo_path))
        if frame is None:
            console.print(f"[yellow]Skipping {photo_path.name}: could not read image.[/yellow]")
            continue

        faces = detector.detect_faces(frame)
        valid_faces = [f for f in faces if f["det_score"] >= min_det_score]

        if len(valid_faces) == 0:
            console.print(
                f"[yellow]Skipping {photo_path.name}: no face detected "
                f"(det_score threshold {min_det_score}).[/yellow]"
            )
            continue
        if len(valid_faces) > 1:
            console.print(
                f"[yellow]Skipping {photo_path.name}: {len(valid_faces)} faces detected "
                f"— enrollment photos must contain exactly one face.[/yellow]"
            )
            continue

        embeddings.append(valid_faces[0]["embedding"])
        console.print(f"  [green][OK][/green] {photo_path.name} - face detected (det_score={valid_faces[0]['det_score']:.2f})")

    return embeddings


@click.group()
@click.option("--db-path", default=None, help="Path to SQLite database file.")
@click.pass_context
def cli(ctx, db_path):
    """Office Tracking System — Employee Enrollment CLI"""
    config = load_config()
    db_path = db_path or config.get("database", {}).get("sqlite_path", "office_track.db")
    db.init_db(db_path)
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


@cli.command()
@click.option("--employee-id", default=None, help="Unique employee ID (auto-generated if omitted).")
@click.option("--name", required=True, help="Full name of the employee.")
@click.option("--department", default="", help="Department name.")
@click.option(
    "--photos", required=True,
    type=click.Path(exists=True),
    help="Directory containing 3–5 enrollment photos (JPEG/PNG).",
)
@click.option("--min-photos", default=3, help="Minimum number of valid photos required.")
@click.pass_context
def enroll(ctx, employee_id, name, department, photos, min_photos):
    """Enroll a new employee from their face photos."""
    config = ctx.obj["config"]

    # Generate ID if not provided
    if employee_id is None:
        employee_id = str(uuid.uuid4())[:8].upper()
        console.print(f"[dim]Auto-generated employee ID: {employee_id}[/dim]")

    # Collect image files
    photo_dir = Path(photos)
    photo_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    photo_paths = sorted([
        p for p in photo_dir.iterdir()
        if p.suffix.lower() in photo_exts
    ])

    if len(photo_paths) < min_photos:
        console.print(
            f"[red]Found only {len(photo_paths)} image(s) in {photos}. "
            f"Need at least {min_photos}.[/red]"
        )
        sys.exit(1)

    console.print(f"\n[bold]Enrolling:[/bold] {name} ({employee_id}) — {len(photo_paths)} photos")

    # Load face detector
    face_cfg = config.get("face_recognition", {})
    det_size = tuple(face_cfg.get("det_size", [640, 640]))
    model_name = face_cfg.get("model_name", "buffalo_s")

    with console.status("[bold green]Loading InsightFace model..."):
        detector = FaceDetector(model_name=model_name, det_size=det_size)

    # Extract embeddings
    console.print("\nExtracting face embeddings:")
    embeddings = extract_embeddings_from_photos(photo_paths, detector)

    if len(embeddings) < min_photos:
        console.print(
            f"\n[red]Only {len(embeddings)} valid face(s) extracted "
            f"(need {min_photos}). Enrollment aborted.[/red]"
        )
        sys.exit(1)

    # Average embeddings for robustness
    avg_embedding = np.mean(np.stack(embeddings), axis=0).astype(np.float32)
    # Normalise to unit length (standard for cosine similarity matching)
    norm = np.linalg.norm(avg_embedding)
    if norm > 0:
        avg_embedding = avg_embedding / norm

    # Store in database
    db.upsert_employee(employee_id, name, department, avg_embedding)

    console.print(
        f"\n[bold green][OK] Enrolled successfully![/bold green]\n"
        f"  ID:         {employee_id}\n"
        f"  Name:       {name}\n"
        f"  Department: {department}\n"
        f"  Photos used: {len(embeddings)}/{len(photo_paths)}\n"
        f"  Embedding:  512-dim float32 (averaged + L2-normalised)"
    )


@cli.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="Include deactivated employees.")
@click.pass_context
def list_employees(ctx, show_all):
    """List all enrolled employees."""
    employees = db.get_all_employees(active_only=not show_all)

    table = Table(title="Enrolled Employees")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Department")
    table.add_column("Enrolled At")
    table.add_column("Active", style="green")

    for emp in employees:
        table.add_row(
            emp["employee_id"],
            emp["name"],
            emp.get("department") or "-",
            emp["enrolled_at"][:19],
            "YES" if emp["active"] else "NO",
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(employees)} employee(s)[/dim]")


@cli.command()
@click.option("--employee-id", required=True, help="Employee ID to deactivate.")
@click.pass_context
def deactivate(ctx, employee_id):
    """Deactivate (soft-delete) an enrolled employee."""
    emp = db.get_employee(employee_id)
    if emp is None:
        console.print(f"[red]Employee {employee_id} not found.[/red]")
        sys.exit(1)

    if click.confirm(f"Deactivate {emp['name']} ({employee_id})?"):
        db.deactivate_employee(employee_id)
        console.print(f"[green][OK] {emp['name']} deactivated.[/green]")
    else:
        console.print("Cancelled.")


@cli.command()
@click.option("--employee-id", required=True)
@click.option("--photos", required=True, type=click.Path(exists=True))
@click.option("--min-photos", default=3)
@click.pass_context
def re_enroll(ctx, employee_id, photos, min_photos):
    """Re-enroll an existing employee with new photos (replaces embedding)."""
    config = ctx.obj["config"]
    emp = db.get_employee(employee_id)
    if emp is None:
        console.print(f"[red]Employee {employee_id} not found.[/red]")
        sys.exit(1)

    ctx.invoke(
        enroll,
        employee_id=employee_id,
        name=emp["name"],
        department=emp.get("department", ""),
        photos=photos,
        min_photos=min_photos,
    )


if __name__ == "__main__":
    cli()
