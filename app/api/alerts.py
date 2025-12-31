"""
Alert API endpoints
Kritik hatalar için bildirim sistemi
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import AlertRule, AlertHistory
from app.schemas import AlertRuleCreate, AlertRuleResponse, AlertHistoryResponse
from app.alerts import process_alert_rule

router = APIRouter()


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(rule: AlertRuleCreate, db: Session = Depends(get_db)):
    """Yeni bir alert kuralı oluştur"""
    # Aynı isimde kural var mı kontrol et
    existing = db.query(AlertRule).filter(AlertRule.name == rule.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"'{rule.name}' adında bir alert kuralı zaten mevcut",
        )

    alert_rule = AlertRule(
        name=rule.name,
        description=rule.description,
        condition_type=rule.condition_type,
        condition_params=rule.condition_params,
        notification_channels=rule.notification_channels,
        recipients=rule.recipients,
        is_active=rule.is_active,
        cooldown_period=rule.cooldown_period,
    )

    db.add(alert_rule)
    db.commit()
    db.refresh(alert_rule)

    return alert_rule


@router.get("", response_model=List[AlertRuleResponse])
async def list_alert_rules(db: Session = Depends(get_db)):
    """Tüm alert kurallarını listele"""
    rules = db.query(AlertRule).order_by(AlertRule.created_at.desc()).all()
    return rules


@router.get("/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """Belirli bir alert kuralını getir"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert kuralı bulunamadı")
    return rule


@router.put("/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int, rule: AlertRuleCreate, db: Session = Depends(get_db)
):
    """Alert kuralını güncelle"""
    alert_rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not alert_rule:
        raise HTTPException(status_code=404, detail="Alert kuralı bulunamadı")

    # İsim değişiyorsa benzersizlik kontrolü
    if rule.name != alert_rule.name:
        existing = (
            db.query(AlertRule)
            .filter(AlertRule.name == rule.name, AlertRule.id != rule_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"'{rule.name}' adında bir alert kuralı zaten mevcut",
            )

    alert_rule.name = rule.name
    alert_rule.description = rule.description
    alert_rule.condition_type = rule.condition_type
    alert_rule.condition_params = rule.condition_params
    alert_rule.notification_channels = rule.notification_channels
    alert_rule.recipients = rule.recipients
    alert_rule.is_active = rule.is_active
    alert_rule.cooldown_period = rule.cooldown_period
    alert_rule.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(alert_rule)

    return alert_rule


@router.delete("/{rule_id}")
async def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """Alert kuralını sil"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert kuralı bulunamadı")

    db.delete(rule)
    db.commit()

    return {"message": "Alert kuralı silindi"}


@router.post("/{rule_id}/test")
async def test_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """Alert kuralını test et (hemen kontrol et)"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert kuralı bulunamadı")

    # Cooldown'u geçici olarak devre dışı bırak
    original_last_triggered = rule.last_triggered_at
    rule.last_triggered_at = None

    try:
        result = await process_alert_rule(rule, db)
        return {
            "triggered": result,
            "message": "Alert test edildi" if result else "Koşul sağlanmadı",
        }
    finally:
        # Orijinal değeri geri yükle (test için değiştirdik)
        rule.last_triggered_at = original_last_triggered
        db.commit()


@router.get("/{rule_id}/history", response_model=List[AlertHistoryResponse])
async def get_alert_history(
    rule_id: int, limit: int = 50, db: Session = Depends(get_db)
):
    """Alert kuralının geçmişini getir"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert kuralı bulunamadı")

    history = (
        db.query(AlertHistory)
        .filter(AlertHistory.alert_rule_id == rule_id)
        .order_by(AlertHistory.triggered_at.desc())
        .limit(limit)
        .all()
    )

    return history


@router.post("/check-all")
async def check_all_alerts(db: Session = Depends(get_db)):
    """Tüm aktif alert kurallarını kontrol et (manuel tetikleme)"""
    active_rules = db.query(AlertRule).filter(AlertRule.is_active == "active").all()

    results = []
    for rule in active_rules:
        try:
            triggered = await process_alert_rule(rule, db)
            results.append(
                {"rule_id": rule.id, "rule_name": rule.name, "triggered": triggered}
            )
        except Exception as e:
            results.append(
                {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "triggered": False,
                    "error": str(e),
                }
            )

    return {
        "checked_rules": len(active_rules),
        "triggered_count": sum(1 for r in results if r.get("triggered")),
        "results": results,
    }
