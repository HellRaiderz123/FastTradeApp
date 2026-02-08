/**
 * Alerts API Integration
 * Backend: /alerts/*
 */

import api from './api';

export type AlertOperator = 'above' | 'below' | 'above_or_equal' | 'below_or_equal' | 'equal';

export interface AlertCondition {
  operator: AlertOperator;
  price: number;
}

export interface Alert {
  id: number;
  name: string;
  ticker: string;
  alert_type: string;
  condition: AlertCondition;
  is_enabled: boolean;
  is_recurring: boolean;
  notify_via: Record<string, any>;
  trigger_count: number;
  last_triggered_at: string | null;
  created_at: string;
}

export interface CreateAlertRequest {
  name?: string;
  ticker: string;
  alert_type?: string;
  condition: AlertCondition;
  is_enabled?: boolean;
  is_recurring?: boolean;
  notify_via?: Record<string, any>;
  action_on_trigger?: string;
  created_by?: string;
}

export interface UpdateAlertRequest {
  name?: string;
  description?: string;
  condition?: AlertCondition;
  is_enabled?: boolean;
  is_recurring?: boolean;
  notify_via?: Record<string, any>;
  action_on_trigger?: string;
}

export const alertsAPI = {
  /**
   * Create a new alert
   */
  async create(request: CreateAlertRequest): Promise<{ success: boolean; alert: Alert }> {
    const response = await api.post('/alerts/create', request);
    return response.data;
  },

  /**
   * List all alerts (optionally filter by ticker)
   */
  async list(ticker?: string): Promise<{ success: boolean; count: number; alerts: Alert[] }> {
    const response = await api.get('/alerts/list', {
      params: ticker ? { ticker } : undefined,
    });
    return response.data;
  },

  /**
   * Get specific alert by ID
   */
  async get(alertId: number): Promise<{ success: boolean; alert: Alert }> {
    const response = await api.get(`/alerts/${alertId}`);
    return response.data;
  },

  /**
   * Update alert
   */
  async update(alertId: number, request: UpdateAlertRequest): Promise<{ success: boolean; alert: Alert }> {
    const response = await api.patch(`/alerts/${alertId}`, request);
    return response.data;
  },

  /**
   * Enable alert
   */
  async enable(alertId: number): Promise<{ success: boolean; alert: Alert }> {
    const response = await api.post(`/alerts/${alertId}/enable`);
    return response.data;
  },

  /**
   * Disable alert
   */
  async disable(alertId: number): Promise<{ success: boolean; alert: Alert }> {
    const response = await api.post(`/alerts/${alertId}/disable`);
    return response.data;
  },

  /**
   * Delete alert
   */
  async delete(alertId: number): Promise<{ success: boolean; message: string }> {
    const response = await api.delete(`/alerts/${alertId}`);
    return response.data;
  },

  /**
   * Evaluate all alerts (trigger check)
   */
  async evaluate(ticker?: string): Promise<{
    success: boolean;
    count: number;
    triggered: Array<{
      alert_id: number;
      ticker: string;
      current: number;
      target: number;
      operator: string;
    }>;
  }> {
    const response = await api.post('/alerts/evaluate', null, {
      params: ticker ? { ticker } : undefined,
    });
    return response.data;
  },
};
