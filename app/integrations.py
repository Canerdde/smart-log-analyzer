"""
Integration Services - Slack, Teams, Jira, Trello, Webhook
"""
import httpx
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

class IntegrationService:
    """Integration servisleri için base class"""
    
    @staticmethod
    async def send_webhook(url: str, payload: Dict[str, Any]) -> bool:
        """Generic webhook gönderimi"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                return response.status_code in [200, 201, 204]
        except Exception as e:
            print(f"Webhook gönderim hatası: {e}")
            return False

class SlackIntegration(IntegrationService):
    """Slack integration"""
    
    @staticmethod
    async def send_message(
        webhook_url: str,
        message: str,
        title: str = "Log Analyzer Alert",
        color: str = "danger",  # good, warning, danger
        fields: Optional[List[Dict[str, str]]] = None
    ) -> bool:
        """Slack webhook'a mesaj gönder"""
        payload = {
            "text": title,
            "attachments": [
                {
                    "color": color,
                    "text": message,
                    "fields": fields or [],
                    "footer": "Smart Log Analyzer",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }
        return await IntegrationService.send_webhook(webhook_url, payload)
    
    @staticmethod
    async def send_alert(
        webhook_url: str,
        alert_name: str,
        condition: str,
        log_entries: List[Dict[str, Any]],
        threshold: int
    ) -> bool:
        """Slack'e alert gönder"""
        fields = [
            {"title": "Alert", "value": alert_name, "short": True},
            {"title": "Condition", "value": condition, "short": True},
            {"title": "Threshold", "value": str(threshold), "short": True},
            {"title": "Matches", "value": str(len(log_entries)), "short": True}
        ]
        
        message = f"Alert tetiklendi: {alert_name}\n"
        if log_entries:
            message += f"Örnek log: {log_entries[0].get('message', '')[:200]}"
        
        return await SlackIntegration.send_message(
            webhook_url,
            message,
            title="🚨 Log Analyzer Alert",
            color="danger",
            fields=fields
        )

class TeamsIntegration(IntegrationService):
    """Microsoft Teams integration"""
    
    @staticmethod
    async def send_message(
        webhook_url: str,
        message: str,
        title: str = "Log Analyzer Alert",
        theme_color: str = "FF0000"
    ) -> bool:
        """Teams webhook'a mesaj gönder"""
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": theme_color,
            "title": title,
            "text": message,
            "sections": []
        }
        return await IntegrationService.send_webhook(webhook_url, payload)
    
    @staticmethod
    async def send_alert(
        webhook_url: str,
        alert_name: str,
        condition: str,
        log_entries: List[Dict[str, Any]],
        threshold: int
    ) -> bool:
        """Teams'e alert gönder"""
        facts = [
            {"name": "Alert", "value": alert_name},
            {"name": "Condition", "value": condition},
            {"name": "Threshold", "value": str(threshold)},
            {"name": "Matches", "value": str(len(log_entries))}
        ]
        
        message = f"Alert tetiklendi: {alert_name}"
        if log_entries:
            message += f"\n\nÖrnek log:\n{log_entries[0].get('message', '')[:500]}"
        
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": "Log Analyzer Alert",
            "themeColor": "FF0000",
            "title": "🚨 Log Analyzer Alert",
            "text": message,
            "sections": [
                {
                    "facts": facts,
                    "markdown": True
                }
            ]
        }
        return await IntegrationService.send_webhook(webhook_url, payload)

class JiraIntegration(IntegrationService):
    """Jira integration - Issue oluşturma"""
    
    @staticmethod
    async def create_issue(
        jira_url: str,
        email: str,
        api_token: str,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "High"
    ) -> Optional[Dict[str, Any]]:
        """Jira'da issue oluştur"""
        try:
            auth = (email, api_token)
            url = f"{jira_url.rstrip('/')}/rest/api/3/issue"
            
            payload = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": description
                                    }
                                ]
                            }
                        ]
                    },
                    "issuetype": {"name": issue_type},
                    "priority": {"name": priority}
                }
            }
            
            async with httpx.AsyncClient(auth=auth, timeout=10.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    print(f"Jira issue oluşturma hatası: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"Jira integration hatası: {e}")
            return None
    
    @staticmethod
    async def create_issue_from_alert(
        jira_url: str,
        email: str,
        api_token: str,
        project_key: str,
        alert_name: str,
        condition: str,
        log_entries: List[Dict[str, Any]],
        threshold: int
    ) -> Optional[Dict[str, Any]]:
        """Alert'ten Jira issue oluştur"""
        summary = f"Log Alert: {alert_name}"
        description = f"""
Alert tetiklendi: {alert_name}

Condition: {condition}
Threshold: {threshold}
Matches: {len(log_entries)}

Örnek log entries:
{chr(10).join([f"- {entry.get('message', '')[:200]}" for entry in log_entries[:5]])}
        """.strip()
        
        return await JiraIntegration.create_issue(
            jira_url, email, api_token, project_key,
            summary, description, issue_type="Bug", priority="High"
        )

class TrelloIntegration(IntegrationService):
    """Trello integration - Card oluşturma"""
    
    @staticmethod
    async def create_card(
        api_key: str,
        api_token: str,
        board_id: str,
        list_id: str,
        name: str,
        description: str,
        labels: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Trello'da card oluştur"""
        try:
            url = "https://api.trello.com/1/cards"
            params = {
                "key": api_key,
                "token": api_token,
                "idList": list_id,
                "name": name,
                "desc": description
            }
            
            if labels:
                params["idLabels"] = ",".join(labels)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, params=params)
                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    print(f"Trello card oluşturma hatası: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"Trello integration hatası: {e}")
            return None
    
    @staticmethod
    async def create_card_from_alert(
        api_key: str,
        api_token: str,
        board_id: str,
        list_id: str,
        alert_name: str,
        condition: str,
        log_entries: List[Dict[str, Any]],
        threshold: int
    ) -> Optional[Dict[str, Any]]:
        """Alert'ten Trello card oluştur"""
        name = f"🚨 {alert_name}"
        description = f"""
Alert tetiklendi: {alert_name}

**Condition:** {condition}
**Threshold:** {threshold}
**Matches:** {len(log_entries)}

**Örnek log entries:**
{chr(10).join([f"- {entry.get('message', '')[:200]}" for entry in log_entries[:5]])}
        """.strip()
        
        return await TrelloIntegration.create_card(
            api_key, api_token, board_id, list_id,
            name, description, labels=["red"]  # Kırmızı label (alert)
        )

