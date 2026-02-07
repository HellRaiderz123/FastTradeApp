"""
Economic Calendar API
Events, earnings, RBI meetings, IPO schedule, dividends, corporate actions
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import random

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calendar", tags=["economic_calendar"])


# Mock upcoming events for next 30 days
def generate_economic_calendar(days_ahead: int = 30, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate mock economic calendar events"""
    
    base_date = datetime.now()
    events = []
    
    # Earnings announcements
    earnings_stocks = [
        {"symbol": "TCS", "name": "Tata Consultancy Services", "estimate": "Q4 EPS ₹125", "impact": "high"},
        {"symbol": "INFY", "name": "Infosys", "estimate": "Q4 EPS ₹95", "impact": "high"},
        {"symbol": "RELIANCE", "name": "Reliance Industries", "estimate": "Q4 EPS ₹102", "impact": "high"},
        {"symbol": "HDFCBANK", "name": "HDFC Bank", "estimate": "Q4 EPS ₹48", "impact": "high"},
        {"symbol": "ICICIBANK", "name": "ICICI Bank", "estimate": "Q4 EPS ₹45", "impact": "medium"},
        {"symbol": "WIPRO", "name": "Wipro", "estimate": "Q4 EPS ₹32", "impact": "medium"},
        {"symbol": "TATAMOTORS", "name": "Tata Motors", "estimate": "Q4 EPS ₹38", "impact": "medium"},
        {"symbol": "MARUTI", "name": "Maruti Suzuki", "estimate": "Q4 EPS ₹425", "impact": "medium"},
        {"symbol": "SUNPHARMA", "name": "Sun Pharma", "estimate": "Q4 EPS ₹52", "impact": "low"},
        {"symbol": "TITAN", "name": "Titan Company", "estimate": "Q4 EPS ₹68", "impact": "medium"},
    ]
    
    for i, stock in enumerate(earnings_stocks):
        event_date = base_date + timedelta(days=random.randint(1, days_ahead))
        events.append({
            "type": "earnings",
            "title": f"{stock['name']} Q4 Results",
            "symbol": stock["symbol"],
            "date": event_date.strftime("%Y-%m-%d"),
            "time": "16:00",
            "description": stock["estimate"],
            "impact": stock["impact"],
            "status": "scheduled",
            "actual": None,
            "forecast": stock["estimate"],
        })
    
    # RBI & Economic Data
    economic_events = [
        {
            "type": "rbi",
            "title": "RBI Monetary Policy Meeting",
            "symbol": None,
            "date": (base_date + timedelta(days=8)).strftime("%Y-%m-%d"),
            "time": "10:00",
            "description": "Interest rate decision expected - Current repo rate 6.50%",
            "impact": "high",
            "status": "scheduled",
            "actual": None,
            "forecast": "6.50% (no change expected)",
        },
        {
            "type": "economic",
            "title": "CPI Inflation Data",
            "symbol": None,
            "date": (base_date + timedelta(days=12)).strftime("%Y-%m-%d"),
            "time": "17:30",
            "description": "January 2026 Consumer Price Index",
            "impact": "high",
            "status": "scheduled",
            "actual": None,
            "forecast": "5.8% YoY",
        },
        {
            "type": "economic",
            "title": "GDP Growth Data",
            "symbol": None,
            "date": (base_date + timedelta(days=20)).strftime("%Y-%m-%d"),
            "time": "17:30",
            "description": "Q3 FY26 GDP Growth Rate",
            "impact": "high",
            "status": "scheduled",
            "actual": None,
            "forecast": "7.0% YoY",
        },
        {
            "type": "economic",
            "title": "Manufacturing PMI",
            "symbol": None,
            "date": (base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
            "time": "09:30",
            "description": "February 2026 Manufacturing PMI",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "57.5",
        },
        {
            "type": "economic",
            "title": "Services PMI",
            "symbol": None,
            "date": (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
            "time": "09:30",
            "description": "February 2026 Services PMI",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "61.2",
        },
        {
            "type": "economic",
            "title": "IIP Data",
            "symbol": None,
            "date": (base_date + timedelta(days=15)).strftime("%Y-%m-%d"),
            "time": "17:30",
            "description": "December 2025 Industrial Production",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "5.2% YoY",
        },
        {
            "type": "economic",
            "title": "Trade Balance",
            "symbol": None,
            "date": (base_date + timedelta(days=18)).strftime("%Y-%m-%d"),
            "time": "12:00",
            "description": "January 2026 Import-Export Data",
            "impact": "low",
            "status": "scheduled",
            "actual": None,
            "forecast": "Deficit: $23.5B",
        },
        {
            "type": "economic",
            "title": "GST Collection",
            "symbol": None,
            "date": (base_date + timedelta(days=2)).strftime("%Y-%m-%d"),
            "time": "20:00",
            "description": "January 2026 GST Revenue",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "₹1.68 Lakh Crore",
        },
    ]
    
    events.extend(economic_events)
    
    # IPO Schedule
    ipo_events = [
        {
            "type": "ipo",
            "title": "Waaree Energies IPO Opens",
            "symbol": "WAAREE",
            "date": (base_date + timedelta(days=4)).strftime("%Y-%m-%d"),
            "time": "09:15",
            "description": "Issue size: ₹4,321 Cr | Price band: ₹1,427-1,503",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "Subscription: 15-20x expected",
        },
        {
            "type": "ipo",
            "title": "Premier Energies IPO Closes",
            "symbol": "PREMIER",
            "date": (base_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "time": "17:00",
            "description": "Issue size: ₹2,830 Cr | Current subscription: 8.2x",
            "impact": "low",
            "status": "scheduled",
            "actual": None,
            "forecast": "Grey market premium: ₹125",
        },
        {
            "type": "ipo",
            "title": "Gopal Snacks Listing",
            "symbol": "GOPALSNACKS",
            "date": (base_date + timedelta(days=6)).strftime("%Y-%m-%d"),
            "time": "09:15",
            "description": "IPO listing on exchanges",
            "impact": "low",
            "status": "scheduled",
            "actual": None,
            "forecast": "Premium expected: 25-30%",
        },
    ]
    
    events.extend(ipo_events)
    
    # Dividends
    dividend_events = [
        {
            "type": "dividend",
            "title": "TCS Dividend",
            "symbol": "TCS",
            "date": (base_date + timedelta(days=10)).strftime("%Y-%m-%d"),
            "time": "00:00",
            "description": "Ex-dividend date - ₹24 per share",
            "impact": "low",
            "status": "scheduled",
            "actual": None,
            "forecast": "₹24/share",
        },
        {
            "type": "dividend",
            "title": "HDFCBANK Dividend",
            "symbol": "HDFCBANK",
            "date": (base_date + timedelta(days=14)).strftime("%Y-%m-%d"),
            "time": "00:00",
            "description": "Ex-dividend date - ₹19.50 per share",
            "impact": "low",
            "status": "scheduled",
            "actual": None,
            "forecast": "₹19.50/share",
        },
        {
            "type": "dividend",
            "title": "ITC Dividend",
            "symbol": "ITC",
            "date": (base_date + timedelta(days=22)).strftime("%Y-%m-%d"),
            "time": "00:00",
            "description": "Ex-dividend date - ₹7.25 per share",
            "impact": "low",
            "status": "scheduled",
            "actual": None,
            "forecast": "₹7.25/share",
        },
    ]
    
    events.extend(dividend_events)
    
    # Corporate Actions
    corporate_actions = [
        {
            "type": "corporate_action",
            "title": "Reliance AGM",
            "symbol": "RELIANCE",
            "date": (base_date + timedelta(days=25)).strftime("%Y-%m-%d"),
            "time": "14:00",
            "description": "Annual General Meeting - Major announcements expected",
            "impact": "high",
            "status": "scheduled",
            "actual": None,
            "forecast": "Telecom 5G rollout update expected",
        },
        {
            "type": "corporate_action",
            "title": "HDFC Bank-HDFC Ltd Merger",
            "symbol": "HDFCBANK",
            "date": (base_date + timedelta(days=7)).strftime("%Y-%m-%d"),
            "time": "11:00",
            "description": "Post-merger integration update",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "Synergy benefits discussion",
        },
        {
            "type": "corporate_action",
            "title": "Adani Stock Split",
            "symbol": "ADANIPORTS",
            "date": (base_date + timedelta(days=16)).strftime("%Y-%m-%d"),
            "time": "00:00",
            "description": "Stock split 1:2 record date",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "Split ratio 1:2",
        },
    ]
    
    events.extend(corporate_actions)
    
    # Global Events affecting Indian markets
    global_events = [
        {
            "type": "global",
            "title": "US Fed Interest Rate Decision",
            "symbol": None,
            "date": (base_date + timedelta(days=19)).strftime("%Y-%m-%d"),
            "time": "00:30",
            "description": "FOMC meeting outcome - affects FII flows",
            "impact": "high",
            "status": "scheduled",
            "actual": None,
            "forecast": "5.25-5.50% (no change)",
        },
        {
            "type": "global",
            "title": "China GDP Data",
            "symbol": None,
            "date": (base_date + timedelta(days=11)).strftime("%Y-%m-%d"),
            "time": "07:00",
            "description": "Q4 2025 China GDP Growth",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "4.8% YoY",
        },
        {
            "type": "global",
            "title": "Crude Oil Inventory",
            "symbol": None,
            "date": (base_date + timedelta(days=9)).strftime("%Y-%m-%d"),
            "time": "20:00",
            "description": "US EIA Crude Oil Inventory Report",
            "impact": "medium",
            "status": "scheduled",
            "actual": None,
            "forecast": "-2.5M barrels",
        },
    ]
    
    events.extend(global_events)
    
    # Filter by event type if specified
    if event_type and event_type != "all":
        events = [e for e in events if e["type"] == event_type]
    
    # Sort by date
    events.sort(key=lambda x: x["date"])
    
    # Add countdown and days_until
    for event in events:
        event_datetime = datetime.strptime(event["date"], "%Y-%m-%d")
        days_until = (event_datetime.date() - base_date.date()).days
        event["days_until"] = days_until
        
        if days_until == 0:
            event["countdown"] = "Today"
        elif days_until == 1:
            event["countdown"] = "Tomorrow"
        elif days_until < 7:
            event["countdown"] = f"In {days_until} days"
        else:
            event["countdown"] = f"In {days_until // 7} week{'s' if days_until // 7 > 1 else ''}"
    
    return events


@router.get("/events")
async def get_calendar_events(
    days_ahead: int = 30,
    event_type: Optional[str] = None,
    impact: Optional[str] = None
):
    """
    Get upcoming economic calendar events
    
    Query params:
        days_ahead: Number of days to look ahead (default 30)
        event_type: Filter by type (earnings, rbi, economic, ipo, dividend, corporate_action, global, all)
        impact: Filter by impact level (high, medium, low)
    
    Returns:
        {
            "events": [...],
            "total_count": 45,
            "event_types": ["earnings", "rbi", ...],
            "upcoming_high_impact": 12
        }
    """
    try:
        events = generate_economic_calendar(days_ahead, event_type)
        
        # Filter by impact
        if impact and impact != "all":
            events = [e for e in events if e["impact"] == impact]
        
        # Get event type counts
        event_types = list(set(e["type"] for e in events))
        high_impact_count = len([e for e in events if e["impact"] == "high"])
        
        return {
            "events": events,
            "total_count": len(events),
            "event_types": sorted(event_types),
            "upcoming_high_impact": high_impact_count,
        }
    
    except Exception as e:
        logger.error(f"Calendar error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch calendar: {str(e)}")


@router.get("/today")
async def get_today_events():
    """Get today's events only"""
    try:
        all_events = generate_economic_calendar(days_ahead=1)
        today_events = [e for e in all_events if e["days_until"] == 0]
        
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "events": today_events,
            "count": len(today_events),
        }
    
    except Exception as e:
        logger.error(f"Today calendar error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch today's events: {str(e)}")


@router.get("/week")
async def get_week_events():
    """Get this week's events (next 7 days)"""
    try:
        all_events = generate_economic_calendar(days_ahead=7)
        week_events = [e for e in all_events if e["days_until"] <= 7]
        
        # Group by day
        events_by_day = {}
        for event in week_events:
            date = event["date"]
            if date not in events_by_day:
                events_by_day[date] = []
            events_by_day[date].append(event)
        
        return {
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "end_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "events_by_day": events_by_day,
            "total_count": len(week_events),
        }
    
    except Exception as e:
        logger.error(f"Week calendar error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch week events: {str(e)}")


@router.get("/earnings")
async def get_earnings_calendar(days_ahead: int = 30):
    """Get earnings announcements only"""
    try:
        events = generate_economic_calendar(days_ahead, event_type="earnings")
        
        return {
            "earnings": events,
            "count": len(events),
        }
    
    except Exception as e:
        logger.error(f"Earnings calendar error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch earnings: {str(e)}")


@router.get("/ipo")
async def get_ipo_calendar(days_ahead: int = 30):
    """Get IPO schedule only"""
    try:
        events = generate_economic_calendar(days_ahead, event_type="ipo")
        
        return {
            "ipos": events,
            "count": len(events),
        }
    
    except Exception as e:
        logger.error(f"IPO calendar error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch IPOs: {str(e)}")
