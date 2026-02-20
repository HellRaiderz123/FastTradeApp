#!/usr/bin/env python
"""Quick test of the news API"""
import requests

try:
    print("Testing /news/feed...")
    r = requests.get('http://localhost:8000/news/feed?limit=3', timeout=10)
    print(f"Status: {r.status_code}")
    
    data = r.json()
    print(f"Data source: {data.get('data_source')}")
    print(f"Total news: {len(data.get('news', []))}")
    
    if data.get('news'):
        news = data['news'][0]
        print(f"\nFirst news:")
        print(f"  Title: {news.get('title', 'N/A')[:70]}")
        print(f"  Category: {news.get('category', 'N/A')}")
        print(f"  Sentiment: {news.get('sentiment', 'N/A')}")
        print(f"  Source: {news.get('source', 'N/A')}")
    else:
        print("No news returned")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
