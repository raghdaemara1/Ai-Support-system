import io
import re
import csv
from typing import List, Dict

import PyPDF2


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract raw text from PDF bytes."""
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n\n"
    return text


def get_pdf_metadata(file_bytes: bytes, filename: str) -> dict:
    """Extract basic metadata from a PDF file."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        meta = reader.metadata or {}
        return {
            "source_name": filename,
            "title": meta.get("/Title", ""),
            "author": meta.get("/Author", ""),
            "creator": meta.get("/Creator", ""),
            "producer": meta.get("/Producer", ""),
            "creation_date": meta.get("/CreationDate", ""),
            "num_pages": len(reader.pages)
        }
    except Exception as e:
        return {"source_name": filename, "error": str(e)}


def classify_reason(description: str, cause: str) -> dict:
    """Keyword-based heuristic classification ported from Industrail_App."""
    cat = "Basic Machine and Safety Faults"
    r2 = "Mechanical"
    desc_lower = (description + " " + (cause or "")).lower()
    
    electrical_words = ["electric", "voltage", "current", "drive", "inverter", "short circuit", "wire", "contactor", "spark", "arc", "encoder", "fuse", "relay", "power supply", "amp"]
    mechanical_words = ["jam", "wear", "broken", "loose", "fracture", "belt", "bearing", "pneumatic", "hydraulic", "valve", "pump", "gear", "seal", "lubrication", "friction"]
    instrumentation_words = ["sensor", "encoder", "limit switch", "photocell", "vision", "camera", "probe", "detector"]
    software_words = ["program", "software", "plc", "timeout", "hmi", "network", "communication loss", "watchdog"]

    if any(w in desc_lower for w in electrical_words):
        r2 = "Electrical"
    elif any(w in desc_lower for w in instrumentation_words):
        r2 = "Sensor/Instrumentation"
    elif any(w in desc_lower for w in software_words):
        r2 = "Software/Control"
    elif any(w in desc_lower for w in mechanical_words):
        r2 = "Mechanical"
        
    category_type = "Unplanned Downtime"
    
    return {
        "reason_level_1": cat,
        "reason_level_2": r2,
        "category_type": category_type
    }


def chunk_text(text: str, chunk_size=4000) -> list:
    """Paragraph-aware chunking."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for p in paragraphs:
        if set(p.strip()) == {""}: continue
        if len(current) + len(p) < chunk_size:
            current += p + "\n\n"
        else:
            if current: chunks.append(current)
            current = p + "\n\n"
    if current: chunks.append(current)
    return chunks


def extract_alarms_from_text(text: str) -> List[Dict]:
    """
    Extract structured alarms using the regex from Industrail_App.
    Regex captures Alarm ID, Description, Cause, and Action.
    """
    alarms = []
    chunks = chunk_text(text)
    
    # Ported from Industrail_App LocalLLMExtractor
    pattern = re.compile(
        r'^[ \t]*(?:Alarm|Error|Fault)[ \t]*[:\-]?[ \t]*(\d{1,5})[ \t\.\-\:]*(?:.*?)\n(.*?)(?:\n[ \t]*Cause:[ \t]*(.*?))?(?:\n[ \t]*(?:Reaction|Remedy|Action):[ \t]*(.*?))?(?=\n[ \t]*(?:Alarm|Error|Fault)[ \t]*[:\-]?[ \t]*\d{1,5}|\Z)',
        re.IGNORECASE | re.DOTALL | re.MULTILINE
    )
    
    unique_alarms = {}
    
    for chunk in chunks:
        for match in pattern.finditer(chunk):
            aid = match.group(1).strip()
            desc = match.group(2).strip()
            cause = match.group(3).strip() if match.group(3) else ""
            action_text = match.group(4).strip() if match.group(4) else ""
            
            if not desc: continue
            desc = desc.split('\n')[0] # often multiline leaks, take just first
            
            if aid not in unique_alarms:
                # Apply heuristic classification
                clss = classify_reason(desc, cause)
                
                unique_alarms[aid] = {
                    "Fault Code *": str(aid).zfill(4),
                    "Fault Name *": desc,
                    "Reason 3": cause,
                    "Reason 4": action_text,
                    "Reason 1 *": clss["reason_level_1"],
                    "Reason 2": clss["reason_level_2"],
                    "Category Type *": clss["category_type"]
                }
                
    return list(unique_alarms.values())


def generate_alarm_csv(alarms: List[Dict], machine_name: str = "Unknown Machine") -> str:
    """Convert extracted alarms to a CSV string matching the Downtime Config schema."""
    fieldnames = [
        "Machine *", "Reason 1 *", "Reason 2", "Reason 3", "Reason 4", 
        "Category Type *", "Fault Code *", "Fault Name *"
    ]
    
    if not alarms:
        return ",".join(fieldnames) + "\n"
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for alarm in alarms:
        row = alarm.copy()
        row["Machine *"] = machine_name
        writer.writerow(row)
    
    return output.getvalue()


def format_alarms_for_rag(alarms: List[Dict]) -> str:
    """
    Format alarms into a highly structured text document designed specifically
    to be ingested by ChromaDB so the LLM can easily answer questions like 
    'What is alarm 2008?'.
    """
    lines = []
    for alarm in alarms:
        block = f"ALARM CODE: {alarm['Fault Code *']}\n"
        block += f"DESCRIPTION: {alarm['Fault Name *']}\n"
        block += f"CATEGORY: {alarm['Reason 1 *']} - {alarm['Reason 2']} ({alarm['Category Type *']})\n"
        if alarm.get('Reason 3'):
            block += f"CAUSE: {alarm['Reason 3']}\n"
        if alarm.get('Reason 4'):
            block += f"ACTION: {alarm['Reason 4']}\n"
        lines.append(block)
        
    return "\n\n---\n\n".join(lines)
