"""
@author: caoshuai.cs
@date: 2026-07-12
@description: API v1 路由聚合
"""
from fastapi import APIRouter

from app.api.v1 import ai, feedback, knowledge, skills, user

api_router = APIRouter()
api_router.include_router(user.router)
api_router.include_router(ai.router)
api_router.include_router(knowledge.router)
api_router.include_router(feedback.router)
api_router.include_router(skills.router)
