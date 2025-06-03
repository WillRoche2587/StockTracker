# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import yfinance as yf
import asyncio
from datetime import datetime, timedelta
import json
from typing import Dict, List

app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Type-annotated storage for recent searches
recent_searches: Dict[str, dict] = {}

def is_market_open() -> bool:
    """
    Check if the US stock market is currently open.
    
    Returns:
        bool: True if market is open, False otherwise
    """
    now = datetime.now()
    if now.weekday() >= 5:  # Weekend check
        return False
    
    et_hour = (now.hour - 4) % 24  # Convert to Eastern Time
    return 9.5 <= et_hour < 16  # Market hours: 9:30 AM - 4:00 PM ET

def calculate_timeframe_change(historical_prices: List[dict]) -> float:
    """
    Calculate percentage change based on historical data.
    
    Args:
        historical_prices (List[dict]): List of historical price data points
        
    Returns:
        float: Percentage change rounded to 2 decimal places
    """
    if not historical_prices or len(historical_prices) < 2:
        return 0.0
    
    start_price = historical_prices[0]["price"]
    end_price = historical_prices[-1]["price"]
    
    if start_price == 0:
        return 0.0
        
    return round(((end_price - start_price) / start_price) * 100, 2)

def get_historical_data(stock: yf.Ticker, timeframe: str) -> List[dict]:
    """
    Get historical stock data based on timeframe.
    
    Args:
        stock (yf.Ticker): Yahoo Finance Ticker object
        timeframe (str): Time period for historical data ("1D", "1W", "1M", "1Y")
        
    Returns:
        List[dict]: List of historical price data points
    """
    end_date = datetime.now()
    
    timeframe_settings = {
        "1D": (timedelta(days=1), "1m"),
        "1W": (timedelta(weeks=1), "15m"),
        "1M": (timedelta(days=30), "1h"),
        "1Y": (timedelta(days=365), "1d")
    }
    
    delta, interval = timeframe_settings.get(timeframe, timeframe_settings["1D"])
    start_date = end_date - delta
    
    # Adjust for market closed scenario in 1D view
    if timeframe == "1D" and not is_market_open():
        # If market is closed, get most recent trading day's data
        now = datetime.now()
        # If it's weekend or outside trading hours
        if now.weekday() >= 5:  # Weekend
            days_to_subtract = now.weekday() - 4  # Go back to Friday
            end_date = (now - timedelta(days=days_to_subtract)).replace(hour=16, minute=0, second=0)
            start_date = end_date - timedelta(days=1)
        else:  # Weekday but market closed
            if now.hour < 9 or (now.hour == 9 and now.minute < 30):
                # Before market opens, show previous day
                if now.weekday() == 0:  # Monday
                    start_date = (now - timedelta(days=3)).replace(hour=9, minute=30, second=0)  # Friday
                    end_date = (now - timedelta(days=3)).replace(hour=16, minute=0, second=0)
                else:
                    start_date = (now - timedelta(days=1)).replace(hour=9, minute=30, second=0)
                    end_date = (now - timedelta(days=1)).replace(hour=16, minute=0, second=0)
            else:  # After market closes
                start_date = now.replace(hour=9, minute=30, second=0)
                end_date = now.replace(hour=16, minute=0, second=0)
    
    hist_data = stock.history(start=start_date, end=end_date, interval=interval)
    
    return [
        {
            "timestamp": index.strftime("%Y-%m-%d %H:%M:%S"),
            "price": round(row["Close"], 2)
        }
        for index, row in hist_data.iterrows()
    ]

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the index.html file."""
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time stock data updates.
    
    Args:
        websocket (WebSocket): FastAPI WebSocket connection
    """
    await websocket.accept()
    
    try:
        while True:
            message = await websocket.receive_text()
            
            try:
                data = json.loads(message)
                ticker = data.get("symbol", "")
                timeframe = data.get("timeframe", "1D")
            except json.JSONDecodeError:
                ticker = message
                timeframe = "1D"
            
            stock = yf.Ticker(ticker)
            stock_info = stock.info
            historical_prices = get_historical_data(stock, timeframe)
            timeframe_change_percent = calculate_timeframe_change(historical_prices)
            current_price = stock_info.get("currentPrice", 0)

            # Update recent searches
            recent_searches[ticker] = {
                "symbol": ticker,
                "name": stock_info.get("shortName", "Unknown"),
                "price": current_price,
                "change": timeframe_change_percent
            }

            # Prepare response data
            response_data = {
                "symbol": stock_info.get("symbol", ticker),
                "price": current_price,
                "percentChange": timeframe_change_percent,
                "currency": stock_info.get("currency", "N/A"),
                "name": stock_info.get("shortName", "Unknown"),
                "sector": stock_info.get("sector", "N/A"),
                "industry": stock_info.get("industry", "N/A"),
                "country": stock_info.get("country", "N/A"),
                "historicalData": historical_prices,
                "marketOpen": is_market_open(),
                "recentSearches": list(recent_searches.values())[-7:],
                # Additional stock info
                "marketCap": stock_info.get("marketCap", "N/A"),
                "volume": stock_info.get("volume", "N/A"),
                "averageVolume": stock_info.get("averageVolume", "N/A"),
                "pe_ratio": stock_info.get("trailingPE", "N/A"),
                "eps": stock_info.get("trailingEps", "N/A"),
                "dividend_yield": stock_info.get("dividendYield", "N/A"),
                "beta": stock_info.get("beta", "N/A"),
                "fiftyTwoWeekHigh": stock_info.get("fiftyTwoWeekHigh", "N/A"),
                "fiftyTwoWeekLow": stock_info.get("fiftyTwoWeekLow", "N/A"),
                "previousClose": stock_info.get("previousClose", "N/A"),
                "open": stock_info.get("open", "N/A"),
                "dayHigh": stock_info.get("dayHigh", "N/A"),
                "dayLow": stock_info.get("dayLow", "N/A")
            }
            
            await websocket.send_json(response_data)
            await asyncio.sleep(2)  # Rate limiting
            
    except WebSocketDisconnect:
        print("Client disconnected")
