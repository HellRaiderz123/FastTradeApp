import axios from 'axios';

const CALENDAR_API = axios.create({
  baseURL: 'http://localhost:8000/calendar',
  timeout: 15000,
});

export interface CalendarEvent {
  type: 'earnings' | 'rbi' | 'economic' | 'ipo' | 'dividend' | 'corporate_action' | 'global';
  title: string;
  symbol: string | null;
  date: string;
  time: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
  status: 'scheduled' | 'completed' | 'cancelled';
  actual: string | null;
  forecast: string | null;
  days_until: number;
  countdown: string;
}

export interface CalendarEventsResponse {
  events: CalendarEvent[];
  total_count: number;
  event_types: string[];
  upcoming_high_impact: number;
}

export interface TodayEventsResponse {
  date: string;
  events: CalendarEvent[];
  count: number;
}

export interface WeekEventsResponse {
  start_date: string;
  end_date: string;
  events_by_day: Record<string, CalendarEvent[]>;
  total_count: number;
}

export interface EarningsCalendarResponse {
  earnings: CalendarEvent[];
  count: number;
}

export interface IPOCalendarResponse {
  ipos: CalendarEvent[];
  count: number;
}

export const getCalendarEvents = async (
  days_ahead: number = 30,
  event_type?: string,
  impact?: string
): Promise<CalendarEventsResponse> => {
  const params = new URLSearchParams();
  params.append('days_ahead', days_ahead.toString());
  if (event_type) params.append('event_type', event_type);
  if (impact) params.append('impact', impact);

  const response = await CALENDAR_API.get<CalendarEventsResponse>(`/events?${params.toString()}`);
  return response.data;
};

export const getTodayEvents = async (): Promise<TodayEventsResponse> => {
  const response = await CALENDAR_API.get<TodayEventsResponse>('/today');
  return response.data;
};

export const getWeekEvents = async (): Promise<WeekEventsResponse> => {
  const response = await CALENDAR_API.get<WeekEventsResponse>('/week');
  return response.data;
};

export const getEarningsCalendar = async (days_ahead: number = 30): Promise<EarningsCalendarResponse> => {
  const response = await CALENDAR_API.get<EarningsCalendarResponse>(`/earnings?days_ahead=${days_ahead}`);
  return response.data;
};

export const getIPOCalendar = async (days_ahead: number = 30): Promise<IPOCalendarResponse> => {
  const response = await CALENDAR_API.get<IPOCalendarResponse>(`/ipo?days_ahead=${days_ahead}`);
  return response.data;
};
