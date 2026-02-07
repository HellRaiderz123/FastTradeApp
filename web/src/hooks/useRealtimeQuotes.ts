import { useEffect, useState, useRef } from 'react';

export interface QuoteData {
  ltp: number;
  change: number;
  change_percent: number;
  volume: number;
  last_traded_time?: string;
}

export interface QuotesMap {
  [symbol: string]: QuoteData;
}

interface QuoteMessage {
  type: 'connected' | 'quote_update' | 'error';
  data?: QuotesMap;
  symbols?: string[];
  message?: string;
  timestamp?: string;
}

/**
 * React hook for real-time stock quotes via WebSocket
 * 
 * @param symbols - Array of stock symbols to subscribe to
 * @param enabled - Whether to connect to WebSocket (default: true)
 * @returns Object with quotes data, loading state, and error
 * 
 * @example
 * const { quotes, loading, error } = useRealtimeQuotes(['RELIANCE', 'TCS']);
 * console.log(quotes.RELIANCE.ltp); // 2875.40
 */
export function useRealtimeQuotes(symbols: string[], enabled: boolean = true) {
  const [quotes, setQuotes] = useState<QuotesMap>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState<boolean>(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef<number>(0);
  
  useEffect(() => {
    if (!enabled || symbols.length === 0) {
      setLoading(false);
      return;
    }
    
    const connectWebSocket = () => {
      try {
        // Determine WebSocket URL based on environment
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = window.location.hostname === 'localhost' 
          ? 'localhost:8000' 
          : window.location.host;
        
        const symbolsParam = symbols.join(',');
        const wsUrl = `${wsProtocol}//${wsHost}/ws/quotes?symbols=${symbolsParam}`;
        
        console.log(`[useRealtimeQuotes] Connecting to ${wsUrl}`);
        
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;
        
        ws.onopen = () => {
          console.log('[useRealtimeQuotes] Connected');
          setConnected(true);
          setLoading(false);
          setError(null);
          reconnectAttempts.current = 0;
        };
        
        ws.onmessage = (event) => {
          try {
            const message: QuoteMessage = JSON.parse(event.data);
            
            if (message.type === 'connected') {
              console.log('[useRealtimeQuotes] Subscription confirmed:', message.symbols);
            } else if (message.type === 'quote_update' && message.data) {
              setQuotes(message.data);
            } else if (message.type === 'error') {
              console.error('[useRealtimeQuotes] Server error:', message.message);
              setError(message.message || 'Unknown error');
            }
          } catch (err) {
            console.error('[useRealtimeQuotes] Failed to parse message:', err);
          }
        };
        
        ws.onerror = (event) => {
          console.error('[useRealtimeQuotes] WebSocket error:', event);
          setError('WebSocket connection error');
        };
        
        ws.onclose = (event) => {
          console.log('[useRealtimeQuotes] Disconnected:', event.code, event.reason);
          setConnected(false);
          wsRef.current = null;
          
          // Attempt to reconnect with exponential backoff
          if (reconnectAttempts.current < 5) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
            console.log(`[useRealtimeQuotes] Reconnecting in ${delay}ms...`);
            
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttempts.current += 1;
              connectWebSocket();
            }, delay);
          } else {
            setError('Failed to connect after multiple attempts');
            setLoading(false);
          }
        };
      } catch (err) {
        console.error('[useRealtimeQuotes] Connection failed:', err);
        setError('Failed to establish WebSocket connection');
        setLoading(false);
      }
    };
    
    connectWebSocket();
    
    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      if (wsRef.current) {
        console.log('[useRealtimeQuotes] Closing connection');
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [symbols.join(','), enabled]);
  
  return {
    quotes,
    loading,
    error,
    connected,
  };
}
