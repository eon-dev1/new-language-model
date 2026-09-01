# grammar.py
"""
Grammar endpoints for language grammar system views.

Provides endpoints to:
- Fetch grammar categories for a language
- Create/update grammar category content
- Update human_verified status for categories, subcategories, notes, examples
"""

from fastapi import APIRouter, HTTPException, Path, Body, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime, timezone
import logging

from db_connector.connection import MongoDBConnector
from constants import Collection
from .dependencies import get_db, api_error

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Pydantic Models ---

class GrammarCategory(BaseModel):
    """Flat grammar category."""
    name: str
    description: str = ""
    subcategories: List[Any] = []  # str or {name, content, examples, human_verified}
    notes: List[Any] = []  # str (legacy) or {text, human_verified} (new format)
    examples: List[Any] = []  # str or {source_text, english, analysis, human_verified}
    ai_confidence: Optional[float] = None
    human_verified: bool = False
    updated_at: Optional[datetime] = None


class CategoriesResponse(BaseModel):
    """Response containing grammar categories."""
    language_code: str
    categories: List[GrammarCategory]
    count: int


class SubcategoryData(BaseModel):
    """Structured subcategory with content and examples."""
    name: str
    content: str = ""
    examples: List[str] = []
    human_verified: bool = False


class NoteData(BaseModel):
    """Structured note with verification status."""
    text: str
    human_verified: bool = False


class ExampleData(BaseModel):
    """Structured example with source, translation, and analysis."""
    source_text: str = ""  # Language-agnostic (replaces legacy 'bughotu')
    english: str = ""
    analysis: str = ""
    human_verified: bool = False


class UpdateCategoryRequest(BaseModel):
    """Request to update grammar category content.

    Write path accepts rich format only. Read path handles both
    legacy flat strings and rich objects via GrammarCategory.
    """
    notes: List[NoteData] = Field(default=[])  # Rich format with verification
    subcategories: List[SubcategoryData] = Field(default=[])  # Rich only
    examples: List[ExampleData] = Field(default=[])           # Rich only


class UpdateCategoryResponse(BaseModel):
    """Response confirming category update."""
    success: bool
    category_name: str
    language_code: str
    action: str  # "updated"


class VerifyRequest(BaseModel):
    """Request to update verification status of any grammar item."""
    human_verified: bool


class VerifyResponseBase(BaseModel):
    """Shared fields for all grammar verify responses."""
    success: bool
    category_name: str
    language_code: str
    human_verified: bool


class VerifyCategoryResponse(VerifyResponseBase):
    pass


class VerifySubcategoryResponse(VerifyResponseBase):
    subcategory_index: int
    subcategory_name: str


class VerifyNoteResponse(VerifyResponseBase):
    note_index: int


class VerifyExampleResponse(VerifyResponseBase):
    example_index: int


# Valid grammar categories
VALID_CATEGORIES = ["phonology", "morphology", "syntax", "semantics", "discourse"]


# --- Endpoints ---

@router.get("/grammar/{language}/categories", response_model=CategoriesResponse)
async def get_grammar_categories(
    language: str = Path(..., description="Language code (e.g., 'kope', 'french')"),
    db: MongoDBConnector = Depends(get_db)
) -> CategoriesResponse:
    """
    Fetch all grammar categories for a language.

    Args:
        language: Target language code

    Returns:
        CategoriesResponse with categories

    Raises:
        HTTPException: 500 on database error
    """
    try:
        language_code = language.lower().replace(' ', '_').replace('-', '_')
        database = db.get_database()
        grammar_systems = database[Collection.GRAMMAR_SYSTEMS]

        doc = await grammar_systems.find_one({"language_code": language_code})

        if not doc:
            # Return empty category shells instead of 404
            logger.info(f"No grammar system found for {language_code}, returning empty shells")
            empty_categories = [GrammarCategory(name=c) for c in VALID_CATEGORIES]
            return CategoriesResponse(
                language_code=language_code,
                categories=empty_categories,
                count=len(empty_categories)
            )

        categories = []
        for category_name in VALID_CATEGORIES:
            cat_data = doc.get("categories", {}).get(category_name, {})
            categories.append(GrammarCategory(
                name=category_name,
                description=cat_data.get("description", ""),
                subcategories=cat_data.get("subcategories", []),
                notes=cat_data.get("notes", []),
                examples=cat_data.get("examples", []),
                ai_confidence=cat_data.get("ai_confidence"),
                human_verified=cat_data.get("human_verified", False),
                updated_at=cat_data.get("updated_at")
            ))

        logger.info(f"Retrieved {len(categories)} grammar categories for {language_code}")

        return CategoriesResponse(
            language_code=language_code,
            categories=categories,
            count=len(categories)
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
    Update grammar category content.

    Updates notes, subcategories, and examples for a specific category.
    Auto-sets human_verified = true.

    Args:
        language: Target language code
        category_name: Grammar category (phonology, morphology, syntax, semantics, discourse)
        request: Category data (notes, examples, subcategories)

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

        # Get the grammar document
        doc = await grammar_systems.find_one({"language_code": language_code})

        if not doc:
            # Create new grammar system document (upsert pattern)
            logger.info(f"Creating new grammar system for {language_code}")
            new_doc = {
                "language_code": language_code,
                "language_name": language_code.replace('_', ' ').title(),
                "grammar_system_name": f"{language_code.replace('_', ' ').title()} Grammar System",
                "created_at": datetime.now(timezone.utc),
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
                    "description": f"Grammar system for {language_code}",
                }
            }
            await grammar_systems.insert_one(new_doc)

        now = datetime.now(timezone.utc)

        # Update the specific category with rich structures
        result = await grammar_systems.update_one(
            {"language_code": language_code},
            {
                "$set": {
                    f"categories.{category_name}.notes": [
                        n.model_dump() for n in request.notes
                    ],
                    f"categories.{category_name}.subcategories": [
                        s.model_dump() for s in request.subcategories
                    ],
                    f"categories.{category_name}.examples": [
                        e.model_dump() for e in request.examples
                    ],
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
    request: VerifyRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> VerifyCategoryResponse:
    """
    Update human_verified status for a grammar category.

    Args:
        language: Target language code
        category_name: Grammar category to verify
        request: Contains human_verified status

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

        database = db.get_database()
        grammar_systems = database[Collection.GRAMMAR_SYSTEMS]

        # Get the grammar document
        doc = await grammar_systems.find_one({"language_code": language_code})

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Grammar system not found for {language}"
            )

        # Check category exists
        if not doc.get("categories", {}).get(category_name):
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_name}' not found in grammar"
            )

        # Update verification status
        result = await grammar_systems.update_one(
            {"language_code": language_code},
            {
                "$set": {
                    f"categories.{category_name}.human_verified": request.human_verified,
                    f"categories.{category_name}.updated_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update verification status"
            )

        logger.info(
            f"Updated verification for '{category_name}' in "
            f"grammar for {language_code}: {request.human_verified}"
        )

        return VerifyCategoryResponse(
            success=True,
            category_name=category_name,
            language_code=language_code,
            human_verified=request.human_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Verify grammar category {category_name} for {language}", e)


@router.patch(
    "/grammar/{language}/categories/{category_name}/subcategories/{index}/verify",
    response_model=VerifySubcategoryResponse
)
async def verify_grammar_subcategory(
    language: str = Path(..., description="Language code"),
    category_name: str = Path(..., description="Category name"),
    index: int = Path(..., ge=0, description="Subcategory index"),
    request: VerifyRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> VerifySubcategoryResponse:
    """
    Update the human_verified status for a specific subcategory.

    Args:
        language: Target language code
        category_name: Grammar category (phonology, morphology, etc.)
        index: Index of the subcategory in the subcategories array
        request: Contains human_verified status

    Returns:
        VerifySubcategoryResponse confirming the update

    Raises:
        HTTPException: 400 if invalid category/index, 404 if not found, 500 on error
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

        # Get the grammar document
        doc = await grammar_systems.find_one({"language_code": language_code})

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Grammar system not found for {language}"
            )

        # Check category and subcategory exist
        category = doc.get("categories", {}).get(category_name)
        if not category:
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_name}' not found in grammar"
            )

        subcategories = category.get("subcategories", [])
        if index >= len(subcategories):
            raise HTTPException(
                status_code=400,
                detail=f"Subcategory index {index} out of range (0-{len(subcategories) - 1})"
            )

        subcategory = subcategories[index]
        subcategory_name = subcategory.get("name", f"Subcategory {index}") if isinstance(subcategory, dict) else str(subcategory)

        # Update verification status for the specific subcategory
        result = await grammar_systems.update_one(
            {"language_code": language_code},
            {
                "$set": {
                    f"categories.{category_name}.subcategories.{index}.human_verified": request.human_verified,
                    f"categories.{category_name}.updated_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update subcategory verification status"
            )

        logger.info(
            f"Updated verification for subcategory '{subcategory_name}' (index {index}) "
            f"in {category_name} for {language_code}: {request.human_verified}"
        )

        return VerifySubcategoryResponse(
            success=True,
            category_name=category_name,
            subcategory_index=index,
            subcategory_name=subcategory_name,
            language_code=language_code,
            human_verified=request.human_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Verify subcategory {index} in {category_name} for {language}", e)


@router.patch(
    "/grammar/{language}/categories/{category_name}/notes/{index}/verify",
    response_model=VerifyNoteResponse
)
async def verify_grammar_note(
    language: str = Path(..., description="Language code"),
    category_name: str = Path(..., description="Category name"),
    index: int = Path(..., ge=0, description="Note index"),
    request: VerifyRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> VerifyNoteResponse:
    """
    Update the human_verified status for a specific note.

    Args:
        language: Target language code
        category_name: Grammar category (phonology, morphology, etc.)
        index: Index of the note in the notes array
        request: Contains human_verified status

    Returns:
        VerifyNoteResponse confirming the update

    Raises:
        HTTPException: 400 if invalid category/index, 404 if not found, 500 on error
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

        # Get the grammar document
        doc = await grammar_systems.find_one({"language_code": language_code})

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Grammar system not found for {language}"
            )

        # Check category and notes exist
        category = doc.get("categories", {}).get(category_name)
        if not category:
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_name}' not found in grammar"
            )

        notes = category.get("notes", [])
        if index >= len(notes):
            raise HTTPException(
                status_code=400,
                detail=f"Note index {index} out of range (0-{len(notes) - 1})"
            )

        # Update verification status for the specific note
        result = await grammar_systems.update_one(
            {"language_code": language_code},
            {
                "$set": {
                    f"categories.{category_name}.notes.{index}.human_verified": request.human_verified,
                    f"categories.{category_name}.updated_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update note verification status"
            )

        logger.info(
            f"Updated verification for note index {index} "
            f"in {category_name} for {language_code}: {request.human_verified}"
        )

        return VerifyNoteResponse(
            success=True,
            category_name=category_name,
            note_index=index,
            language_code=language_code,
            human_verified=request.human_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Verify note {index} in {category_name} for {language}", e)


@router.patch(
    "/grammar/{language}/categories/{category_name}/examples/{index}/verify",
    response_model=VerifyExampleResponse
)
async def verify_grammar_example(
    language: str = Path(..., description="Language code"),
    category_name: str = Path(..., description="Category name"),
    index: int = Path(..., ge=0, description="Example index"),
    request: VerifyRequest = Body(...),
    db: MongoDBConnector = Depends(get_db)
) -> VerifyExampleResponse:
    """
    Update the human_verified status for a specific example.

    Args:
        language: Target language code
        category_name: Grammar category (phonology, morphology, etc.)
        index: Index of the example in the examples array
        request: Contains human_verified status

    Returns:
        VerifyExampleResponse confirming the update

    Raises:
        HTTPException: 400 if invalid category/index, 404 if not found, 500 on error
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

        # Get the grammar document
        doc = await grammar_systems.find_one({"language_code": language_code})

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Grammar system not found for {language}"
            )

        # Check category and examples exist
        category = doc.get("categories", {}).get(category_name)
        if not category:
            raise HTTPException(
                status_code=404,
                detail=f"Category '{category_name}' not found in grammar"
            )

        examples = category.get("examples", [])
        if index >= len(examples):
            raise HTTPException(
                status_code=400,
                detail=f"Example index {index} out of range (0-{len(examples) - 1})"
            )

        # Update verification status for the specific example
        result = await grammar_systems.update_one(
            {"language_code": language_code},
            {
                "$set": {
                    f"categories.{category_name}.examples.{index}.human_verified": request.human_verified,
                    f"categories.{category_name}.updated_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update example verification status"
            )

        logger.info(
            f"Updated verification for example index {index} "
            f"in {category_name} for {language_code}: {request.human_verified}"
        )

        return VerifyExampleResponse(
            success=True,
            category_name=category_name,
            example_index=index,
            language_code=language_code,
            human_verified=request.human_verified
        )

    except HTTPException:
        raise
    except Exception as e:
        raise api_error(f"Verify example {index} in {category_name} for {language}", e)
