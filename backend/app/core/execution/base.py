from abc import ABC, abstractmethod
from typing import Dict, Any


class ExecutionAdapter(ABC):
    """
    Base interface for ALL execution engines
    (Paper, Zerodha, Future brokers)
    """

    @abstractmethod
    def execute(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute entry orders.
        Must return execution result dict.
        """
        pass

    @abstractmethod
    def mtm(self, intent) -> float:
        """
        Mark-to-market PnL.
        Returns unrealized PnL.
        """
        pass

    @abstractmethod
    def exit(self, intent) -> Dict[str, Any]:
        """
        Exit all open positions for intent.
        """
        pass