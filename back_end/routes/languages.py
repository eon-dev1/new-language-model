# languages.py
"""
Languages endpoint for listing all available languages in the translation system.

Always auto-detects languages from bible_texts collection to find all language projects.
Returns list of languages with their metadata and translation progress.
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
import logging
from db_connector.connection import MongoDBConnector
from constants import Collection
from .dependencies import get_db, api_error
from utils.usfm_parser.usfm_book_codes import OT_BOOK_CODES

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/languages", response_model=Dict[str, Any])
async def get_languages(db: MongoDBConnector = Depends(get_db)) -> Dict[str, Any]:
    """
    Get all languages in the translation system.

    Always checks bible_texts collection for language projects to ensure
    newly imported projects are detected automatically.

    Returns:
        dict: Contains:
            - languages (list): List of language objects with:
                - language_name (str): Display name
                - language_code (str): Normalized code
                - is_base_language (bool): Whether this is English (base)
                - status (str): active/inactive
                - total_verses (int): Number of verses
                - verified_count (int): Number of human-verified verses
                - verification_progress (dict): Percentage breakdown with:
                    - old_testament (float): OT verification % (0-100)
                    - new_testament (float): NT verification % (0-100)
                    - total (float): Overall verification % (0-100)
            - count (int): Total number of languages

    Raises:
        HTTPException: 500 if database query fails
    """
    try:
        database = db.get_database()
        bible_texts = database[Collection.BIBLE_TEXTS]

        # Aggregation pipeline that calculates OT/NT verification separately
        # Uses book_code to determine testament (OT_BOOK_CODES list vs others)
        pipeline = [
            {
                "$group": {
                    "_id": "$language_code",
                    "language_name": {"$first": {"$ifNull": ["$language_name", "$language_code"]}},
                    "total_verses": {"$sum": 1},
                    "verified_count": {
                        "$sum": {"$cond": [{"$eq": ["$human_verified", True]}, 1, 0]}
                    },
                    # OT verses (book_code in OT_BOOK_CODES)
                    "ot_total": {
                        "$sum": {"$cond": [{"$in": ["$book_code", OT_BOOK_CODES]}, 1, 0]}
                    },
                    "ot_verified": {
                        "$sum": {"$cond": [
                            {"$and": [
                                {"$in": ["$book_code", OT_BOOK_CODES]},
                                {"$eq": ["$human_verified", True]}
                            ]},
                            1, 0
                        ]}
                    },
                    # NT verses (book_code NOT in OT_BOOK_CODES)
                    "nt_total": {
                        "$sum": {"$cond": [{"$not": {"$in": ["$book_code", OT_BOOK_CODES]}}, 1, 0]}
                    },
                    "nt_verified": {
                        "$sum": {"$cond": [
                            {"$and": [
                                {"$not": {"$in": ["$book_code", OT_BOOK_CODES]}},
                                {"$eq": ["$human_verified", True]}
                            ]},
                            1, 0
                        ]}
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "language_code": "$_id",
                    "language_name": {
                        "$cond": {
                            "if": {"$or": [
                                {"$eq": ["$language_name", None]},
                                {"$eq": ["$language_name", ""]}
                            ]},
                            "then": "$_id",
                            "else": "$language_name"
                        }
                    },
                    "total_verses": 1,
                    "verified_count": 1,
                    "verification_progress": {
                        "old_testament": {
                            "$multiply": [
                                {"$divide": [
                                    "$ot_verified",
                                    {"$max": ["$ot_total", 1]}
                                ]},
                                100
                            ]
                        },
                        "new_testament": {
                            "$multiply": [
                                {"$divide": [
                                    "$nt_verified",
                                    {"$max": ["$nt_total", 1]}
                                ]},
                                100
                            ]
                        },
                        "total": {
                            "$multiply": [
                                {"$divide": [
                                    "$verified_count",
                                    {"$max": ["$total_verses", 1]}
                                ]},
                                100
                            ]
                        }
                    },
                    "status": {"$literal": "active"},
                    "is_base_language": {"$eq": ["$_id", "english"]}
                }
            },
            {"$sort": {"language_name": 1}}
        ]

        cursor = bible_texts.aggregate(pipeline)
        languages = await cursor.to_list(length=None)

        logger.info(f"Detected {len(languages)} languages from bible_texts")

        return {
            "languages": languages,
            "count": len(languages)
        }

    except Exception as e:
        raise api_error("Retrieve languages", e)