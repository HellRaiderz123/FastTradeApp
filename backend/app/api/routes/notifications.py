"""
Notification API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.services.notifications import get_notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================
# SCHEMAS
# ============================

class MarkAsReadRequest(BaseModel):
    notification_ids: List[int]


# ============================
# ENDPOINTS
# ============================

@router.get("/unread")
def get_unread_notifications(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all unread notifications"""
    service = get_notification_service(db)
    notifications = service.get_unread_notifications(limit=limit)
    
    return {
        "success": True,
        "count": len(notifications),
        "notifications": notifications
    }


@router.get("/all")
def get_all_notifications(
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all notifications (read and unread)"""
    from app.db.models_notification import Notification
    
    notifications = (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return {
        "success": True,
        "count": len(notifications),
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "priority": n.priority,
                "metadata": getattr(n, 'data', None) or {},
                "read": n.read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ]
    }


@router.post("/mark-read")
def mark_notifications_read(
    request: MarkAsReadRequest,
    db: Session = Depends(get_db)
):
    """Mark notifications as read"""
    service = get_notification_service(db)
    service.mark_as_read(request.notification_ids)
    
    return {
        "success": True,
        "message": f"Marked {len(request.notification_ids)} notifications as read"
    }


@router.post("/mark-all-read")
def mark_all_notifications_read(db: Session = Depends(get_db)):
    """Mark all notifications as read"""
    from app.db.models_notification import Notification
    
    try:
        db.query(Notification).filter(
            Notification.read == False
        ).update({"read": True}, synchronize_session=False)
        
        db.commit()
        
        return {
            "success": True,
            "message": "All notifications marked as read"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear-old")
def clear_old_notifications(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Clear notifications older than N days"""
    service = get_notification_service(db)
    service.clear_old_notifications(days=days)
    
    return {
        "success": True,
        "message": f"Cleared notifications older than {days} days"
    }


@router.get("/unread-count")
def get_unread_count(db: Session = Depends(get_db)):
    """Get count of unread notifications"""
    from app.db.models_notification import Notification
    
    count = db.query(Notification).filter(Notification.read == False).count()
    
    return {
        "success": True,
        "count": count
    }
