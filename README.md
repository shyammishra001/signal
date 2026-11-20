# 🚀 SHYAM AI — F&O EXPLOSION SCANNER V2.5

### Intelligent NSE F&O Market Scanner | Stock Analysis | Option Chain | Momentum Scoring

A professional, read-only NSE Futures & Options market analysis dashboard designed to identify potential intraday opportunities using market momentum, price action, volume, Open Interest and option-chain analytics.

**Version:** 2.5  
**Platform:** Python / Streamlit  
**Market:** NSE India  
**Mode:** Read-Only  
**Order Execution:** Not Supported

---

## 📌 PROJECT OVERVIEW

SHYAM AI F&O EXPLOSION SCANNER is designed to help traders analyze NSE F&O stocks and identify potential intraday trading opportunities.

The scanner combines market data, momentum analysis, stock ranking and option-chain information to assist users in making informed trading decisions.

The application is intended for educational and analytical purposes.

---

## ⭐ KEY FEATURES

### 1. NSE F&O Market Scanner
- NSE F&O stock universe.
- Top 10 Fastest Rising F&O Stocks.
- Top 10 Fastest Falling F&O Stocks.
- Live LTP and Day Change.
- 1-minute, 3-minute and 5-minute momentum tracking.
- Volume and momentum analysis.
- Automatic stock ranking.

### 2. Intelligent Adaptive Stock Selection
- Compare rising and falling stocks.
- Evaluate momentum strength.
- Analyze unusual daily price movements.
- Consider historical price behaviour.
- Identify potential reversal and continuation risks.
- Generate a final ranked stock selection.

### 3. Stock & Option Score Search
Search for any supported F&O stock and evaluate it against the configured scoring system.

- Stock score out of 100.
- Momentum score.
- Trend confirmation.
- Volume confirmation.
- Risk assessment.
- Option contract score, where supported.

### 4. Professional Option Chain
- CE (Call Options).
- PE (Put Options).
- Strike prices.
- Open Interest (OI).
- Change in OI.
- Trading volume.
- Implied Volatility (IV).
- Delta, Theta, Gamma and Vega.
- Bid and Ask prices.
- ATM strike identification.
- Put-Call Ratio (PCR).
- Option premium analysis.

### 5. Risk Management
- Entry analysis.
- Stop-loss assessment.
- Target assessment.
- Risk-to-reward evaluation.
- Option Theta Decay awareness.
- Premium and liquidity checks.

### 6. Cloud Access
Designed for access through a web browser on:
- Windows
- Ubuntu Linux
- Android
- iPhone
- Tablets
- Every Where

---

## 🛠️ TECHNOLOGY STACK

- Python 3
- Streamlit
- Pandas
- NumPy
- Requests
- NSE Market Data
- INDstocks API (where configured)

---

## ⚙️ LOCAL INSTALLATION

### Step 1: Clone Repository

```bash
git clone https://github.com/shyammishra001/signal.git
```

### Step 2: Enter Project Directory

```bash
cd signal
```

### Step 3: Create Virtual Environment

```bash
python3 -m venv .venv
```

### Step 4: Activate Environment

Ubuntu/Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

### Step 5: Install Requirements

```bash
pip install -r requirements.txt
```

### Step 6: Run Application

```bash
streamlit run app.py
```

Open:

http://localhost:8501

---

## ☁️ STREAMLIT CLOUD DEPLOYMENT

1. Open Streamlit Community Cloud.
2. Sign in using GitHub.
3. Select New App.
4. Select repository: `shyammishra001/signal`
5. Select branch: `main`.
6. Set Main File Path: `app.py`.
7. Configure API credentials through Streamlit Secrets, using the exact variable names required by the application.
8. Click Deploy.

The application will receive a public web address.

---

## 🔐 SECURITY & PRIVACY

Security is important.

- Never upload API tokens to GitHub.
- Never publish passwords or private credentials.
- Use Streamlit Secrets for API credentials.
- Do not commit `.env` or `secrets.toml`.
- Keep sensitive configuration private.
- Use read-only API permissions wherever available.

**Important:** This application is designed as a read-only analytical scanner. It does not place, modify or execute trading orders.

---

## 📊 SCORING SYSTEM

The scanner uses a configurable scoring framework with a maximum score of 100.

The score is intended to evaluate factors such as:

- Price Momentum
- Trend Strength
- Volume Activity
- Open Interest Behaviour
- Market Direction
- Option Liquidity
- Option Greeks
- Risk and Reward

A higher score indicates a stronger match with the configured analytical conditions. It does not represent a guaranteed probability of profit.

---

## ⚠️ IMPORTANT DISCLAIMER

This software is provided for educational, research and informational purposes only.

- No guaranteed profits.
- No guaranteed trading signals.
- Market data may be delayed or incomplete.
- API availability depends on the data provider.
- Options trading involves substantial financial risk.
- Option premiums are affected by Theta Decay, IV changes, liquidity and market volatility.
- Historical performance does not guarantee future results.

Users must independently verify all market information before making financial decisions.

The developer is not responsible for financial losses resulting from the use of this software.

---

## 👨‍💻 DEVELOPER

**Project:** SHYAM AI — F&O EXPLOSION SCANNER  
**Version:** V2.5  
**Developer:** Shyam Mishra  
**GitHub:** shyammishra001

---

### ⭐ PROJECT SUPPORT

If you find this project useful, consider starring the repository on GitHub.

**Built for smarter NSE market analysis.**

🚀 SHYAM AI — F&O EXPLOSION SCANNER V2.5
