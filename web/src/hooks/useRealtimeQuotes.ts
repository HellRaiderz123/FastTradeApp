import { useEffect, useState, useRef, useCallback } from 'react';
import axios from 'axios';

export interface QuoteData {
  ltp: number;
  change: number;
  change_percent: number;
  volume: number;
  last_traded_time?: string;
  live?: boolean;
  error?: string;
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
 * React hook for real-time stock quotes via WebSocket + REST fallback
 * 
 * 1. Immediately fetches quotes via REST so the UI renders data on first paint
 * 2. Opens a WebSocket for live streaming updates
 * 3. Merges incoming data into existing state (never resets to {})
 * 4. Reconnects with exponential backoff on disconnect
 */
export function useRealtimeQuotes(symbols: string[], enabled: boolean = true) {
  const [quotes, setQuotes] = useState<QuotesMap>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState<boolean>(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef<number>(0);
  const symbolsKey = symbols.join(',');

  // ── Step 1: Fetch quotes via REST for instant first-paint ──
  const fetchInitialQuotes = useCallback(async (symbolsList: string[]) => {
    if (symbolsList.length === 0) return;
    try {
      const resp = await axios.get('/api/market/quotes/bulk', {
        params: { symbols: symbolsList.join(',') },
        timeout: 8000,
      });
      if (resp.data?.success && resp.data.data) {
        setQuotes(prev => ({ ...prev, ...resp.data.data }));
        setLoading(false);
      }
    } catch (err) {
      console.warn('[useRealtimeQuotes] Initial REST fetch failed, waiting for WS:', err);
      // Not fatal — WS will provide data
    }
  }, []);

  useEffect(() => {
    if (!enabled || symbols.length === 0) {
      setLoading(false);
      return;
    }
    
    // Fire-and-forget initial REST fetch
    fetchInitialQuotes(symbols);
    
    const connectWebSocket = () => {
      try {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = window.location.hostname === 'localhost' 
          ? 'localhost:8000' 
          : window.location.host;
        
        const wsUrl = `${wsProtocol}//${wsHost}/ws/quotes?symbols=${symbolsKey}`;
        
        console.log(`[useRealtimeQuotes] Connecting to ${wsUrl}`);
        
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;
        
        ws.onopen = () => {
          console.log('[useRealtimeQuotes] Connected');
          setConnected(true);
          setError(null);
          reconnectAttempts.current = 0;
        };
        
        ws.onmessage = (event) => {
          try {
            const message: QuoteMessage = JSON.parse(event.data);
            
            if (message.type === 'connected') {
              console.log('[useRealtimeQuotes] Subscription confirmed:', message.symbols);
            } else if (message.type === 'quote_update' && message.data) {
              // Merge into existing quotes — never replace wholesale
              setQuotes(prev => ({ ...prev, ...message.data }));
              setLoading(false);  // definitely have data now
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
          
          // DON'T clear quotes — keep last known data visible while reconnecting
          
          if (reconnectAttempts.current < 5) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
            console.log(`[useRealtimeQuotes] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1})...`);
            
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
    
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      if (wsRef.current) {
        console.log('[useRealtimeQuotes] Closing connection');
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [symbolsKey, enabled, fetchInitialQuotes]);
  
  return {
    quotes,
    loading,
    error,
    connected,
  };
}
