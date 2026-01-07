"""
Phase 2: Strategy Execution Engine with Multi-Strategy Support

This module bridges StrategyConfig (database) with actual execution via StrategyRegistry.
Supports single and multi-strategy parallel execution.
"""

import logging
import json
import math
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.strategies.registry import StrategyRegistry
from app.db.models import StrategyConfig
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def sanitize_json_value(value: Any) -> Any:
    """
    Sanitize values to be JSON serializable.
    Converts NaN, Infinity, -Infinity to None.
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    elif isinstance(value, dict):
        return {k: sanitize_json_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [sanitize_json_value(v) for v in value]
    return value


class StrategyExecutor:
    """Execute a single strategy from database config"""
    
    def __init__(self, strategy_id: int, db: Session):
        """
        Initialize executor with strategy config
        
        Args:
            strategy_id: ID of StrategyConfig in database
            db: SQLAlchemy session
        """
        self.strategy_id = strategy_id
        self.db = db
        self.config = None
        self.strategy_class = None
        
    def load_config(self) -> bool:
        """Load strategy config from database"""
        try:
            # Query by id first, then validate enabled.
            # This avoids edge cases where SQLite boolean values are stored as text/integer
            # and strict SQL comparisons can miss truthy values.
            self.config = (
                self.db.query(StrategyConfig)
                .filter(StrategyConfig.id == self.strategy_id)
                .first()
            )

            if not self.config or not bool(self.config.enabled):
                logger.error(f"Strategy config not found or not enabled: {self.strategy_id}")
                return False
            
            # Get strategy class from registry
            self.strategy_class = StrategyRegistry.get(self.config.strategy_type)
            logger.info(f"✅ Loaded config: {self.config.name} (type: {self.config.strategy_type})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load config: {e}")
            return False
    
    def execute(self, additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute strategy with database config parameters
        
        Args:
            additional_context: Optional extra context to pass to strategy
            
        Returns:
            Execution result dict
        """
        if not self.config or not self.strategy_class:
            return {
                "success": False,
                "error": "Strategy not loaded",
                "strategy_id": self.strategy_id,
            }
        
        try:
            # Build execution context from config + additional context
            context = {
                "underlying": self.config.underlying,
                "parameters": self.config.parameters,
                "config_id": self.config.id,
                "config_name": self.config.name,
            }
            
            if additional_context:
                context.update(additional_context)
            
            # Instantiate and execute strategy
            strategy_instance = self.strategy_class()
            result = strategy_instance.run(context)
            
            # Add execution metadata
            result["strategy_id"] = self.strategy_id
            result["strategy_name"] = self.config.name
            result["executed_at"] = datetime.now().isoformat()
            result["success"] = True
            
            logger.info(f"✅ Strategy executed: {self.config.name} (ID: {self.strategy_id})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Strategy execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "strategy_id": self.strategy_id,
                "strategy_name": self.config.name if self.config else "Unknown",
                "executed_at": datetime.now().isoformat(),
            }


class MultiStrategyExecutor:
    """Execute multiple enabled strategies in parallel"""
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize multi-executor
        
        Args:
            db: SQLAlchemy session (creates new if not provided)
        """
        self.db = db or SessionLocal()
        self.max_workers = 4  # Concurrent strategy limit
        
    def get_enabled_strategies(self) -> List[StrategyConfig]:
        """Get all enabled strategies from database"""
        try:
            strategies = self.db.query(StrategyConfig).filter_by(enabled=True).all()
            logger.info(f"Found {len(strategies)} enabled strategies")
            return strategies
        except Exception as e:
            logger.error(f"Failed to load enabled strategies: {e}")
            return []
    
    def execute_parallel(self, additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute all enabled strategies in parallel
        
        Args:
            additional_context: Optional context passed to all strategies
            
        Returns:
            Aggregated results dict
        """
        strategies = self.get_enabled_strategies()
        
        if not strategies:
            logger.warning("No enabled strategies found")
            return {
                "success": True,
                "total": 0,
                "results": [],
                "errors": [],
            }
        
        results = []
        errors = []
        
        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all strategies
            future_to_strategy = {}
            for strategy_config in strategies:
                future = executor.submit(
                    self._execute_single,
                    strategy_config.id,
                    additional_context
                )
                future_to_strategy[future] = strategy_config
            
            # Collect results as they complete
            for future in as_completed(future_to_strategy):
                strategy_config = future_to_strategy[future]
                try:
                    result = future.result(timeout=30)  # 30s timeout per strategy
                    
                    if result.get("success"):
                        results.append(result)
                    else:
                        errors.append({
                            "strategy_id": strategy_config.id,
                            "strategy_name": strategy_config.name,
                            "error": result.get("error", "Unknown error"),
                        })
                        
                except Exception as e:
                    logger.error(f"Strategy {strategy_config.name} failed: {e}")
                    errors.append({
                        "strategy_id": strategy_config.id,
                        "strategy_name": strategy_config.name,
                        "error": str(e),
                    })
        
        summary = {
            "success": len(errors) == 0,
            "total": len(strategies),
            "completed": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
            "executed_at": datetime.now().isoformat(),
        }
        
        logger.info(f"Multi-execution summary: {summary['completed']} completed, {summary['failed']} failed")
        return summary
    
    def execute_specific(self, strategy_ids: List[int], 
                        additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute specific strategies by ID
        
        Args:
            strategy_ids: List of strategy IDs to execute
            additional_context: Optional context passed to all strategies
            
        Returns:
            Aggregated results dict
        """
        results = []
        errors = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_id = {
                executor.submit(self._execute_single, sid, additional_context): sid
                for sid in strategy_ids
            }
            
            for future in as_completed(future_to_id):
                sid = future_to_id[future]
                try:
                    result = future.result(timeout=30)
                    
                    if result.get("success"):
                        results.append(result)
                    else:
                        errors.append({
                            "strategy_id": sid,
                            "error": result.get("error", "Unknown error"),
                        })
                        
                except Exception as e:
                    logger.error(f"Strategy {sid} failed: {e}")
                    errors.append({
                        "strategy_id": sid,
                        "error": str(e),
                    })
        
        return {
            "success": len(errors) == 0,
            "total": len(strategy_ids),
            "completed": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
            "executed_at": datetime.now().isoformat(),
        }
    
    @staticmethod
    def _execute_single(strategy_id: int, 
                       additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a single strategy (for thread pool)"""
        db = SessionLocal()
        try:
            executor = StrategyExecutor(strategy_id, db)
            if executor.load_config():
                return executor.execute(additional_context)
            else:
                return {
                    "success": False,
                    "error": "Failed to load config",
                    "strategy_id": strategy_id,
                }
        finally:
            db.close()
