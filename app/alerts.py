"""
Alert sistemi - Kritik hatalar için bildirimler
Email, Slack, Webhook desteği
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import AlertRule, AlertHistory, LogEntry, LogFile

# Email gönderme (opsiyonel)
try:
    from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    print("fastapi-mail bulunamadı, email bildirimleri devre dışı")

# HTTP istekleri için
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    try:
        import requests
        HTTPX_AVAILABLE = False
        REQUESTS_AVAILABLE = True
    except ImportError:
        HTTPX_AVAILABLE = False
        REQUESTS_AVAILABLE = False
        print("httpx veya requests bulunamadı, webhook bildirimleri devre dışı")

def get_email_config():
    """Email konfigürasyonunu döndür"""
    if not EMAIL_AVAILABLE:
        return None
    
    return ConnectionConfig(
        MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
        MAIL_FROM=os.getenv("MAIL_FROM", "noreply@loganalyzer.com"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
        MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True
    )

async def send_email_notification(recipients: List[str], subject: str, body: str):
    """Email bildirimi gönder"""
    if not EMAIL_AVAILABLE:
        print("Email modülü bulunamadı, email gönderilemedi")
        return False
    
    try:
        conf = get_email_config()
        if not conf or not conf.MAIL_USERNAME:
            print("Email konfigürasyonu eksik")
            return False
        
        fm = FastMail(conf)
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            body=body,
            subtype="html"
        )
        await fm.send_message(message)
        return True
    except Exception as e:
        print(f"Email gönderme hatası: {e}")
        return False

async def send_slack_notification(webhook_url: str, message: Dict[str, Any]):
    """Slack webhook bildirimi gönder (legacy - yeni integration kullanılabilir)"""
    if not HTTPX_AVAILABLE and not REQUESTS_AVAILABLE:
        print("HTTP client bulunamadı, Slack bildirimi gönderilemedi")
        return False
    
    try:
        if HTTPX_AVAILABLE:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=message, timeout=10.0)
                return response.status_code == 200
        else:
            # requests kullan (sync)
            response = requests.post(webhook_url, json=message, timeout=10)
            return response.status_code == 200
    except Exception as e:
        print(f"Slack bildirimi gönderme hatası: {e}")
        return False

# Yeni integration servisleri
try:
    from app.integrations import SlackIntegration, TeamsIntegration, JiraIntegration, TrelloIntegration
    INTEGRATIONS_AVAILABLE = True
except ImportError:
    INTEGRATIONS_AVAILABLE = False
    print("Integration modülü bulunamadı")

async def send_webhook_notification(webhook_url: str, payload: Dict[str, Any]):
    """Generic webhook bildirimi gönder"""
    if not HTTPX_AVAILABLE and not REQUESTS_AVAILABLE:
        print("HTTP client bulunamadı, webhook bildirimi gönderilemedi")
        return False
    
    try:
        if HTTPX_AVAILABLE:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=10.0)
                return response.status_code == 200
        else:
            response = requests.post(webhook_url, json=payload, timeout=10)
            return response.status_code == 200
    except Exception as e:
        print(f"Webhook bildirimi gönderme hatası: {e}")
        return False

def check_alert_condition(rule: AlertRule, db: Session) -> Optional[Dict[str, Any]]:
    """
    Alert kuralının koşulunu kontrol et
    
    Returns:
        Koşul sağlanıyorsa condition_met dict, değilse None
    """
    condition_type = rule.condition_type
    params = rule.condition_params
    
    if condition_type == "error_count":
        # Belirli bir zaman diliminde hata sayısı kontrolü
        time_window = params.get("time_window", 300)  # Saniye (varsayılan 5 dakika)
        threshold = params.get("threshold", 10)
        log_level = params.get("log_level", "ERROR")
        file_id = params.get("file_id")  # Opsiyonel, belirli dosya için
        
        since = datetime.utcnow() - timedelta(seconds=time_window)
        
        query = db.query(LogEntry).filter(
            LogEntry.log_level == log_level,
            LogEntry.timestamp >= since
        )
        
        if file_id:
            query = query.filter(LogEntry.log_file_id == file_id)
        
        count = query.count()
        
        if count >= threshold:
            return {
                "type": "error_count",
                "count": count,
                "threshold": threshold,
                "time_window": time_window,
                "log_level": log_level
            }
    
    elif condition_type == "pattern_match":
        # Belirli bir pattern'in eşleşmesi
        pattern = params.get("pattern", "")
        file_id = params.get("file_id")
        time_window = params.get("time_window", 300)
        
        since = datetime.utcnow() - timedelta(seconds=time_window)
        
        query = db.query(LogEntry).filter(
            LogEntry.message.ilike(f"%{pattern}%"),
            LogEntry.timestamp >= since
        )
        
        if file_id:
            query = query.filter(LogEntry.log_file_id == file_id)
        
        matches = query.limit(1).all()
        
        if matches:
            return {
                "type": "pattern_match",
                "pattern": pattern,
                "matched_entry": {
                    "id": matches[0].id,
                    "message": matches[0].message[:100],
                    "timestamp": matches[0].timestamp.isoformat() if matches[0].timestamp else None
                }
            }
    
    elif condition_type == "threshold":
        # Genel threshold kontrolü (tüm loglar için)
        threshold = params.get("threshold", 100)
        time_window = params.get("time_window", 300)
        file_id = params.get("file_id")
        
        since = datetime.utcnow() - timedelta(seconds=time_window)
        
        query = db.query(LogEntry).filter(LogEntry.timestamp >= since)
        
        if file_id:
            query = query.filter(LogEntry.log_file_id == file_id)
        
        count = query.count()
        
        if count >= threshold:
            return {
                "type": "threshold",
                "count": count,
                "threshold": threshold,
                "time_window": time_window
            }
    
    return None

async def process_alert_rule(rule: AlertRule, db: Session):
    """
    Alert kuralını kontrol et ve gerekirse bildirim gönder
    """
    if rule.is_active != "active":
        return False
    
    # Cooldown kontrolü
    if rule.last_triggered_at:
        cooldown_end = rule.last_triggered_at + timedelta(seconds=rule.cooldown_period)
        if datetime.utcnow() < cooldown_end:
            return False  # Hala cooldown period içinde
    
    # Koşulu kontrol et
    condition_met = check_alert_condition(rule, db)
    
    if not condition_met:
        return False
    
    # Bildirim gönder
    notification_sent = {}
    channels = rule.notification_channels
    recipients = rule.recipients
    
    # Email bildirimi
    if "email" in channels and "email" in recipients:
        email_list = recipients["email"]
        if isinstance(email_list, list) and email_list:
            subject = f"🚨 Alert: {rule.name}"
            body = f"""
            <h2>Alert Tetiklendi: {rule.name}</h2>
            <p><strong>Koşul:</strong> {condition_met}</p>
            <p><strong>Açıklama:</strong> {rule.description or 'Açıklama yok'}</p>
            <p><strong>Zaman:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
            success = await send_email_notification(email_list, subject, body)
            notification_sent["email"] = {"success": success, "recipients": email_list}
    
    # Slack bildirimi
    if "slack" in channels and "slack_webhook" in recipients:
        webhook_url = recipients["slack_webhook"]
        if webhook_url:
            slack_message = {
                "text": f"🚨 Alert: {rule.name}",
                "attachments": [{
                    "color": "danger",
                    "fields": [
                        {"title": "Koşul", "value": str(condition_met), "short": False},
                        {"title": "Açıklama", "value": rule.description or "Açıklama yok", "short": False},
                        {"title": "Zaman", "value": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), "short": True}
                    ]
                }]
            }
            success = await send_slack_notification(webhook_url, slack_message)
            notification_sent["slack"] = {"success": success}
    
    # Generic webhook
    if "webhook" in channels and "webhook_url" in recipients:
        webhook_url = recipients["webhook_url"]
        if webhook_url:
            payload = {
                "alert_name": rule.name,
                "condition_met": condition_met,
                "description": rule.description,
                "timestamp": datetime.utcnow().isoformat()
            }
            success = await send_webhook_notification(webhook_url, payload)
            notification_sent["webhook"] = {"success": success}
    
    # Alert history'ye kaydet
    alert_history = AlertHistory(
        alert_rule_id=rule.id,
        condition_met=condition_met,
        notification_sent=notification_sent,
        status="sent" if any(n.get("success", False) for n in notification_sent.values()) else "failed"
    )
    db.add(alert_history)
    
    # Rule'u güncelle
    rule.last_triggered_at = datetime.utcnow()
    rule.trigger_count += 1
    db.commit()
    
    return True

