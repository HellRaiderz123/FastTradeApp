"""
Order Status Monitoring System
Tracks Zerodha order lifecycle with retry logic
"""

import logging
import time
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    """Zerodha order statuses"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    PARTIAL = "PARTIAL"  # Partially filled


class OrderMonitor:
    """
    Monitor Zerodha order status and handle partial fills
    """
    
    def __init__(self, kite_client, db: Session):
        self.kite = kite_client
        self.db = db
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    def place_order_with_monitoring(
        self,
        order_params: Dict[str, Any],
        intent_id: str,
        retry_on_reject: bool = True
    ) -> Dict[str, Any]:
        """
        Place order and monitor until completion
        
        Returns:
            {
                "order_id": "...",
                "status": "COMPLETE",
                "filled_quantity": 100,
                "average_price": 50.25,
                "retries": 0
            }
        """
        
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            try:
                # Place order
                order_id = self._place_order(order_params)
                
                logger.info(f"Order placed: {order_id} for intent {intent_id}")
                
                # Monitor order status
                result = self._monitor_order_status(order_id, timeout=30)
                
                # Handle different statuses
                if result["status"] == OrderStatus.COMPLETE:
                    logger.info(f"✅ Order {order_id} completed successfully")
                    return result
                
                elif result["status"] == OrderStatus.PARTIAL:
                    logger.warning(f"⚠️ Order {order_id} partially filled")
                    # Store partial fill info
                    self._store_partial_fill(intent_id, result)
                    return result
                
                elif result["status"] == OrderStatus.REJECTED:
                    last_error = result.get("rejection_reason", "Unknown")
                    logger.error(f"❌ Order {order_id} rejected: {last_error}")
                    
                    if not retry_on_reject:
                        raise Exception(f"Order rejected: {last_error}")
                    
                    # Retry after delay
                    attempts += 1
                    if attempts < self.max_retries:
                        logger.info(f"Retrying... (Attempt {attempts + 1}/{self.max_retries})")
                        time.sleep(self.retry_delay)
                    
                else:
                    logger.warning(f"⚠️ Order {order_id} status: {result['status']}")
                    return result
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Error placing order (attempt {attempts + 1}): {e}", exc_info=True)
                
                attempts += 1
                if attempts < self.max_retries:
                    time.sleep(self.retry_delay)
        
        # All retries exhausted
        raise Exception(f"Order failed after {self.max_retries} attempts: {last_error}")
    
    def _place_order(self, params: Dict[str, Any]) -> str:
        """Place order via Zerodha API"""
        try:
            order_id = self.kite.place_order(
                variety=params.get("variety", "regular"),
                exchange=params["exchange"],
                tradingsymbol=params["tradingsymbol"],
                transaction_type=params["transaction_type"],
                quantity=params["quantity"],
                order_type=params.get("order_type", "MARKET"),
                product=params.get("product", "NRML"),
                validity=params.get("validity", "DAY"),
                price=params.get("price"),
                trigger_price=params.get("trigger_price")
            )
            
            return order_id
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}", exc_info=True)
            raise
    
    def _monitor_order_status(
        self, 
        order_id: str, 
        timeout: int = 30,
        poll_interval: int = 1
    ) -> Dict[str, Any]:
        """
        Monitor order status until completion or timeout
        
        Polls every `poll_interval` seconds for `timeout` seconds
        """
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Get order status from Zerodha
                orders = self.kite.orders()
                
                order = next((o for o in orders if o["order_id"] == order_id), None)
                
                if not order:
                    logger.warning(f"Order {order_id} not found")
                    time.sleep(poll_interval)
                    continue
                
                status = order["status"]
                
                # Terminal statuses
                if status in ["COMPLETE", "REJECTED", "CANCELLED"]:
                    return {
                        "order_id": order_id,
                        "status": status,
                        "filled_quantity": order.get("filled_quantity", 0),
                        "pending_quantity": order.get("pending_quantity", 0),
                        "average_price": order.get("average_price", 0),
                        "rejection_reason": order.get("status_message"),
                        "timestamp": order.get("order_timestamp")
                    }
                
                # Partial fill
                if order.get("filled_quantity", 0) > 0 and order.get("pending_quantity", 0) > 0:
                    logger.info(f"Order {order_id} partially filled: {order['filled_quantity']}/{order['quantity']}")
                
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring order {order_id}: {e}")
                time.sleep(poll_interval)
        
        # Timeout reached
        logger.warning(f"⏰ Order {order_id} monitoring timeout after {timeout}s")
        
        # Get final status
        try:
            orders = self.kite.orders()
            order = next((o for o in orders if o["order_id"] == order_id), None)
            
            if order:
                return {
                    "order_id": order_id,
                    "status": "TIMEOUT",
                    "filled_quantity": order.get("filled_quantity", 0),
                    "pending_quantity": order.get("pending_quantity", 0),
                    "average_price": order.get("average_price", 0),
                }
        except:
            pass
        
        return {
            "order_id": order_id,
            "status": "TIMEOUT",
            "message": f"Order monitoring timeout after {timeout}s"
        }
    
    def _store_partial_fill(self, intent_id: str, order_result: Dict[str, Any]):
        """Store partial fill information for later reconciliation"""
        from app.db.models import OrderFill
        from app.core.utils.time import now_ist
        
        try:
            fill = OrderFill(
                intent_id=intent_id,
                order_id=order_result["order_id"],
                filled_quantity=order_result["filled_quantity"],
                pending_quantity=order_result["pending_quantity"],
                average_price=order_result["average_price"],
                status="PARTIAL",
                created_at=now_ist()
            )
            
            self.db.add(fill)
            self.db.commit()
            
            logger.info(f"Stored partial fill for intent {intent_id}")
            
        except Exception as e:
            logger.error(f"Failed to store partial fill: {e}")
            self.db.rollback()
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of an order"""
        try:
            orders = self.kite.orders()
            order = next((o for o in orders if o["order_id"] == order_id), None)
            
            if order:
                return {
                    "order_id": order["order_id"],
                    "status": order["status"],
                    "tradingsymbol": order["tradingsymbol"],
                    "quantity": order["quantity"],
                    "filled_quantity": order.get("filled_quantity", 0),
                    "average_price": order.get("average_price", 0),
                    "order_timestamp": order.get("order_timestamp")
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return None
    
    def cancel_order(self, order_id: str, variety: str = "regular") -> bool:
        """Cancel an order"""
        try:
            self.kite.cancel_order(variety=variety, order_id=order_id)
            logger.info(f"✅ Cancelled order {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def reconcile_positions(self) -> Dict[str, Any]:
        """
        Reconcile local positions with Zerodha positions
        
        Returns:
            {
                "matched": [...],
                "missing_local": [...],
                "missing_broker": [...]
            }
        """
        try:
            # Get Zerodha positions
            broker_positions = self.kite.positions()["net"]
            
            # Get local positions
            from app.db.models_intent import ExecutionIntent
            
            local_positions = self.db.query(ExecutionIntent).filter(
                ExecutionIntent.status == "EXECUTED"
            ).all()
            
            matched = []
            missing_local = []
            missing_broker = []
            
            # Build lookup maps
            broker_map = {p["tradingsymbol"]: p for p in broker_positions}
            local_map = {}
            
            for intent in local_positions:
                ticket = intent.ticket
                if ticket and "legs" in ticket:
                    for leg in ticket["legs"]:
                        symbol = leg.get("symbol")
                        if symbol:
                            local_map[symbol] = intent
            
            # Find matches
            for symbol, broker_pos in broker_map.items():
                if symbol in local_map:
                    matched.append({
                        "symbol": symbol,
                        "quantity": broker_pos["quantity"],
                        "status": "matched"
                    })
                else:
                    missing_local.append({
                        "symbol": symbol,
                        "quantity": broker_pos["quantity"],
                        "issue": "Position exists at broker but not tracked locally"
                    })
            
            # Find missing at broker
            for symbol in local_map:
                if symbol not in broker_map:
                    missing_broker.append({
                        "symbol": symbol,
                        "issue": "Position tracked locally but not found at broker"
                    })
            
            logger.info(f"Reconciliation: {len(matched)} matched, {len(missing_local)} missing local, {len(missing_broker)} missing broker")
            
            return {
                "success": True,
                "matched": matched,
                "missing_local": missing_local,
                "missing_broker": missing_broker,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Position reconciliation failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
