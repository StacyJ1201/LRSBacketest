"""
TQQQ Strategy Backtest with Simulated + Real TQQQ Data (1999-2026)
Run this script on your local machine with internet access

Requirements:
pip install yfinance pandas numpy

Synthetic TQQQ is built from QQQ daily returns * 3x minus daily drag
(expense ratio + leveraged borrowing costs). The drag is calibrated against
real TQQQ in the 2010-2026 overlap period so the simulation matches reality.
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
    # Flatten MultiIndex columns if present (newer yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[['Close']].copy()
    df['Close'] = df['Close'].astype(float)
    print(f"  -> Downloaded {len(df)} days of data")
    return df

def build_synthetic_tqqq(qqq_df, real_tqqq_df, irx_df):
    """
    Build a full TQQQ price series from 1999-2026.
    Pre-2010: synthetic from QQQ * 3x daily leverage minus calibrated drag.
    Post-2010: real TQQQ data.

    Drag is calibrated by matching synthetic to real TQQQ in the overlap period.
    """
    splice_date = '2010-02-11'

    # Reindex IRX to match QQQ trading days (forward-fill gaps like holidays)
    irx_aligned = irx_df.reindex(qqq_df.index).ffill().bfill()

    # --- PHASE 1: Calibrate drag against real TQQQ ---
    print("\n" + "-" * 60)
    print("PHASE 1: Calibrating synthetic model against real TQQQ")
    print("-" * 60)

    overlap_dates = qqq_df.loc[splice_date:].index.intersection(real_tqqq_df.index)
    qqq_overlap = qqq_df.loc[overlap_dates, 'Close']
    tqqq_overlap = real_tqqq_df.loc[overlap_dates, 'Close']
    irx_overlap = irx_aligned.loc[overlap_dates, 'Close']

    qqq_daily_ret = qqq_overlap.pct_change().fillna(0).values
    tqqq_daily_ret = tqqq_overlap.pct_change().fillna(0).values
    irx_vals = irx_overlap.values

    best_spread = 0.0
    lowest_error = float('inf')

    cum_real_final = np.prod(1 + tqqq_daily_ret)

    for spread in np.linspace(0.0, 0.05, 501):
        daily_borrow = (irx_vals / 100 + spread) * 2 / 252
        daily_expense = 0.0095 / 252
        daily_drag = daily_borrow + daily_expense
        synth_ret = qqq_daily_ret * 3 - daily_drag

        cum_synth_final = np.prod(1 + synth_ret)

        error = abs(cum_synth_final - cum_real_final)
        if error < lowest_error:
            lowest_error = error
            best_spread = spread

    print(f"  Best spread: {best_spread*100:.2f}%")
    print(f"  Calibration error: {lowest_error*100:.2f}% (cumulative)")

    # --- PHASE 2: Generate full synthetic series from 1999 ---
    print("\n" + "-" * 60)
    print("PHASE 2: Generating synthetic TQQQ from 1999")
    print("-" * 60)

    qqq_ret = qqq_df['Close'].pct_change().fillna(0)
    daily_borrow = (irx_aligned['Close'] / 100 + best_spread) * 2 / 252
    daily_expense = 0.0095 / 252
    daily_drag = daily_borrow + daily_expense
    synth_ret = qqq_ret * 3 - daily_drag

    # Forward-build synthetic prices from an arbitrary start, then rescale
    synth_cumulative = (1 + synth_ret).cumprod()

    # Scale so that on splice_date the synthetic matches real TQQQ's first price
    real_start_price = real_tqqq_df['Close'].iloc[0]
    synth_at_splice = synth_cumulative.loc[splice_date]
    scale = real_start_price / synth_at_splice
    synth_prices = synth_cumulative * scale

    # Stitch: use synthetic pre-2010, real post-2010
    pre_splice = synth_prices[synth_prices.index < splice_date]
    post_splice = real_tqqq_df['Close']
    full_tqqq = pd.concat([pre_splice, post_splice])
    full_tqqq.name = 'Close'

    print(f"  Synthetic period: {pre_splice.index[0].strftime('%Y-%m-%d')} to {pre_splice.index[-1].strftime('%Y-%m-%d')} ({len(pre_splice)} days)")
    print(f"  Real period:      {post_splice.index[0].strftime('%Y-%m-%d')} to {post_splice.index[-1].strftime('%Y-%m-%d')} ({len(post_splice)} days)")
    print(f"  Total:            {len(full_tqqq)} days")
    print(f"  Simulated TQQQ start price (1999): ${pre_splice.iloc[0]:.4f}")
    print(f"  Splice price (2010-02-11):          ${real_start_price:.4f}")
    print(f"  Current price:                      ${post_splice.iloc[-1]:.2f}")

    # Also return the pure synthetic series for validation
    synth_only_df = pd.DataFrame({'Close': synth_prices})

    return pd.DataFrame({'Close': full_tqqq}), synth_only_df

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
    print("TQQQ Strategy Backtest - Simulated (1999) + Real (2010) Data")
    print("=" * 80)
    print()

    end_date = datetime.now().strftime('%Y-%m-%d')
    qqq_start = '1999-03-10'  # QQQ inception

    # Download data
    print("Downloading historical data from Yahoo Finance...")
    qqq_df = download_data('QQQ', qqq_start, end_date)
    real_tqqq_df = download_data('TQQQ', '2010-02-11', end_date)
    irx_df = download_data('^IRX', qqq_start, end_date)  # 13-week T-bill for borrow cost
    print()

    # Build full synthetic+real TQQQ series (also get pure synthetic for validation)
    tqqq_df, synth_only_df = build_synthetic_tqqq(qqq_df, real_tqqq_df, irx_df)

    # Show data info
    print()
    print(f"Backtest Period: {qqq_df.index[0].strftime('%Y-%m-%d')} to {qqq_df.index[-1].strftime('%Y-%m-%d')}")
    print(f"Total Trading Days: {len(qqq_df)}")
    print()
    print(f"QQQ Starting Price:  ${qqq_df['Close'].iloc[0].item():.2f}")
    print(f"QQQ Ending Price:    ${qqq_df['Close'].iloc[-1].item():.2f}")
    print(f"QQQ Buy & Hold Return: {((qqq_df['Close'].iloc[-1].item() / qqq_df['Close'].iloc[0].item()) - 1) * 100:.2f}%")
    print()
    print(f"TQQQ Sim Start Price (1999): ${tqqq_df['Close'].iloc[0]:.4f}")
    print(f"TQQQ Ending Price:           ${tqqq_df['Close'].iloc[-1]:.2f}")
    tqqq_bh_return = ((tqqq_df['Close'].iloc[-1] / tqqq_df['Close'].iloc[0]) - 1) * 100
    print(f"TQQQ Buy & Hold Return:      {tqqq_bh_return:.2f}%")
    print()

    # =========================================================================
    # VALIDATION: Compare Real TQQQ vs Synthetic TQQQ (2010-2026 only)
    # =========================================================================
    print("=" * 90)
    print("VALIDATION: Real TQQQ vs Synthetic TQQQ (2010-2026)")
    print("=" * 90)
    print()

    # QQQ from 2010 onward (need pre-2010 for SMA warmup, so use full QQQ)
    qqq_2010 = download_data('QQQ', '2010-02-11', end_date)

    # Synthetic-only TQQQ for the 2010+ period
    synth_2010 = synth_only_df.loc['2010-02-11':]

    validation_configs = [
        {'buy': 0.05, 'sell': 0.03, 'name': '5% Buy / 3% Sell'},
        {'buy': 0.03, 'sell': 0.03, 'name': '3% Buy / 3% Sell'},
        {'buy': 0.01, 'sell': 0.01, 'name': '1% Buy / 1% Sell'},
        {'buy': 0.005, 'sell': 0.005, 'name': '0.5% Buy / 0.5% Sell'},
        {'buy': 0.00, 'sell': 0.00, 'name': '0% (No Buffer)'},
    ]

    real_results = []
    synth_results = []
    for vc in validation_configs:
        r_real = backtest_qqq_tqqq_strategy(
            qqq_2010, real_tqqq_df,
            buy_buffer_pct=vc['buy'], sell_buffer_pct=vc['sell']
        )
        r_synth = backtest_qqq_tqqq_strategy(
            qqq_2010, synth_2010,
            buy_buffer_pct=vc['buy'], sell_buffer_pct=vc['sell']
        )
        r_real['name'] = vc['name']
        r_synth['name'] = vc['name']
        real_results.append(r_real)
        synth_results.append(r_synth)

    print(f"{'Strategy':<22} | {'--- Real TQQQ ---':^30} | {'--- Synthetic TQQQ ---':^30} | {'Return Diff':>12}")
    print(f"{'':22} | {'Return':>12} {'CAGR':>8} {'Max DD':>8} | {'Return':>12} {'CAGR':>8} {'Max DD':>8} |")
    print("-" * 105)

    for rr, rs in zip(real_results, synth_results):
        diff = rs['total_return'] - rr['total_return']
        print(f"{rr['name']:<22} | {rr['total_return']:>11.2f}% {rr['cagr']:>7.2f}% {rr['max_drawdown']:>7.2f}% "
              f"| {rs['total_return']:>11.2f}% {rs['cagr']:>7.2f}% {rs['max_drawdown']:>7.2f}% "
              f"| {diff:>+11.2f}%")

    print()
    print("(Smaller differences = more accurate synthetic model)")
    print()

    # =========================================================================
    # FULL 1999-2026 BACKTEST
    # =========================================================================

    # Run backtests
    print("Running full 1999-2026 backtests...")
    print()

    configs = [
        {'buy': 0.05, 'sell': 0.03, 'name': '5% Buy / 3% Sell'},
        {'buy': 0.05, 'sell': 0.05, 'name': '5% Buy / 5% Sell'},
        {'buy': 0.03, 'sell': 0.03, 'name': '3% Buy / 3% Sell'},
        {'buy': 0.03, 'sell': 0.01, 'name': '3% Buy / 1% Sell'},
        {'buy': 0.02, 'sell': 0.02, 'name': '2% Buy / 2% Sell'},
        {'buy': 0.01, 'sell': 0.01, 'name': '1% Buy / 1% Sell'},
        {'buy': 0.005, 'sell': 0.005, 'name': '0.5% Buy / 0.5% Sell'},
        {'buy': 0.00, 'sell': 0.00, 'name': '0% Buy / 0% Sell (No Buffer)'},
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

    # Buy & Hold benchmarks (invest $10k on day 1, hold to end)
    initial_capital = 10000
    tqqq_start_px = tqqq_df['Close'].iloc[0]
    tqqq_end_px = tqqq_df['Close'].iloc[-1]
    tqqq_bh_final = initial_capital * (tqqq_end_px / tqqq_start_px)
    tqqq_bh_return = ((tqqq_end_px / tqqq_start_px) - 1) * 100
    years_total = (tqqq_df.index[-1] - tqqq_df.index[0]).days / 365.25
    tqqq_bh_cagr = (((tqqq_end_px / tqqq_start_px) ** (1 / years_total)) - 1) * 100

    qqq_start_px = qqq_df['Close'].iloc[0].item()
    qqq_end_px = qqq_df['Close'].iloc[-1].item()
    qqq_bh_final = initial_capital * (qqq_end_px / qqq_start_px)
    qqq_bh_return = ((qqq_end_px / qqq_start_px) - 1) * 100
    qqq_bh_cagr = (((qqq_end_px / qqq_start_px) ** (1 / years_total)) - 1) * 100

    # Sort results by total return descending
    results.sort(key=lambda x: x['total_return'], reverse=True)

    # Display results
    print("=" * 95)
    print("BACKTEST RESULTS SUMMARY (1999-2026, sorted by return)")
    print("=" * 95)
    print()
    print(f"{'#':<4} {'Strategy':<30} {'$10k Becomes':<14} {'Return':<12} {'CAGR':<10} {'Max DD':<10} {'Trades':<8} {'Win%':<8}")
    print("-" * 95)

    for i, result in enumerate(results, 1):
        print(f"{i:<4} {result['name']:<30} ${result['final_value']:>11,.0f} {result['total_return']:>10.2f}%  {result['cagr']:>8.2f}%  "
              f"{result['max_drawdown']:>8.2f}%  {result['num_trades']:>6}  {result['win_rate']:>6.1f}%")

    print("-" * 95)
    print(f"{'':4} {'TQQQ Buy & Hold':<30} ${tqqq_bh_final:>11,.0f} {tqqq_bh_return:>10.2f}%  {tqqq_bh_cagr:>8.2f}%  "
          f"{'':>8}   {'':>6}  {'':>6}")
    print(f"{'':4} {'QQQ Buy & Hold':<30} ${qqq_bh_final:>11,.0f} {qqq_bh_return:>10.2f}%  {qqq_bh_cagr:>8.2f}%  "
          f"{'':>8}   {'':>6}  {'':>6}")
    print()

    # Detailed results
    print("=" * 80)
    print("DETAILED PERFORMANCE METRICS")
    print("=" * 80)
    print()

    for result in results:
        print(f"Strategy: {result['name']}")
        print("-" * 60)
        print(f"  Total Return:      {result['total_return']:>12.2f}%")
        print(f"  CAGR:              {result['cagr']:>12.2f}%")
        print(f"  Max Drawdown:      {result['max_drawdown']:>12.2f}%")
        print(f"  Trades:            {result['num_trades']:>12}")
        print(f"  Win Rate:          {result['win_rate']:>12.2f}%")
        print(f"  Avg Win:           {result['avg_win']:>12.2f}%")
        print(f"  Avg Loss:          {result['avg_loss']:>12.2f}%")
        print(f"  Final Portfolio:   ${result['final_value']:>12,.2f}")
        print(f"  Years Tested:      {result['years']:>12.1f}")
        print()

    # Winner
    best = results[0]  # already sorted
    print("=" * 80)
    print("WINNER")
    print("=" * 80)
    print()
    print(f"  {best['name']}")
    print(f"  Total Return: {best['total_return']:.2f}% | CAGR: {best['cagr']:.2f}%")
    print(f"  Max Drawdown: {best['max_drawdown']:.2f}% | Trades: {best['num_trades']}")
    print(f"  Final Portfolio: ${best['final_value']:,.2f} (from $10,000)")
    print()

    # Show last 10 trades for winner
    print("=" * 80)
    print(f"LAST 10 TRADES - {best['name']}")
    print("=" * 80)
    print()

    recent_trades = best['trades'][-20:]
    for trade in recent_trades:
        date_str = pd.Timestamp(trade['Date']).strftime('%Y-%m-%d')
        if trade['Type'] == 'BUY':
            print(f"  {date_str}: BUY  TQQQ @ ${trade['TQQQ_Price']:.2f}")
            print(f"             (QQQ ${trade['QQQ_Price']:.2f} > Buy Level ${trade['Buy_Level']:.2f})")
        else:
            print(f"  {date_str}: SELL TQQQ @ ${trade['TQQQ_Price']:.2f} (P/L: {trade['PnL_pct']:+.2f}%)")
            print(f"             (QQQ ${trade['QQQ_Price']:.2f} < Sell Level ${trade['Sell_Level']:.2f})")
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