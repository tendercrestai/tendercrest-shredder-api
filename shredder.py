import os
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
import pdfplumber
import instructor
from openai import OpenAI

from schemas import ShreddedDocumentResult, ComplianceRequirement

load_dotenv()

client = instructor.from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

EXTRACTION_SYSTEM_PROMPT = """
You are an expert Federal and Commercial RFP Proposal Manager and Legal Compliance Specialist.
Your task is to "shred" solicitation pages into atomic, defensible compliance requirements.

Rules:
1. Deconstruct compound sentences: If a single sentence contains multiple mandates, break them into distinct individual items.
2. Flag all deontic directives: Watch for keywords like "shall", "must", "will be required to", "offerors need to submit", "mandatory".
3. Assign appropriate Categories (INSTRUCTION, EVALUATION, TECHNICAL_SCOPE, LEGAL_CLAUSE, SUBMISSION_ADMIN).
4. Do NOT hallucinate requirements that are not explicitly stated or implied in the provided text.
"""

def extract_pages_with_metadata(pdf_path: str) -> List[Dict[str, Any]]:
    extracted_pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            page_text = page.extract_text(layout=False) or ""
            words = page.extract_words()
            extracted_pages.append({
                "page_number": idx + 1,
                "text": page_text,
                "words": words,
                "width": float(page.width),
                "height": float(page.height)
            })
    return extracted_pages

def find_approx_bbox(words: List[Dict[str, Any]], match_text: str) -> Dict[str, float] | None:
    if not words or not match_text:
        return None

    target_tokens = [re.sub(r'\W+', '', t).lower() for t in match_text.split()[:4]]
    if not target_tokens:
        return None

    matching_boxes = []
    for w in words:
        cleaned_word = re.sub(r'\W+', '', w["text"]).lower()
        if cleaned_word in target_tokens:
            matching_boxes.append((w["x0"], w["top"], w["x1"], w["bottom"]))

    if not matching_boxes:
        return None

    return {
        "x0": round(min(b[0] for b in matching_boxes), 2),
        "y0": round(min(b[1] for b in matching_boxes), 2),
        "x1": round(max(b[2] for b in matching_boxes), 2),
        "y1": round(max(b[3] for b in matching_boxes), 2)
    }

def shred_document_chunk(chunk_text: str, page_number: int, start_req_index: int) -> List[ComplianceRequirement]:
    if len(chunk_text.strip()) < 50:
        return []

    user_prompt = f"""
    Analyze Page {page_number} of the following solicitation excerpt.
    Extract every single proposal requirement, instruction, or mandatory scope item.
    Start requirement numbering at REQ-{start_req_index:03d}.

    --- SOLICITATION TEXT ---
    {chunk_text}
    """

    class PageExtraction(instructor.OpenAISchema):
        requirements: List[ComplianceRequirement]

    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        response_model=PageExtraction,
        temperature=0.0,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        max_retries=2
    )

    return response.requirements

def run_rfp_shredder(pdf_path: str, doc_title: str = "Solicitation") -> ShreddedDocumentResult:
    pages_data = extract_pages_with_metadata(pdf_path)
    all_requirements: List[ComplianceRequirement] = []
    current_counter = 1

    for page in pages_data:
        triggers = ["shall", "must", "require", "offeror", "submittal", "evaluation", "criteria", "scope"]
        has_triggers = any(t in page["text"].lower() for t in triggers)
        
        if not has_triggers and len(page["text"]) < 200:
            continue

        raw_reqs = shred_document_chunk(
            chunk_text=page["text"], 
            page_number=page["page_number"], 
            start_req_index=current_counter
        )

        for req in raw_reqs:
            req.page_number = page["page_number"]
            bbox = find_approx_bbox(page["words"], req.exact_solicitation_text)
            if bbox:
                req.bounding_box = bbox

            all_requirements.append(req)
            current_counter += 1

    return ShreddedDocumentResult(
        document_title=doc_title,
        total_requirements_found=len(all_requirements),
        requirements=all_requirements
    )
