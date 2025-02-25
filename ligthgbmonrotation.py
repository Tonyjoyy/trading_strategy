# -*- coding: utf-8 -*-
"""ligthgbmonrotation.ipynb
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
import yfinance as yf
import re
import matplotlib.pyplot as plt

def download_data(symbol, start_date, end_date):
    return yf.download(symbol, start=start_date, end=end_date)

def calculate_rsi(prices, window):
    delta = prices.diff(1)
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = -delta.clip(upper=0).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def sanitize_feature_names(df):
    df.columns = [re.sub(r'[^A-Za-z0-9_]+', '', str(col)) for col in df.columns]
    return df


def compute_features(data_etf, data_sp500):
    # Reset index to flatten the multi-index structure
    data_etf = data_etf.reset_index()
    data_sp500 = data_sp500.reset_index()

    # Use 'Close' instead of 'Adj Close' (check for column existence)
    if 'Close' not in data_etf.columns or 'Close' not in data_sp500.columns:
        raise KeyError("The 'Close' column is missing in the downloaded data.")

    # Extract relevant columns
    df = data_etf[['Close']].rename(columns={"Close": "Price"}).copy()
    df['sp500price'] = data_sp500['Close']

    # Compute simple return features
    for i in range(1, 6):
        df[f'Return_{i}'] = df['Price'].pct_change(i)

    # Compute RSI
    df['RSI_6'] = calculate_rsi(df['Price'], 6)
    df['RSI_12'] = calculate_rsi(df['Price'], 12)
    df['RSI_24'] = calculate_rsi(df['Price'], 24)

    # Compute moving averages
    for ma in [20, 50, 100, 200]:
        df[f'MA{ma}_Price'] = df['Price'].rolling(window=ma).mean() / df['Price']
        df[f'MA{ma}_Bigger'] = (df['Price'].rolling(window=ma).mean() - df['Price']) / df['Price']

    # Compute SP500 features
    sp500_returns = data_sp500['Close'].pct_change()
    df['SP500_20Day_Mean_Return'] = sp500_returns.rolling(window=20).mean()

    # Compute MACD
    ema_short = df['Price'].ewm(span=12, adjust=False).mean()
    ema_long = df['Price'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_short - ema_long
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']

    # Compute new factors: highest and lowest prices
    df['High20_to_Price'] = df['Price'].rolling(window=20).max() / df['Price']
    df['Low20_to_Price'] = df['Price'].rolling(window=20).min() / df['Price']
    df['High5_to_Price'] = df['Price'].rolling(window=5).max() / df['Price']
    df['Low5_to_Price'] = df['Price'].rolling(window=5).min() / df['Price']

    # Sanitize feature names
    df = sanitize_feature_names(df)
    return df.dropna()

start_date, end_date = "2017-01-01", "2025-01-01"
etf_symbol, sp500_symbol = "XLF", "^GSPC"
data_etf = download_data(etf_symbol, start_date, end_date)
data_sp500 = download_data(sp500_symbol, start_date, end_date)
data_etf = data_etf.reset_index()
data_sp500 = data_sp500.reset_index()

print(data_etf.head())

df_features = compute_features(data_etf, data_sp500)

# 添加 PriceXLF / PriceSP500 的比率列
df_features['PriceXLF_to_SP500'] = df_features['PriceXLF'] / df_features['sp500price']
df_features['20_to_50'] = df_features['MA20_Bigger'] / df_features['MA50_Bigger']
df_features['20_to_100'] = df_features['MA20_Bigger'] / df_features['MA100_Bigger']

print(df_features.head())

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, confusion_matrix, classification_report
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings("ignore")

# 计算目标列
future_return = data_etf['Close'].pct_change(5).shift(-5)
df_features['Target'] = (future_return > 0).astype(int)

# 删除无用特征，确保数据完整性
df_features = df_features.dropna()
X = df_features.drop(columns=['Target', 'PriceXLF', 'sp500price'])
y = df_features['Target']

# 划分训练集和测试集
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 训练 LightGBM 模型（限制 max_depth）
clf = lgb.LGBMClassifier(max_depth=6)  # 限制最大深度为 6
clf.fit(X_train, y_train)

# 模型评估函数
def evaluate_model(clf, X_test, y_test):
    y_pred = clf.predict(X_test)
    y_pred_proba = clf.predict_proba(X_test)[:, 1]

    # 计算评估指标
    accuracy = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_pred_proba)

    # 打印评估结果
    print(f"Accuracy: {accuracy:.4f}")
    print(f"AUC: {auc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # 绘制混淆矩阵
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(6, 4))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['Down', 'Up'], yticklabels=['Down', 'Up'])
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.title('Confusion Matrix')
    plt.show()

# 调用评估函数
evaluate_model(clf, X_test, y_test)

# 绘制特征重要性
def plot_feature_importance(clf, X):
    plt.figure(figsize=(10, 6))
    lgb.plot_importance(clf, max_num_features=10, importance_type='gain')
    plt.title("Feature Importance")
    plt.show()

# 调用特征重要性绘图函数
plot_feature_importance(clf, X)

