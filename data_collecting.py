import yfinance as yf
import numpy as np
import pandas as pd
from scipy import stats
import pandas_ta as ta
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# 获取 S&P 500 股票列表
def get_sp500_companies():
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'constituents'})
        df = pd.read_html(str(table))[0]
        return df['Symbol'].tolist()
    except Exception as e:
        print(f"Error fetching S&P 500 companies: {e}")
        return []


# 收集单个股票的财务数据并返回字典
def collect_financial_data(ticker, option_expiry='2025-01-17'):
    try:
        # 获取股票数据
        stock = yf.Ticker(ticker)
        
        # 获取财务信息（PE Ratio, ROE, Beta, PB Ratio）
        info = stock.info
        pe_ratio = info.get('trailingPE', 'N/A')  # PE Ratio
        roe = info.get('returnOnEquity', 'N/A')   # Return on Equity
        beta_info = info.get('beta', 'N/A')       # Beta
        pb_ratio = info.get('priceToBook', 'N/A') # Price-to-Book Ratio (PB)

        # 获取历史市场数据（过去1个月的数据）
        hist = stock.history(period="1mo")
        
        # 检查数据是否为空
        if hist.empty:
            print(f"No historical data available for {ticker}")
            return None

        # 获取开盘价、收盘价、成交量
        open_price = hist['Open'].iloc[-1] if len(hist) > 0 else 'N/A'
        close_price = hist['Close'].iloc[-1] if len(hist) > 0 else 'N/A'
        volume = hist['Volume'].iloc[-1] if len(hist) > 0 else 'N/A'

        # 计算 RSI (14天) 使用 pandas_ta
        rsi = ta.rsi(hist['Close'], length=14)
        latest_rsi = rsi.iloc[-1] if len(rsi) > 0 else 'N/A'

        # 获取期权链数据
        option_chain = stock.option_chain(option_expiry)

        # 分别获取看涨期权和看跌期权的数据
        calls = option_chain.calls
        puts = option_chain.puts

        # 计算看涨期权和看跌期权的成交量总和
        call_volume = calls['volume'].sum() if len(calls) > 0 else 'N/A'
        put_volume = puts['volume'].sum() if len(puts) > 0 else 'N/A'

        # 计算 Put/Call Ratio
        put_call_ratio = put_volume / call_volume if call_volume != 0 else 'N/A'

        # 获取隐含波动率的均值 (看涨期权的隐含波动率)
        iv = calls['impliedVolatility'].mean() if len(calls) > 0 else 'N/A'

        # 获取标的股票和基准指数的历史数据（过去1年的数据）
        stock_data = stock.history(period="1y")
        
        # 检查是否有历史数据
        if stock_data.empty:
            print(f"No 1-year historical data available for {ticker}")
            return None
        
        # 下载基准指数（S&P 500）的数据
        benchmark_data = yf.download('^GSPC', start=stock_data.index.min(), end=stock_data.index.max())

        # 解决 tz-naive 和 tz-aware 问题
        stock_data.index = stock_data.index.tz_localize(None)
        benchmark_data.index = benchmark_data.index.tz_localize(None)

        # 计算每日回报率，使用 'Close' 替代 'Adj Close'
        if 'Close' in stock_data.columns and 'Close' in benchmark_data.columns:
            stock_data['Returns'] = stock_data['Close'].pct_change()
            benchmark_data['Returns'] = benchmark_data['Close'].pct_change()
        else:
            print(f"Missing 'Close' data for {ticker}")
            return None

        # 删除缺失值
        returns_data = pd.DataFrame({
            'Stock_Returns': stock_data['Returns'],
            'Benchmark_Returns': benchmark_data['Returns']
        }).dropna()

        # 使用线性回归计算 Alpha 和 Beta
        if not returns_data.empty:
            slope, intercept, _, _, _ = stats.linregress(returns_data['Benchmark_Returns'], returns_data['Stock_Returns'])
            alpha = intercept
            beta = slope
        else:
            alpha = 'N/A'
            beta = 'N/A'

        # 返回结果为字典
        return {
            'Ticker': ticker, 
            'PE Ratio': pe_ratio,
            'ROE': roe,
            'Beta (info)': beta_info,
            'PB Ratio': pb_ratio,
            'Open Price': open_price,
            'Close Price': close_price,
            'Volume': volume,
            'RSI': latest_rsi,
            'Put/Call Ratio': put_call_ratio,
            'Implied Volatility': iv,
            'Alpha': alpha,
            'Beta (regression)': beta
        }
    except Exception as e:
        print(f"Error collecting data for {ticker}: {e}")
        return None

# 收集所有 S&P 500 公司的财务数据并保存到 Excel 和 CSV 文件
def collect_sp500_financial_data():
    # 获取 S&P 500 公司列表
    sp500_companies = get_sp500_companies()
    
    # 初始化结果列表
    financial_data = []

    # 遍历所有公司并收集财务数据
    for ticker in sp500_companies:
        print(f"Collecting data for {ticker}...")
        data = collect_financial_data(ticker)
        time.sleep(1)  # Pause for 1 second between requests
        if data:
            financial_data.append(data)
    
    if financial_data:
        df = pd.DataFrame(financial_data)
        current_date = datetime.now().strftime("%Y-%m-%d")
        excel_output_file = f'sp500_financial_data_{current_date}.xlsx'
        csv_output_file = f'sp500_financial_data_{current_date}.csv'
        
        df.to_excel(excel_output_file, index=False)
        df.to_csv(csv_output_file, index=False)

        print(f"Financial data for S&P 500 companies has been saved to {excel_output_file} and {csv_output_file}")
    else:
        print("No financial data collected.")

# 调用函数
if __name__ == "__main__":
    collect_sp500_financial_data()