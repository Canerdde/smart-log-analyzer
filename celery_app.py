"""
Celery worker başlatma dosyası
Kullanım: celery -A celery_app worker --loglevel=info
"""
from app.tasks import celery_app

if __name__ == '__main__':
    celery_app.start()

