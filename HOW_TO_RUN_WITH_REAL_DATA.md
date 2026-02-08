# How to Run the TQQQ Backtest with REAL Data

Since I don't have network access to download real market data, I've created a Python script that YOU can run on your own computer with real QQQ and TQQQ historical prices from Yahoo Finance.

## Quick Start

### Step 1: Install Requirements
Open your terminal/command prompt and run:

```bash
pip install yfinance pandas numpy matplotlib
```

### Step 2: Download the Script
Save the file `tqqq_backtest_REAL_DATA.py` to your computer.

### Step 3: Run It
```bash
python tqqq_backtest_REAL_DATA.py
```

That's it! The script will:
1. Download all QQQ and TQQQ historical data from Yahoo Finance (Feb 2010 to today)
2. Run backtests with all 4 buffer configurations
3. Print detailed results to console
4. Generate a visualization: `tqqq_backtest_results_REAL_DATA.png`

## What You'll Get

### Console Output:
- Complete backtest results for each buffer configuration
- Detailed metrics (returns, CAGR, max drawdown, win rate, etc.)
- Trade-by-trade history for the winning strategy
- Comparison with TQQQ buy-and-hold

### Visualization File:
- Portfolio growth over time (log scale)
- QQQ price vs 200 SMA
- Total returns comparison
- CAGR comparison
- Drawdown analysis
- Win rate vs trade frequency

## Expected Results (based on synthetic data)

With REAL data, results may differ, but based on my synthetic backtest:

**Winner: 0% Buffer (No Buffer)**
- ~17,000% total return over 16 years
- ~38% CAGR
- ~65 trades
- ~20% win rate (but massive wins when right)

## Customization Options

You can modify the script to:

### Change Date Range:
```python
start_date = '2015-01-01'  # Start from 2015 instead
end_date = '2024-12-31'    # End at specific date
```

### Test Different Buffer Combinations:
```python
configs = [
    {'buy': 0.02, 'sell': 0.01, 'name': '2% Buy / 1% Sell'},
    {'buy': 0.04, 'sell': 0.04, 'name': '4% Symmetric'},
    # Add your own configurations
]
```

### Change SMA Period:
```python
result = backtest_qqq_tqqq_strategy(
    qqq_df, tqqq_df,
    buy_buffer_pct=0.01,
    sell_buffer_pct=0.01,
    sma_period=150  # Use 150-day SMA instead of 200
)
```

### Change Starting Capital:
Find this line in the script:
```python
initial_capital = 10000  # Change to whatever you want
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'yfinance'"
→ Run: `pip install yfinance`

### "Could not find a version that satisfies the requirement"
→ Try: `pip install --upgrade pip` then retry installation

### Data download fails
→ Check your internet connection
→ Yahoo Finance occasionally rate-limits; wait a few minutes and retry

### Different results than my synthetic backtest
→ This is EXPECTED! Real data will show different performance
→ The relative ranking of strategies should be similar
→ Actual returns/drawdowns will reflect real market conditions

## Understanding the Results

### If 0% buffer wins (like in my synthetic test):
- QQQ is smooth enough that buffers just delay entries/exits
- Trade immediately when QQQ crosses 200 SMA
- Many trades but small losses, big wins

### If 1-3% buffer wins:
- Real market has more noise than synthetic data
- Small buffers help avoid whipsaws
- Better balance of trade frequency vs signal quality

### If TQQQ Buy-and-Hold wins:
- It probably will for long bull markets
- BUT you'd have to endure 80%+ drawdowns
- Strategy provides risk management with lower but steadier returns

## What to Do After Running

1. **Compare all strategies** - which buffer fits your risk tolerance?

2. **Check the trades** - do the buy/sell signals make sense historically?

3. **Look at drawdowns** - which strategy has drawdowns you can stomach?

4. **Consider taxes** - more trades = more short-term capital gains

5. **Test different periods:**
   - Bull market only (2010-2021)
   - Including bear market (2022)
   - Recent years only (2020-2024)

6. **Paper trade** - track signals for a few months before using real money

## Important Notes

⚠️ **Past performance does not guarantee future results**

⚠️ **TQQQ is 3x leveraged - extremely risky**

⚠️ **This backtest doesn't include:**
- Transaction costs
- Slippage
- Tax implications
- Overnight gaps
- Trading halts
- Volatility decay in TQQQ

⚠️ **Always test with real data before trading real money**

⚠️ **Consider consulting a financial advisor**

## Advanced: Export Trade History

Add this to the script after backtesting:

```python
# Export all trades to CSV
import csv

for result in results:
    filename = f"trades_{result['name'].replace(' ', '_').replace('/', '-')}.csv"
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=result['trades'][0].keys())
        writer.writeheader()
        writer.writerows(result['trades'])
    print(f"Saved trades to: {filename}")
```

This creates a CSV file for each strategy with all buy/sell trades that you can analyze in Excel.

---

**Ready to see the real results? Run the script and let me know what you find!**
