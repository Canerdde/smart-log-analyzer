"""
Integration API endpoints - Slack, Teams, Jira, Trello test ve yönetim
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_active_user, require_role
from app.models import User

# Integration servisleri
try:
    from app.integrations import (JiraIntegration, SlackIntegration,
                                  TeamsIntegration, TrelloIntegration)

    INTEGRATIONS_AVAILABLE = True
except ImportError:
    INTEGRATIONS_AVAILABLE = False

router = APIRouter()


class SlackTestRequest(BaseModel):
    webhook_url: str
    message: Optional[str] = "Test mesajı"


class TeamsTestRequest(BaseModel):
    webhook_url: str
    message: Optional[str] = "Test mesajı"


class JiraTestRequest(BaseModel):
    jira_url: str
    email: str
    api_token: str
    project_key: str


class TrelloTestRequest(BaseModel):
    api_key: str
    api_token: str
    board_id: str
    list_id: str


@router.post("/slack/test")
async def test_slack_integration(
    request: SlackTestRequest, current_user: User = Depends(get_current_active_user)
):
    """Slack webhook'u test et"""
    if not INTEGRATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Integration modülü mevcut değil")

    success = await SlackIntegration.send_message(
        request.webhook_url,
        request.message or "Test mesajı",
        title="Test Alert",
        color="good",
    )

    return {
        "success": success,
        "message": (
            "Slack webhook test edildi" if success else "Slack webhook test başarısız"
        ),
    }


@router.post("/teams/test")
async def test_teams_integration(
    request: TeamsTestRequest, current_user: User = Depends(get_current_active_user)
):
    """Teams webhook'u test et"""
    if not INTEGRATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Integration modülü mevcut değil")

    success = await TeamsIntegration.send_message(
        request.webhook_url, request.message or "Test mesajı", title="Test Alert"
    )

    return {
        "success": success,
        "message": (
            "Teams webhook test edildi" if success else "Teams webhook test başarısız"
        ),
    }


@router.post("/jira/test")
async def test_jira_integration(
    request: JiraTestRequest, current_user: User = Depends(get_current_active_user)
):
    """Jira bağlantısını test et"""
    if not INTEGRATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Integration modülü mevcut değil")

    issue = await JiraIntegration.create_issue(
        request.jira_url,
        request.email,
        request.api_token,
        request.project_key,
        "Test Issue - Log Analyzer",
        "Bu bir test issue'sudur. Integration çalışıyor!",
        issue_type="Task",
        priority="Low",
    )

    return {
        "success": issue is not None,
        "issue": issue,
        "message": (
            "Jira integration test edildi"
            if issue
            else "Jira integration test başarısız"
        ),
    }


@router.post("/trello/test")
async def test_trello_integration(
    request: TrelloTestRequest, current_user: User = Depends(get_current_active_user)
):
    """Trello bağlantısını test et"""
    if not INTEGRATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Integration modülü mevcut değil")

    card = await TrelloIntegration.create_card(
        request.api_key,
        request.api_token,
        request.board_id,
        request.list_id,
        "Test Card - Log Analyzer",
        "Bu bir test card'ıdır. Integration çalışıyor!",
        labels=["blue"],
    )

    return {
        "success": card is not None,
        "card": card,
        "message": (
            "Trello integration test edildi"
            if card
            else "Trello integration test başarısız"
        ),
    }
