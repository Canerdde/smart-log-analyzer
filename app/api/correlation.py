"""
Log Correlation API - Farklı log dosyaları arası ilişki analizi, event chain analizi
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from app.database import get_db
from app.models import LogFile, LogEntry
from app.auth import get_current_active_user
from app.models import User

router = APIRouter()

@router.post("/correlate")
async def correlate_logs(
    file_ids: List[int],
    time_window: int = Query(300, description="Zaman penceresi (saniye) - olaylar arası maksimum süre"),
    correlation_type: str = Query("temporal", description="Correlation tipi: temporal, pattern, error_chain"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Birden fazla log dosyası arasında ilişki analizi yap
    
    Args:
        file_ids: Analiz edilecek log dosyası ID'leri
        time_window: Olaylar arası maksimum zaman farkı (saniye)
        correlation_type: temporal (zaman bazlı), pattern (pattern bazlı), error_chain (hata zinciri)
    
    Returns:
        Correlation analiz sonuçları
    """
    if len(file_ids) < 2:
        raise HTTPException(status_code=400, detail="En az 2 dosya seçilmelidir")
    
    # Kullanıcı bazlı filtreleme
    if current_user.role != "admin":
        user_file_ids = db.query(LogFile.id).filter(LogFile.user_id == current_user.id).all()
        user_file_ids = [f[0] for f in user_file_ids]
        file_ids = [fid for fid in file_ids if fid in user_file_ids]
        if not file_ids:
            raise HTTPException(status_code=403, detail="Bu dosyalara erişim yetkiniz yok")
    
    # Log entry'leri al
    all_entries = []
    for file_id in file_ids:
        entries = db.query(LogEntry).filter(
            LogEntry.log_file_id == file_id,
            LogEntry.timestamp.isnot(None)
        ).order_by(LogEntry.timestamp).all()
        
        for entry in entries:
            all_entries.append({
                'file_id': file_id,
                'entry_id': entry.id,
                'timestamp': entry.timestamp,
                'log_level': entry.log_level,
                'message': entry.message,
                'line_number': entry.line_number
            })
    
    if not all_entries:
        raise HTTPException(status_code=404, detail="Timestamp'li log girişi bulunamadı")
    
    # Timestamp'e göre sırala
    all_entries.sort(key=lambda x: x['timestamp'])
    
    if correlation_type == "temporal":
        return _temporal_correlation(all_entries, time_window, file_ids)
    elif correlation_type == "pattern":
        return _pattern_correlation(all_entries, file_ids)
    elif correlation_type == "error_chain":
        return _error_chain_correlation(all_entries, time_window, file_ids)
    else:
        raise HTTPException(status_code=400, detail="Geçersiz correlation tipi")

def _temporal_correlation(entries: List[Dict], time_window: int, file_ids: List[int]) -> Dict[str, Any]:
    """Zaman bazlı correlation - yakın zamanda gerçekleşen olayları grupla"""
    correlations = []
    time_delta = timedelta(seconds=time_window)
    
    for i, entry1 in enumerate(entries):
        related_events = [entry1]
        
        for j, entry2 in enumerate(entries[i+1:], start=i+1):
            if entry2['timestamp'] - entry1['timestamp'] <= time_delta:
                if entry2['file_id'] != entry1['file_id']:  # Farklı dosyalardan
                    related_events.append(entry2)
            else:
                break  # Zaman penceresi dışında
        
        if len(related_events) > 1:
            correlations.append({
                'events': related_events,
                'time_span': (related_events[-1]['timestamp'] - related_events[0]['timestamp']).total_seconds(),
                'file_count': len(set(e['file_id'] for e in related_events))
            })
    
    # En önemli correlation'ları seç (en fazla dosya içeren)
    correlations.sort(key=lambda x: (x['file_count'], -x['time_span']), reverse=True)
    
    return {
        'correlation_type': 'temporal',
        'total_correlations': len(correlations),
        'top_correlations': [
            {
                'events': corr['events'][:10],  # İlk 10 event
                'time_span_seconds': corr['time_span'],
                'files_involved': corr['file_count']
            }
            for corr in correlations[:20]  # İlk 20 correlation
        ]
    }

def _pattern_correlation(entries: List[Dict], file_ids: List[int]) -> Dict[str, Any]:
    """Pattern bazlı correlation - benzer mesajları farklı dosyalarda bul"""
    # Mesaj pattern'lerini grupla
    pattern_groups = defaultdict(list)
    
    for entry in entries:
        # Basit pattern extraction (mesajın ilk 50 karakteri)
        pattern = entry['message'][:50].strip()
        pattern_groups[pattern].append(entry)
    
    # Birden fazla dosyada görünen pattern'ler
    cross_file_patterns = []
    for pattern, pattern_entries in pattern_groups.items():
        unique_files = set(e['file_id'] for e in pattern_entries)
        if len(unique_files) > 1:
            cross_file_patterns.append({
                'pattern': pattern,
                'occurrences': len(pattern_entries),
                'files': list(unique_files),
                'file_count': len(unique_files),
                'sample_entries': pattern_entries[:5]
            })
    
    cross_file_patterns.sort(key=lambda x: (x['file_count'], x['occurrences']), reverse=True)
    
    return {
        'correlation_type': 'pattern',
        'total_patterns': len(cross_file_patterns),
        'top_patterns': cross_file_patterns[:20]
    }

def _error_chain_correlation(entries: List[Dict], time_window: int, file_ids: List[int]) -> Dict[str, Any]:
    """Hata zinciri correlation - ERROR loglarını zaman bazlı zincirle"""
    error_entries = [e for e in entries if e['log_level'] == 'ERROR']
    time_delta = timedelta(seconds=time_window)
    
    chains = []
    current_chain = []
    
    for i, entry in enumerate(error_entries):
        if not current_chain:
            current_chain = [entry]
        else:
            last_entry = current_chain[-1]
            time_diff = entry['timestamp'] - last_entry['timestamp']
            
            if time_diff <= time_delta:
                current_chain.append(entry)
            else:
                if len(current_chain) > 1:
                    chains.append(current_chain)
                current_chain = [entry]
    
    # Son chain'i ekle
    if len(current_chain) > 1:
        chains.append(current_chain)
    
    # Chain'leri analiz et
    analyzed_chains = []
    for chain in chains:
        unique_files = set(e['file_id'] for e in chain)
        time_span = (chain[-1]['timestamp'] - chain[0]['timestamp']).total_seconds()
        
        analyzed_chains.append({
            'chain_length': len(chain),
            'files_involved': list(unique_files),
            'file_count': len(unique_files),
            'time_span_seconds': time_span,
            'events': chain[:10]  # İlk 10 event
        })
    
    analyzed_chains.sort(key=lambda x: (x['file_count'], x['chain_length']), reverse=True)
    
    return {
        'correlation_type': 'error_chain',
        'total_chains': len(analyzed_chains),
        'chains': analyzed_chains[:20]
    }

@router.get("/event-chain/{file_id}")
async def get_event_chain(
    file_id: int,
    start_entry_id: int = Query(..., description="Başlangıç entry ID"),
    max_depth: int = Query(10, description="Maksimum zincir derinliği"),
    time_window: int = Query(300, description="Zaman penceresi (saniye)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Belirli bir log entry'den başlayarak event chain analizi yap"""
    
    # Başlangıç entry'sini al
    start_entry = db.query(LogEntry).filter(LogEntry.id == start_entry_id).first()
    if not start_entry:
        raise HTTPException(status_code=404, detail="Entry bulunamadı")
    
    # Kullanıcı kontrolü
    if current_user.role != "admin":
        file = db.query(LogFile).filter(LogFile.id == file_id).first()
        if not file or file.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Bu dosyaya erişim yetkiniz yok")
    
    if not start_entry.timestamp:
        raise HTTPException(status_code=400, detail="Entry'de timestamp yok")
    
    # Zaman penceresi içindeki entry'leri al
    time_delta = timedelta(seconds=time_window)
    start_time = start_entry.timestamp
    end_time = start_time + time_delta
    
    related_entries = db.query(LogEntry).filter(
        LogEntry.log_file_id == file_id,
        LogEntry.timestamp >= start_time,
        LogEntry.timestamp <= end_time,
        LogEntry.id != start_entry_id
    ).order_by(LogEntry.timestamp).limit(max_depth).all()
    
    chain = [{
        'id': start_entry.id,
        'timestamp': start_entry.timestamp.isoformat(),
        'log_level': start_entry.log_level,
        'message': start_entry.message,
        'line_number': start_entry.line_number
    }]
    
    for entry in related_entries:
        chain.append({
            'id': entry.id,
            'timestamp': entry.timestamp.isoformat() if entry.timestamp else None,
            'log_level': entry.log_level,
            'message': entry.message,
            'line_number': entry.line_number,
            'time_diff_seconds': (entry.timestamp - start_time).total_seconds() if entry.timestamp else None
        })
    
    return {
        'start_entry_id': start_entry_id,
        'chain_length': len(chain),
        'time_window_seconds': time_window,
        'chain': chain
    }

