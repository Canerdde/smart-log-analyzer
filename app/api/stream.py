"""
Real-time log streaming API - WebSocket endpoint'leri
Kullanıcı odaklı, performanslı log streaming
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (APIRouter, Depends, HTTPException, WebSocket,
                     WebSocketDisconnect)
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import LogAnalysis, LogEntry, LogFile

router = APIRouter()


# Aktif WebSocket bağlantılarını yönet
class ConnectionManager:
    def __init__(self):
        # Her file_id için bağlantı listesi
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, file_id: int):
        await websocket.accept()
        if file_id not in self.active_connections:
            self.active_connections[file_id] = []
        self.active_connections[file_id].append(websocket)
        print(
            f"WebSocket bağlantısı: file_id={file_id}, toplam={len(self.active_connections[file_id])}"
        )

    def disconnect(self, websocket: WebSocket, file_id: int):
        if file_id in self.active_connections:
            if websocket in self.active_connections[file_id]:
                self.active_connections[file_id].remove(websocket)
            if len(self.active_connections[file_id]) == 0:
                del self.active_connections[file_id]
        print(f"WebSocket bağlantısı kapatıldı: file_id={file_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            print(f"Mesaj gönderme hatası: {e}")

    async def broadcast_to_file(self, file_id: int, message: str):
        if file_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[file_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Broadcast hatası: {e}")
                    disconnected.append(connection)

            # Bağlantısı kopanları temizle
            for conn in disconnected:
                self.disconnect(conn, file_id)


manager = ConnectionManager()


@router.websocket("/ws/logs/{file_id}")
async def websocket_log_stream(
    websocket: WebSocket,
    file_id: int,
    log_level: Optional[str] = None,
    search: Optional[str] = None,
):
    """
    Real-time log streaming endpoint

    Query Parameters:
    - log_level: ERROR, WARNING, INFO, DEBUG (opsiyonel filtre)
    - search: Mesaj içinde arama (opsiyonel)
    """
    await manager.connect(websocket, file_id)

    try:
        # Dosya kontrolü
        db = SessionLocal()
        log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
        if not log_file:
            await manager.send_personal_message(
                json.dumps({"error": "Log dosyası bulunamadı"}), websocket
            )
            await websocket.close()
            return

        # İlk mesaj: dosya bilgileri
        await manager.send_personal_message(
            json.dumps(
                {
                    "type": "file_info",
                    "data": {
                        "id": log_file.id,
                        "filename": log_file.filename,
                        "total_lines": log_file.total_lines,
                        "status": log_file.status,
                    },
                }
            ),
            websocket,
        )

        # Mevcut logları gönder (son 100)
        entries = db.query(LogEntry).filter(LogEntry.log_file_id == file_id)

        if log_level:
            entries = entries.filter(LogEntry.log_level == log_level.upper())
        if search:
            entries = entries.filter(LogEntry.message.ilike(f"%{search}%"))

        recent_entries = entries.order_by(LogEntry.line_number.desc()).limit(100).all()

        # Ters sırada gönder (en eski önce)
        for entry in reversed(recent_entries):
            await manager.send_personal_message(
                json.dumps(
                    {
                        "type": "log_entry",
                        "data": {
                            "line_number": entry.line_number,
                            "log_level": entry.log_level,
                            "timestamp": (
                                entry.timestamp.isoformat() if entry.timestamp else None
                            ),
                            "message": entry.message,
                        },
                    }
                ),
                websocket,
            )

        await manager.send_personal_message(
            json.dumps({"type": "ready", "message": "Streaming başladı"}), websocket
        )

        # Yeni log girişlerini dinle (polling)
        last_line = recent_entries[0].line_number if recent_entries else 0

        while True:
            # Client'tan mesaj bekle (ping/pong veya filter değişikliği)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message = json.loads(data)

                if message.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}), websocket
                    )
                elif message.get("type") == "filter":
                    # Filtre değişikliği
                    log_level = message.get("log_level")
                    search = message.get("search")
                    # Yeni filtreyle logları tekrar gönder
                    # (basit implementasyon, production'da daha gelişmiş olabilir)
                    pass

            except asyncio.TimeoutError:
                # Timeout - yeni log kontrolü yap
                pass

            # Yeni log girişlerini kontrol et (her 2 saniyede bir)
            new_entries = db.query(LogEntry).filter(
                LogEntry.log_file_id == file_id, LogEntry.line_number > last_line
            )

            if log_level:
                new_entries = new_entries.filter(
                    LogEntry.log_level == log_level.upper()
                )
            if search:
                new_entries = new_entries.filter(LogEntry.message.ilike(f"%{search}%"))

            new_entries = new_entries.order_by(LogEntry.line_number).all()

            for entry in new_entries:
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "log_entry",
                            "data": {
                                "line_number": entry.line_number,
                                "log_level": entry.log_level,
                                "timestamp": (
                                    entry.timestamp.isoformat()
                                    if entry.timestamp
                                    else None
                                ),
                                "message": entry.message,
                            },
                        }
                    ),
                    websocket,
                )
                last_line = entry.line_number

            # CPU kullanımını azaltmak için kısa bekleme
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        manager.disconnect(websocket, file_id)
    except Exception as e:
        print(f"WebSocket hatası: {e}")
        manager.disconnect(websocket, file_id)
        try:
            await websocket.close()
        except:
            pass
    finally:
        db.close()


@router.get("/ws/status/{file_id}")
async def get_stream_status(file_id: int):
    """Aktif WebSocket bağlantı sayısını döndür"""
    count = len(manager.active_connections.get(file_id, []))
    return {"file_id": file_id, "active_connections": count, "is_streaming": count > 0}
