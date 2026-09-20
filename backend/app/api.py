from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.ingestion import ingest
from app.schemas import ChatRequest, ChatResponse, FeedbackRequest, IngestResponse
from app.security import Principal, current_principal, require_role
from app.service import answer

router = APIRouter()
_feedback: list[dict] = []

@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, principal: Principal = Depends(current_principal)):
    return await answer(payload.question, principal.tenant_id, payload.filters)

@router.post("/documents", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...), department: str = Form("general"),
    principal: Principal = Depends(current_principal),
):
    require_role(principal, "analyst", "admin")
    if file.content_type not in {"text/plain", "text/markdown"}:
        raise HTTPException(415, "Demo accepts TXT/Markdown; production worker also parses PDF/DOCX")
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "File too large")
    document_id, count = ingest(file.filename or "document", data.decode("utf-8"), principal.tenant_id, {"department": department})
    return IngestResponse(document_id=document_id, chunks_created=count, status="indexed")

@router.post("/feedback", status_code=202)
async def feedback(payload: FeedbackRequest, principal: Principal = Depends(current_principal)):
    _feedback.append({**payload.model_dump(), "tenant_id": principal.tenant_id, "user_id": principal.subject})
    return {"accepted": True}

@router.get("/me")
async def me(principal: Principal = Depends(current_principal)):
    return {"subject": principal.subject, "role": principal.role, "tenant_id": principal.tenant_id}
