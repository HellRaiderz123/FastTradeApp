import React, { useState, useEffect } from 'react';
import {
  getCalendarEvents,
  getTodayEvents,
  CalendarEvent,
} from '../api/calendarAPI';
import {
  Calendar as CalendarIcon,
  TrendingUp,
  Building2,
  Globe2,
  CalendarDays,
  DollarSign,
  Briefcase,
  Clock,
  AlertCircle,
  Filter,
} from 'lucide-react';

interface EconomicCalendarProps {
  height?: number;
  compact?: boolean;
}

const EconomicCalendar: React.FC<EconomicCalendarProps> = ({ height = 700, compact = false }) => {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedImpact, setSelectedImpact] = useState<string>('all');
  const [daysAhead, setDaysAhead] = useState<number>(30);
  const [showToday, setShowToday] = useState(false);

  useEffect(() => {
    loadCalendar();

    // Auto-refresh every 5 minutes
    const interval = setInterval(() => {
      loadCalendar();
    }, 300000);

    return () => clearInterval(interval);
  }, [selectedType, selectedImpact, daysAhead, showToday]);

  const loadCalendar = async () => {
    try {
      setLoading(true);
      
      if (showToday) {
        const response = await getTodayEvents();
        setEvents(response.events);
      } else {
        const response = await getCalendarEvents(
          daysAhead,
          selectedType === 'all' ? undefined : selectedType,
          selectedImpact === 'all' ? undefined : selectedImpact
        );
        setEvents(response.events);
      }
    } catch (error) {
      console.error('Failed to load calendar:', error);
    } finally {
      setLoading(false);
    }
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'earnings':
        return <TrendingUp className="w-4 h-4" />;
      case 'rbi':
      case 'economic':
        return <Building2 className="w-4 h-4" />;
      case 'ipo':
        return <Briefcase className="w-4 h-4" />;
      case 'dividend':
        return <DollarSign className="w-4 h-4" />;
      case 'corporate_action':
        return <Briefcase className="w-4 h-4" />;
      case 'global':
        return <Globe2 className="w-4 h-4" />;
      default:
        return <CalendarIcon className="w-4 h-4" />;
    }
  };

  const getEventColor = (type: string) => {
    switch (type) {
      case 'earnings':
        return 'bg-green-500/20 text-green-300 border-green-500/40';
      case 'rbi':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/40';
      case 'economic':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/40';
      case 'ipo':
        return 'bg-orange-500/20 text-orange-300 border-orange-500/40';
      case 'dividend':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
      case 'corporate_action':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40';
      case 'global':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
      default:
        return 'bg-gray-500/20 text-gray-300 border-gray-500/40';
    }
  };

  const getImpactBadge = (impact: string) => {
    switch (impact) {
      case 'high':
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/40 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" />
            HIGH
          </span>
        );
      case 'medium':
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/20 text-yellow-300 border border-yellow-500/40">
            MED
          </span>
        );
      case 'low':
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/40">
            LOW
          </span>
        );
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    if (date.toDateString() === today.toDateString()) {
      return 'Today';
    } else if (date.toDateString() === tomorrow.toDateString()) {
      return 'Tomorrow';
    } else {
      return date.toLocaleDateString('en-IN', { 
        weekday: 'short', 
        month: 'short', 
        day: 'numeric' 
      });
    }
  };

  const groupEventsByDate = () => {
    const grouped: Record<string, CalendarEvent[]> = {};
    
    events.forEach(event => {
      if (!grouped[event.date]) {
        grouped[event.date] = [];
      }
      grouped[event.date].push(event);
    });

    return grouped;
  };

  const eventsByDate = groupEventsByDate();
  const dates = Object.keys(eventsByDate).sort();

  return (
    <div style={{ height: `${height}px` }} className="flex flex-col">
      {/* Header with Filters */}
      <div className="mb-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CalendarIcon className="w-5 h-5 text-blue-400" />
            <h3 className="text-lg font-semibold text-gray-200">Economic Calendar</h3>
          </div>
          <button
            onClick={() => setShowToday(!showToday)}
            className={`px-3 py-1.5 rounded text-xs font-semibold transition ${
              showToday
                ? 'bg-blue-500/30 text-blue-300 border border-blue-500/50'
                : 'bg-slate-700/50 text-gray-400 border border-slate-600 hover:bg-slate-700'
            }`}
          >
            {showToday ? 'Show All' : 'Today Only'}
          </button>
        </div>

        {!showToday && (
          <div className="flex items-center gap-2 flex-wrap">
            {/* Event Type Filter */}
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-gray-300 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Types</option>
              <option value="earnings">Earnings</option>
              <option value="rbi">RBI</option>
              <option value="economic">Economic Data</option>
              <option value="ipo">IPO</option>
              <option value="dividend">Dividend</option>
              <option value="corporate_action">Corporate Actions</option>
              <option value="global">Global</option>
            </select>

            {/* Impact Filter */}
            <select
              value={selectedImpact}
              onChange={(e) => setSelectedImpact(e.target.value)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-gray-300 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Impact</option>
              <option value="high">High Impact</option>
              <option value="medium">Medium Impact</option>
              <option value="low">Low Impact</option>
            </select>

            {/* Days Ahead Filter */}
            <select
              value={daysAhead}
              onChange={(e) => setDaysAhead(Number(e.target.value))}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-gray-300 focus:outline-none focus:border-blue-500"
            >
              <option value={7}>Next 7 Days</option>
              <option value={14}>Next 2 Weeks</option>
              <option value={30}>Next Month</option>
              <option value={60}>Next 2 Months</option>
            </select>

            <div className="text-xs text-gray-500 ml-2">
              {events.length} event{events.length !== 1 ? 's' : ''}
            </div>
          </div>
        )}
      </div>

      {/* Events List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-4">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-gray-400 text-sm">Loading calendar...</div>
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-gray-500">
            <CalendarDays className="w-12 h-12 mb-2 opacity-50" />
            <div className="text-sm">No events found</div>
          </div>
        ) : (
          dates.map((date) => (
            <div key={date} className="space-y-2">
              {/* Date Header */}
              <div className="sticky top-0 z-10 bg-slate-900/90 backdrop-blur-sm border-b border-slate-700 pb-2">
                <div className="flex items-center gap-2">
                  <CalendarDays className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-semibold text-gray-300">
                    {formatDate(date)}
                  </span>
                  <span className="text-xs text-gray-500">
                    {eventsByDate[date].length} event{eventsByDate[date].length !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>

              {/* Events for this date */}
              <div className="space-y-2">
                {eventsByDate[date].map((event, index) => (
                  <div
                    key={`${event.type}-${event.symbol}-${index}`}
                    className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 hover:border-slate-600 hover:bg-slate-800/70 transition-all"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2 flex-1">
                        <div className={`p-1.5 rounded ${getEventColor(event.type)}`}>
                          {getEventIcon(event.type)}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="text-sm font-semibold text-gray-200">
                              {event.title}
                            </h4>
                            {event.symbol && (
                              <span className="text-xs font-mono bg-slate-700/50 px-2 py-0.5 rounded text-gray-300">
                                {event.symbol}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                        {getImpactBadge(event.impact)}
                        <div className="flex items-center gap-1 text-xs text-gray-500">
                          <Clock className="w-3 h-3" />
                          {event.time}
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-gray-400 mb-2 leading-relaxed">
                      {event.description}
                    </p>

                    {event.forecast && (
                      <div className="flex items-start gap-4 text-xs">
                        <div className="flex-1">
                          <span className="text-gray-500">Forecast:</span>
                          <span className="text-gray-300 ml-2">{event.forecast}</span>
                        </div>
                        {event.actual && (
                          <div className="flex-1">
                            <span className="text-gray-500">Actual:</span>
                            <span className="text-green-400 ml-2 font-semibold">{event.actual}</span>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="mt-2 pt-2 border-t border-slate-700/50 flex items-center justify-between">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${getEventColor(event.type)}`}>
                        {event.type.replace('_', ' ').toUpperCase()}
                      </span>
                      <span className="text-xs text-gray-500 font-medium">
                        {event.countdown}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Summary Footer */}
      {!loading && events.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-700">
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-red-500/10 rounded p-2 border border-red-500/30">
              <div className="text-lg font-bold text-red-400">
                {events.filter((e) => e.impact === 'high').length}
              </div>
              <div className="text-xs text-gray-400">High Impact</div>
            </div>
            <div className="bg-yellow-500/10 rounded p-2 border border-yellow-500/30">
              <div className="text-lg font-bold text-yellow-400">
                {events.filter((e) => e.impact === 'medium').length}
              </div>
              <div className="text-xs text-gray-400">Medium</div>
            </div>
            <div className="bg-blue-500/10 rounded p-2 border border-blue-500/30">
              <div className="text-lg font-bold text-blue-400">
                {events.filter((e) => e.impact === 'low').length}
              </div>
              <div className="text-xs text-gray-400">Low</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EconomicCalendar;
