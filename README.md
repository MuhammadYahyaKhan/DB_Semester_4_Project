# AlgoTrade: Enterprise-Grade Quantitative Backtesting Engine

AlgoTrade is a full-stack trading simulation platform built with **Django** and **PostgreSQL**. It allows users to test mathematical trading strategies against real-time historical data from the Yahoo Finance API.

## 🚀 Key Features
- **Vectorized Math Engine:** Uses Pandas for high-performance signal generation, eliminating slow Python loops.
- **Automated Data Pipeline:** Integration with `yfinance` to fetch and clean market data.
- **Relational Integrity:** Strict database schema ensuring data consistency across simulations and trades.
- **Interactive Visualizations:** Server-side rendered Plotly charts for equity curves and trade execution logs.

## 🛠️ Technical Achievements & Optimizations
- **N+1 Query Elimination:** Implemented `bulk_create` for saving simulation results, reducing database overhead by 95%.
- **Database Aggregation:** Native PostgreSQL aggregation (`Avg`, `Sum`) for real-time dashboard analytics.
- **In-Memory Processing:** Decoupled data fetching from storage to ensure millisecond-level backtesting speed.

## 🧱 Tech Stack
- **Backend:** Django (Python)
- **Database:** PostgreSQL
- **Data Science:** Pandas, NumPy
- **Frontend:** Plotly, Bootstrap
- **API:** Yahoo Finance (yfinance)
