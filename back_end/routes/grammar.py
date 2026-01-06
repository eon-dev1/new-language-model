# grammar.py
"""
Grammar endpoints for unified human/AI grammar system views.

Provides endpoints to:
- Fetch merged grammar categories from both human and AI sources
- Create/update human grammar category content
- Update human_verified status for categories
"""

from fastapi import APIRouter, HTTPException, Path, Body, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from db_connector.connection import MongoDBConnector
from constants import Collection, TranslationType
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Pydantic Models ---

class CategoryVersion(BaseModel):
    """Single version (human or AI) of a grammar category."""
    description: str
    subcategories: List[Any] = []  # str or {name, content, examples} for AI
    notes: List[str] = []
    examples: List[Any] = []  # str or {bughotu, english, analysis} for AI
    ai_confidence: Optional[float] = None
    human_verified: bool = False
    updated_at: Optional[datetime] = None


class MergedCategory(BaseModel):
    """Grammar category with optional human and AI versions."""
    name: str
    human: Optional[CategoryVersion] = None
    ai: Optional[CategoryVersion] = None


class CategoriesResponse(BaseModel):
    """Response containing merged grammar categories."""
    language_code: str
    categories: List[MergedCategory]
    count: int


class UpdateCategoryRequest(BaseModel):
    """Request to update human grammar category content."""
    notes: List[str] = Field(default=[])
    examples: List[str] = Field(default=[])


class UpdateCategoryResponse(BaseModel):
    """Response confirming category update."""
    success: bool
    category_name: str
    language_code: str
    action: str  # "updated"


class VerifyCategoryRequest(BaseModel):
    """Request to update category verification status."""
    translation_type: str = Field(..., pattern="^(human|ai)$")
    human_verified: bool


class VerifyCategoryResponse(BaseModel):
    """Response confirming verification update."""
    success: bool
    category_name: str
    language_code: str
    translation_type: str
    human_verified: bool


# Valid grammar categories
VALID_CATEGORIES = ["phonology", "morphology", "syntax", "semantics", "discourse"]


# --- Endpoints ---

@router.get("/grammar/{language}/categories", response_model=CategoriesResponse)
async def get_grammar_categories(
    language: str = Path(..., description="Language code (e.g., 'kope', 'french')"),
    db: MongoDBConnector = Depends(get_db)
) -> CategoriesResponse:
    """
    Fetch all grammar categories for a language, merging human and AI versions.

    Returns categories with both human and AI versions where available.

    Args:
        language: Target language code

    Returns:
        CategoriesResponse with merged categories from both sources

    Raises:
        HTTPException: 404 if no grammar found, 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        grammar_systems = database[Collection.GRAMMAR_SYSTEMS]

        # Fetch both human and AI grammar documents
        human_doc = await grammar_systems.find_one({
            "language_code": language_code,
            "translation_type": TranslationType.HUMAN
        })
        ai_doc = await grammar_systems.find_one({
            "language_code": language_code,
            "translation_type": TranslationType.AI
        })

        if not human_doc and not ai_doc:
            # Return empty category shells instead of 404 - allows UI to show empty state
            logger.info(f"No grammar system found for {language_code}, returning empty shells")
            empty_categories = [MergedCategory(name=c) for c in VALID_CATEGORIES]
            return CategoriesResponse(
                language_code=language_code,
                categories=empty_categories,
                count=len(empty_categories)
            )

        merged_categories = []

        for category_name in VALID_CATEGORIES:
            merged = MergedCategory(name=category_name)

            # Extract human version
            if human_doc and human_doc.get("categories", {}).get(category_name):
                cat_data = human_doc["categories"][category_name]
                merged.human = CategoryVersion(
                    description=cat_data.get("description", ""),
                    subcategories=cat_data.get("subcategories", []),
                    notes=cat_data.get("notes", []),
                    examples=cat_data.get("examples", []),
                    ai_confidence=cat_data.get("ai_confidence"),
                    human_verified=cat_data.get("human_verified", False),
                    updated_at=cat_data.get("updated_at")
                )

            # Extract AI version
            if ai_doc and ai_doc.get("categories", {}).get(category_name):
                cat_data = ai_doc["categories"][category_name]
                merged.ai = CategoryVersion(
                    description=cat_data.get("description", ""),
                    subcategories=cat_data.get("subcategories", []),
                    notes=cat_data.get("notes", []),
                    examples=cat_data.get("examples", []),
                    ai_confidence=cat_data.get("ai_confidence"),
                    human_verified=cat_data.get("human_verified", False),
                    updated_at=cat_data.get("updated_at")
                )

            merged_categories.append(merged)

        logger.info(f"Retrieved {len(merged_categories)} grammar categories for {language_code}")

        return CategoriesResponse(
            language_code=language_code,
            categories=merged_categories,
            count=len(merged_categories)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Fetch grammar categories for {language}", e)


@router.post("/grammar/{language}/categories/{category_name}", response_model=UpdateCategoryResponse)
async def update_grammar_category(
    language: str = Path(..., description="Language code"),
    category_name: str = Path(..., description="Category name (phonology, morphology, etc.)"),
    request: UpdateCategoryRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> UpdateCategoryResponse:
    """
    Update human grammar category content.

    Updates notes and examples for a specific category.
    Auto-sets human_verified = true.

    This endpoint is used when:
    - Adding human notes/examples from scratch
    - Editing AI content (creates/updates human version, preserves AI)

    Args:
        language: Target language code
        category_name: Grammar category (phonology, morphology, syntax, semantics, discourse)
        request: Category data (notes, examples)

    Returns:
        UpdateCategoryResponse confirming update

    Raises:
        HTTPException: 400 if invalid category, 404 if grammar not found, 500 on database error
    """
    try:
        if category_name not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {category_name}. Must be one of: {VALID_CATEGORIES}"
            )

        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        grammar_systems = database[Collection.GRAMMAR_SYSTEMS]

        # Get the human grammar document
        human_doc = await grammar_systems.find_one({
            "language_code": language_code,
            "translation_type": TranslationType.HUMAN
        })

        if not human_doc:
            # Create new grammar system document (upsert pattern)
            logger.info(f"Creating new human grammar system for {language_code}")
            new_doc = {
                "language_code": language_code,
                "language_name": language_code.replace('_', ' ').title(),
                "translation_type": TranslationType.HUMAN,
                "grammar_system_name": f"{language_code.replace('_', ' ').title()} Human Grammar System",
                "created_at": datetime.utcnow(),
                "categories": {
                    cat: {
                        "description": "",
                        "subcategories": [],
                        "notes": [],
                        "examples": [],
                        "human_verified": False
                    } for cat in VALID_CATEGORIES
                },
                "metadata": {
                    "version": "1.0",
                    "status": "active",
                    "description": f"Human-curated grammar for {language_code}",
                    "generation_method": "human"
                }
            }
            await grammar_systems.insert_one(new_doc)
            human_doc = new_doc

        now = datetime.utcnow()

        # Update the specific category
        result = await grammar_systems.update_one(
            {
                "language_code": language_code,
                "translation_type": TranslationType.HUMAN
            },
            {
                "$set": {
                    f"categories.{category_name}.notes": request.notes,
                    f"categories.{category_name}.examples": request.examples,
                    f"categories.{category_name}.human_verified": True,
                    f"categories.{category_name}.updated_at": now
                }
            }
        )

        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update category"
            )

        logger.info(f"Updated grammar category '{category_name}' for {language_code}")

        return UpdateCategoryResponse(
            success=True,
            category_name=category_name,
            language_code=language_code,
            action="updated"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Update grammar category {category_name} for {language}", e)


@router.patch("/grammar/{language}/categories/{category_name}/verify", response_model=VerifyCategoryResponse)
async def verify_grammar_category(
    language: str = Path(..., description="Language code"),
    category_name: str = Path(..., description="Category name"),
    request: VerifyCategoryRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> VerifyCategoryResponse:
    """
    Update human_verified status for a grammar category.

    Can verify either human or AI categories based on translation_type.
    Used for Scenario 2: AI content is correct, just verify without editing.

    Args:
        language: Target language code
        category_name: Grammar category to verify
        request: Contains translation_type and human_verified status

    Returns:
        VerifyCategoryResponse confirming the update

    Raises:
        HTTPException: 400 if invalid category, 404 if not found, 500 on database error
    """
    try:
        if category_name not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {category_name}. Must be one of: {VALID_CATEGORIES}"
            )

        language_code = language.lower().replace(' ', '_').replace('-', '_')
        translation_type = request.translation_type

        database = db.get_database()
        grammar_systems = database[Collection.GRAMMAR_SYSTEMS]

        # Get the specified grammar document
        doc = await grammar_systems.find_one({
            "language_code": language_code,
            "translation_type": translation_type
        })

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"{translation_type.capitalize()} grammar system not found for {language}"
            )

        # Check category exists
        if not doc.get("categories", {}).get(category_name):
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_name}' not found in {translation_type} grammar"
            )

        # Update verification status
        result = await grammar_systems.update_one(
            {
                "language_code": language_code,
                "translation_type": translation_type
            },
            {
                "$set": {
                    f"categories.{category_name}.human_verified": request.human_verified,
                    f"categories.{category_name}.updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update verification status"
            )

        logger.info(
            f"Updated verification for '{category_name}' in {translation_type} "
            f"grammar for {language_code}: {request.human_verified}"
        )

        return VerifyCategoryResponse(
            success=True,
            category_name=category_name,
            language_code=language_code,
            translation_type=translation_type,
            human_verified=request.human_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Verify grammar category {category_name} for {language}", e)
