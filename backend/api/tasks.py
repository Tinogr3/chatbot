"""
Endpoint de estado de tareas asíncronas - GET /status/{task_id}
"""
from fastapi import APIRouter, HTTPException

from schemas import TaskStatusResponse
from worker import get_task_result

router = APIRouter(prefix="/status", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """Consulta el estado y progreso de una tarea encolada (upload PDF o process_video)."""
    result = get_task_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    status = result.status
    progress = 0.0
    message = None
    result_payload = None
    error = None

    if status == "PROGRESS" and result.info:
        meta = result.info if isinstance(result.info, dict) else {}
        progress = float(meta.get("progress", 0.0))
        message = meta.get("message")

    if status == "SUCCESS" and result.result:
        result_payload = result.result if isinstance(result.result, dict) else {"result": result.result}
        progress = 1.0

    if status == "FAILURE":
        progress = 1.0
        error = str(result.result) if result.result else "Error desconocido"

    if status == "PENDING":
        message = "Tarea en cola, esperando ejecución..."

    return TaskStatusResponse(
        task_id=task_id,
        status=status,
        progress=progress,
        message=message,
        result=result_payload if status == "SUCCESS" else None,
        error=error,
    )
