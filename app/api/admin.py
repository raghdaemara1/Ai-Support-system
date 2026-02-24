"""Admin API endpoints for tenant management and knowledge ingestion."""
import os
import tempfile
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.dependencies import AdminAPIKey, get_db_session
from app.models.schemas import (
    IngestionRequest,
    IngestionResponse,
    TenantConfig,
    TenantCreate,
    TenantResponse,
)
from app.rag.ingestion import ingest_documents
from app.services.tenant_service import TenantService

router = APIRouter()
logger = get_logger(__name__)


# Tenant Management
@router.post("/tenants", response_model=dict)
async def create_tenant(
    data: TenantCreate,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Create a new tenant.

    Returns the tenant info and API key (only shown once!).
    """
    service = TenantService(db)

    # Check if slug already exists
    existing = await service.get_tenant_by_slug(data.slug)
    if existing:
        raise HTTPException(status_code=400, detail="Tenant slug already exists")

    tenant, api_key = await service.create_tenant(data)

    return {
        "tenant": TenantResponse.model_validate(tenant).model_dump(),
        "api_key": api_key,
        "warning": "Save this API key! It will not be shown again.",
    }


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    db: AsyncSession = Depends(get_db_session),
) -> List[TenantResponse]:
    """List all active tenants."""
    service = TenantService(db)
    tenants = await service.list_tenants()
    return [TenantResponse.model_validate(t) for t in tenants]


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> TenantResponse:
    """Get tenant by ID."""
    service = TenantService(db)
    tenant = await service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantResponse.model_validate(tenant)


@router.put("/tenants/{tenant_id}/config", response_model=TenantResponse)
async def update_tenant_config(
    tenant_id: str,
    config: TenantConfig,
    api_key: str = Depends(AdminAPIKey),
    db: AsyncSession = Depends(get_db_session),
) -> TenantResponse:
    """Update tenant configuration."""
    service = TenantService(db)
    tenant = await service.update_config(tenant_id, config)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantResponse.model_validate(tenant)


# Knowledge Base Ingestion
@router.post("/tenants/{tenant_id}/knowledge", response_model=IngestionResponse)
async def ingest_knowledge(
    tenant_id: str,
    request: IngestionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> IngestionResponse:
    """
    Ingest knowledge from various sources.

    Accepts JSON with sources array:
    {
        "sources": [
            {"type": "text", "content": "...", "source_name": "faq"},
            {"type": "url", "url": "https://...", "source_name": "website"}
        ]
    }
    """
    # Verify tenant exists (accepts UUID or slug)
    service = TenantService(db)
    tenant = await service.get_tenant_by_id_or_slug(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Convert to dict format for ingestion
    sources = [s.model_dump() for s in request.sources]

    try:
        # Use slug as namespace — consistent with how chat endpoint queries the KB
        result = await ingest_documents(tenant_id=tenant.slug, sources=sources)
        return IngestionResponse(
            status="completed",
            chunks_ingested=result["chunks_ingested"],
            sources_processed=result["sources_processed"],
        )
    except Exception as e:
        logger.error("Ingestion failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/tenants/{tenant_id}/knowledge/upload", response_model=IngestionResponse)
async def upload_knowledge_files(
    tenant_id: str,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db_session),
) -> IngestionResponse:
    """
    Upload PDF or text files to the knowledge base.
    """
    # Verify tenant exists (accepts UUID or slug)
    service = TenantService(db)
    tenant = await service.get_tenant_by_id_or_slug(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    sources = []
    temp_files = []

    try:
        for file in files:
            # Save uploaded file temporarily
            suffix = os.path.splitext(file.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_files.append(tmp.name)

                if suffix.lower() == ".pdf":
                    sources.append({
                        "type": "pdf",
                        "path": tmp.name,
                        "source_name": file.filename,
                    })
                else:
                    sources.append({
                        "type": "text_file",
                        "path": tmp.name,
                        "source_name": file.filename,
                    })

        result = await ingest_documents(tenant_id=tenant.slug, sources=sources)

        return IngestionResponse(
            status="completed",
            chunks_ingested=result["chunks_ingested"],
            sources_processed=result["sources_processed"],
        )

    finally:
        # Clean up temp files
        for path in temp_files:
            try:
                os.unlink(path)
            except Exception:
                pass


@router.post("/tenants/{tenant_id}/knowledge/advanced_csv_extract")
async def extract_and_download_csv(
    tenant_id: str,
    file: UploadFile = File(...),
    format: str = "csv",
    machine_name: str = "Unknown Machine",
    db: AsyncSession = Depends(get_db_session),
):
    """
    Advanced Data Extraction & CSV Download
    Upload a PDF. Extracts structured alarms using Regex/LLM logic, 
    ingests the structured data into ChromaDB for highly accurate RAG, 
    and returns a downloadable CSV file of all extracted alarms.
    """
    # Verify tenant
    service = TenantService(db)
    tenant = await service.get_tenant_by_id_or_slug(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for advanced extraction")

    try:
        import json
        from app.rag.csv_extractor import extract_text_from_pdf, extract_alarms_from_text, generate_alarm_csv, format_alarms_for_rag, get_pdf_metadata
        
        # 1. Read PDF bytes
        content = await file.read()
        
        # 2. Extract Raw Text & Metadata
        raw_text = extract_text_from_pdf(content)
        metadata = get_pdf_metadata(content, file.filename)
        
        # 3. Apply Regex/LLM hybrid extraction for structured alarms
        alarms = extract_alarms_from_text(raw_text)
        
        if not alarms:
            raise HTTPException(status_code=404, detail="No structured alarms or parameters could be found in this document.")

        # 4. Format into a highly structured string for RAG ingestion
        rag_text = format_alarms_for_rag(alarms)
        
        # 5. Ingest into ChromaDB isolated vector store
        sources = [{
            "type": "text",
            "content": rag_text,
            "source_name": f"STRUCTURED_EXTRACT_{file.filename}",
            "metadata": metadata
        }]
        await ingest_documents(tenant_id=tenant.slug, sources=sources)
        
        # 6. Return Data (CSV or fully structured JSON)
        if format.lower() == "json":
            # Document Intelligence structured output mode
            output_data = {
                "tenant_id": tenant.slug,
                "metadata": metadata,
                "records_extracted": len(alarms),
                "data": alarms
            }
            return Response(
                content=json.dumps(output_data, indent=2),
                media_type="application/json"
            )
        else:
            # Traditional CSV download mode
            csv_data = generate_alarm_csv(alarms, machine_name=machine_name)
            return Response(
                content=csv_data,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=extracted_alarms_{tenant.slug}.csv"}
            )

    except Exception as e:
        logger.error("Advanced extraction failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Advanced extraction failed: {str(e)}")


@router.post("/tenants/{tenant_id}/knowledge/text", response_model=IngestionResponse)
async def add_knowledge_text(
    tenant_id: str,
    content: str,
    source_name: str = "manual_entry",
    db: AsyncSession = Depends(get_db_session),
) -> IngestionResponse:
    """
    Add plain text content to the knowledge base.

    Simple endpoint for quick text additions.
    """
    service = TenantService(db)
    tenant = await service.get_tenant_by_id_or_slug(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    sources = [{
        "type": "text",
        "content": content,
        "source_name": source_name,
    }]

    result = await ingest_documents(tenant_id=tenant.slug, sources=sources)

    return IngestionResponse(
        status="completed",
        chunks_ingested=result["chunks_ingested"],
        sources_processed=1,
    )
