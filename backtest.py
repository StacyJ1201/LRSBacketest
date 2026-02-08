"""
TQQQ Strategy Backtest with REAL QQQ and TQQQ Data
Run this script on your local machine with internet access

Requirements:
pip install yfinance pandas numpy

This will download actual historical data and run the backtest properly.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

def calculate_sma(prices, period=200):
    """Calculate Simple Moving Average"""
    return prices.rolling(window=period).mean()

def download_data(ticker, start_date, end_date):
    """Download historical data from Yahoo Finance"""
    print(f"Downloading {ticker} data from {start_date} to {end_date}...")
    df = yf.download(ticker, start=start_date, end=end_date, progress=False)
    print(f"  → Downloaded {len(df)} days of data")
    return df[['Close']]

def backtest_qqq_tqqq_strategy(qqq_df, tqqq_df, buy_buffer_pct, sell_buffer_pct, sma_period=200):
    """
    Backtest the LRS strategy using QQQ signals to trade TQQQ
    
    Parameters:
    - qqq_df: DataFrame with QQQ 'Close' prices
    - tqqq_df: DataFrame with TQQQ 'Close' prices  
    - buy_buffer_pct: Percentage above QQQ SMA to trigger buy
    - sell_buffer_pct: Percentage below QQQ SMA to trigger sell
    - sma_period: Period for SMA calculation (default 200)
    """
    # Merge on dates
    df = pd.concat([qqq_df['Close'], tqqq_df['Close']], axis=1, keys=['QQQ', 'TQQQ'])
    
    # Drop any NaN values from mismatched dates
    df = df.dropna()
    
    # Calculate QQQ's 200 SMA and buffer levels
    df['QQQ_SMA'] = calculate_sma(df['QQQ'], sma_period)
    df['Buy_Level'] = df['QQQ_SMA'] * (1 + buy_buffer_pct)
    df['Sell_Level'] = df['QQQ_SMA'] * (1 - sell_buffer_pct)
    
    # Extract values as arrays for faster, cleaner access
    dates = df.index.values
    qqq_vals = df['QQQ'].values
    tqqq_vals = df['TQQQ'].values
    qqq_sma_vals = df['QQQ_SMA'].values
    buy_level_vals = df['Buy_Level'].values
    sell_level_vals = df['Sell_Level'].values
    
    # Initialize position tracking
    position = 0  # 0 = cash, 1 = invested in TQQQ
    trades = []
    entry_price = 0
    
    # Track portfolio value
    initial_capital = 10000
    cash = initial_capital
    shares = 0
    portfolio_values = []
    
    for i in range(len(dates)):
        if pd.isna(qqq_sma_vals[i]):
            portfolio_values.append(initial_capital)
            continue
            
        # Extract values as Python scalars to avoid numpy type issues
        current_qqq = qqq_vals[i].item()
        current_tqqq = tqqq_vals[i].item()
        current_date = dates[i]
        buy_level = buy_level_vals[i].item()
        sell_level = sell_level_vals[i].item()
        qqq_sma = qqq_sma_vals[i].item()
        
        # Buy signal: QQQ price crosses above QQQ buy_level → Buy TQQQ
        if position == 0 and current_qqq > buy_level:
            if cash > 0:
                shares = cash / current_tqqq  # Buy TQQQ shares
                entry_price = current_tqqq
                position = 1
                trades.append({
                    'Date': current_date,
                    'Type': 'BUY',
                    'QQQ_Price': current_qqq,
                    'QQQ_SMA': qqq_sma,
                    'Buy_Level': buy_level,
                    'TQQQ_Price': current_tqqq
                })
                cash = 0.0
        
        # Sell signal: QQQ price crosses below QQQ sell_level → Sell TQQQ
        elif position == 1 and current_qqq < sell_level:
            if shares > 0:
                cash = shares * current_tqqq  # Sell TQQQ shares
                pnl = ((current_tqqq - entry_price) / entry_price) * 100
                position = 0
                trades.append({
                    'Date': current_date,
                    'Type': 'SELL',
                    'QQQ_Price': current_qqq,
                    'QQQ_SMA': qqq_sma,
                    'Sell_Level': sell_level,
                    'TQQQ_Price': current_tqqq,
                    'PnL_pct': pnl
                })
                shares = 0.0
        
        # Calculate current portfolio value
        if position == 1:
            portfolio_value = shares * current_tqqq
        else:
            portfolio_value = cash
        
        portfolio_values.append(portfolio_value)
    
    # Final portfolio value
    if position == 1:
        final_value = shares * tqqq_vals[-1].item()
    else:
        final_value = cash
    
    # Calculate metrics
    total_return = ((final_value - initial_capital) / initial_capital) * 100
    
    # Calculate max drawdown
    portfolio_series = pd.Series(portfolio_values, index=dates)
    cummax = portfolio_series.cummax()
    drawdown = (portfolio_series - cummax) / cummax * 100
    max_drawdown = drawdown.min()
    
    # Calculate winning trades
    sell_trades = [t for t in trades if t['Type'] == 'SELL']
    if sell_trades:
        winning_trades = sum(1 for t in sell_trades if t.get('PnL_pct', 0) > 0)
        win_rate = (winning_trades / len(sell_trades)) * 100
        avg_win = float(np.mean([t['PnL_pct'] for t in sell_trades if t.get('PnL_pct', 0) > 0])) if winning_trades > 0 else 0.0
        avg_loss = float(np.mean([t['PnL_pct'] for t in sell_trades if t.get('PnL_pct', 0) < 0])) if (len(sell_trades) - winning_trades) > 0 else 0.0
    else:
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0
    
    # Calculate CAGR
    years = (pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days / 365.25
    cagr = (((final_value / initial_capital) ** (1 / years)) - 1) * 100 if years > 0 else 0.0
    
    return {
        'buy_buffer': buy_buffer_pct * 100,
        'sell_buffer': sell_buffer_pct * 100,
        'total_return': total_return,
        'cagr': cagr,
        'max_drawdown': max_drawdown,
        'num_trades': len(sell_trades),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'final_value': final_value,
        'trades': trades,
        'portfolio_values': portfolio_series,
        'years': years
    }

def main():
    print("=" * 80)
    print("TQQQ Strategy Backtest - Using REAL QQQ and TQQQ Data")
    print("=" * 80)
    print()
    
    # Set date range
    start_date = '2010-02-11'  # TQQQ inception
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Download real data
    print("Downloading historical data from Yahoo Finance...")
    qqq_df = download_data('QQQ', start_date, end_date)
    tqqq_df = download_data('TQQQ', start_date, end_date)
    print()
    
    # Show data info
    print(f"Backtest Period: {qqq_df.index[0].strftime('%Y-%m-%d')} to {qqq_df.index[-1].strftime('%Y-%m-%d')}")
    print(f"Total Trading Days: {len(qqq_df)}")
    print()
    print(f"QQQ Starting Price: ${qqq_df['Close'].iloc[0].item():.2f}")
    print(f"QQQ Ending Price: ${qqq_df['Close'].iloc[-1].item():.2f}")
    print(f"QQQ Buy & Hold Return: {((qqq_df['Close'].iloc[-1].item() / qqq_df['Close'].iloc[0].item()) - 1) * 100:.2f}%")
    print()
    print(f"TQQQ Starting Price: ${tqqq_df['Close'].iloc[0].item():.2f}")
    print(f"TQQQ Ending Price: ${tqqq_df['Close'].iloc[-1].item():.2f}")
    print(f"TQQQ Buy & Hold Return: {((tqqq_df['Close'].iloc[-1].item() / tqqq_df['Close'].iloc[0].item()) - 1) * 100:.2f}%")
    print()
    
    # Run backtests with different buffer configurations
    print("Running backtests...")
    print()
    
    configs = [
        {'buy': 0.05, 'sell': 0.03, 'name': '5% Buy / 3% Sell'},
        {'buy': 0.03, 'sell': 0.03, 'name': '3% Buy / 3% Sell'},
        {'buy': 0.02, 'sell': 0.02, 'name': '2% Buy / 2% Sell'},  # NEW
        {'buy': 0.01, 'sell': 0.01, 'name': '1% Buy / 1% Sell'},
        {'buy': 0.005, 'sell': 0.005, 'name': '0.5% Buy / 0.5% Sell'},  # NEW
        {'buy': 0.00, 'sell': 0.00, 'name': '0% Buy / 0% Sell (No Buffer)'},
        {'buy': 0.03, 'sell': 0.01, 'name': '3% Buy / 1% Sell'},  # NEW - asymmetric
    ]
    
    results = []
    for config in configs:
        result = backtest_qqq_tqqq_strategy(
            qqq_df, tqqq_df, 
            buy_buffer_pct=config['buy'],
            sell_buffer_pct=config['sell']
        )
        result['name'] = config['name']
        results.append(result)
    
    # Calculate TQQQ buy and hold
    # Start after 200 days to align with strategy
    tqqq_bh_start_idx = 200
    tqqq_buy_hold_return = ((tqqq_df['Close'].iloc[-1].item() - tqqq_df['Close'].iloc[tqqq_bh_start_idx].item()) / 
                            tqqq_df['Close'].iloc[tqqq_bh_start_idx].item()) * 100
    years_bh = (tqqq_df.index[-1] - tqqq_df.index[tqqq_bh_start_idx]).days / 365.25
    tqqq_buy_hold_cagr = (((tqqq_df['Close'].iloc[-1].item() / tqqq_df['Close'].iloc[tqqq_bh_start_idx].item()) ** (1 / years_bh)) - 1) * 100
    
    # Display results
    print("=" * 80)
    print("BACKTEST RESULTS SUMMARY")
    print("=" * 80)
    print()
    print(f"{'Strategy':<30} {'Total Return':<15} {'CAGR':<12} {'Max DD':<12} {'Trades':<10} {'Win Rate':<12}")
    print("-" * 80)
    
    for result in results:
        print(f"{result['name']:<30} {result['total_return']:>12.2f}%  {result['cagr']:>10.2f}%  "
              f"{result['max_drawdown']:>10.2f}%  {result['num_trades']:>8}  {result['win_rate']:>10.2f}%")
    
    print(f"{'TQQQ Buy and Hold':<30} {tqqq_buy_hold_return:>12.2f}%  {tqqq_buy_hold_cagr:>10.2f}%  "
          f"{'N/A':<12} {'N/A':<10} {'N/A':<12}")
    print()
    
    # Detailed results
    print("=" * 80)
    print("DETAILED PERFORMANCE METRICS")
    print("=" * 80)
    print()
    
    for result in results:
        print(f"Strategy: {result['name']}")
        print("-" * 80)
        print(f"Total Return:        {result['total_return']:>10.2f}%")
        print(f"CAGR:                {result['cagr']:>10.2f}%")
        print(f"Maximum Drawdown:    {result['max_drawdown']:>10.2f}%")
        print(f"Number of Trades:    {result['num_trades']:>10}")
        print(f"Win Rate:            {result['win_rate']:>10.2f}%")
        print(f"Average Win:         {result['avg_win']:>10.2f}%")
        print(f"Average Loss:        {result['avg_loss']:>10.2f}%")
        print(f"Final Portfolio:     ${result['final_value']:>10,.2f}")
        print(f"Years Tested:        {result['years']:>10.1f}")
        print()
    
    # Find winner
    best_result = max(results, key=lambda x: x['total_return'])
    
    print("=" * 80)
    print("WINNER")
    print("=" * 80)
    print()
    print(f"The {best_result['name']} strategy")
    print(f"achieved the highest total return of {best_result['total_return']:.2f}%")
    print(f"with a CAGR of {best_result['cagr']:.2f}% and {best_result['num_trades']} trades.")
    print()
    
    # Show recent trades for winner
    print("=" * 80)
    print(f"LAST 10 TRADES - {best_result['name']}")
    print("=" * 80)
    print()
    
    recent_trades = best_result['trades'][-20:]  # Last 20 events (10 pairs)
    for trade in recent_trades:
        date_str = pd.Timestamp(trade['Date']).strftime('%Y-%m-%d')
        if trade['Type'] == 'BUY':
            print(f"{date_str}: BUY  TQQQ @ ${trade['TQQQ_Price']:.2f}")
            print(f"           (QQQ ${trade['QQQ_Price']:.2f} > Buy Level ${trade['Buy_Level']:.2f})")
        else:
            print(f"{date_str}: SELL TQQQ @ ${trade['TQQQ_Price']:.2f} "
                  f"(P/L: {trade['PnL_pct']:+.2f}%)")
            print(f"           (QQQ ${trade['QQQ_Price']:.2f} < Sell Level ${trade['Sell_Level']:.2f})")
        print()
    
    print("=" * 80)
    print("Analysis complete.")
    print("=" * 80)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()