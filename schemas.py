from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class RequirementCategory(str, Enum):
    INSTRUCTION = "INSTRUCTION"
    EVALUATION = "EVALUATION"
    TECHNICAL_SCOPE = "TECHNICAL_SCOPE"
    LEGAL_CLAUSE = "LEGAL_CLAUSE"
    SUBMISSION_ADMIN = "SUBMISSION_ADMIN"

class ModalityLevel(str, Enum):
    MANDATORY = "MANDATORY"
    CONDITIONAL = "CONDITIONAL"
    INFORMATIONAL = "INFORMATIONAL"

class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

class ComplianceRequirement(BaseModel):
    requirement_id: str
    section_reference: Optional[str] = None
    page_number: int
    category: RequirementCategory
    modality: ModalityLevel
    exact_solicitation_text: str
    summary_directive: str
    target_proposal_section: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None

class ShreddedDocumentResult(BaseModel):
    document_title: str
    total_requirements_found: int
    requirements: List[ComplianceRequirement]
