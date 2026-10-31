#!/usr/bin/env python3
import csv
from pathlib import Path
base=Path(__file__).resolve().parents[1]/'data'
expected={
'nifty50_daily_prices.csv':['date','symbol','open','high','low','close','adjusted_close','volume'],
'nifty50_annual_performance.csv':['year','symbol','company_name','sector','annual_return_pct','annualized_volatility_pct','max_drawdown_pct'],
'nifty50_final_annual_performance.csv':['year','symbol','company_name','sector','annual_return_pct','annualized_volatility_pct','max_drawdown_pct'],
'nifty50_5year_performance.csv':['symbol','company_name','sector','total_return_pct','cagr_pct','annualized_volatility_pct','max_drawdown_pct'],
'nifty50_corporate_actions.csv':['symbol','event_date','event_type','description','price_data_status'],
'nifty50_yearly_constituents.csv':['year','symbol','company_name','sector','valid_from','valid_to'],
'nifty50_training.csv':['instruction','context','response','category','source']}
for name,cols in expected.items():
 p=base/name
 with p.open(encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f); actual=r.fieldnames or []; rows=sum(1 for _ in r)
 missing=[c for c in cols if c not in actual]
 if missing: raise SystemExit(f'{name}: missing columns {missing}')
 print(f'{name}: {rows:,} rows; columns OK')
print('Dataset verification passed.')
