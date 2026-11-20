SHYAM AI — F&O EXPLOSION SCANNER V2.5 CLEAN PROFESSIONAL UI
================================================

इस build में किए गए सुधार:
1. NSE cash ticker matching में F&O master का SYMBOL_NAME canonical base ticker प्राथमिकता से लिया जाता है; UNDERLYING_SCRIP_NAME को full company name मानकर ticker की तरह उपयोग नहीं किया जाता।
2. Rising और Falling lists अलग-अलग दिशा के आधार पर rank होती हैं। Momentum Score bounded components पर आधारित है; यह win probability नहीं है।
3. Flat 1m/3m movement पर SIDEWAYS / NO FRESH MOMENTUM दिखेगा, ताकि पुराना/स्थिर quote झूठा directional burst न दिखाए।
4. Option Chain expiry lookup: official INDstocks Expiries API, फिर official OPTSTK contract-search fallback, फिर F&O master के SYMBOL_NAME से fallback।
5. Option Chain केवल OPTSTK eligible NSE underlyings दिखाएगी। Underlying ID cash/equity master से लिया जाता है, F&O contract ID से नहीं।
6. Professional CE/Strike/PE table: केवल ITM Calls green और ITM Puts red; OTM cells dark रहते हैं; ATM strike पर पीली divider line; OI/volume/IV/Greeks, bid-ask spread %, lot size और ATM theta per lot/day।
7. Token clear button: token हटाने पर cached scanner/chain state clear होकर clean lock screen दिखेगी।
11. Option chain में CE/PE bid-ask spread %, master से lot size और ATM theta per lot/day जहाँ lot data उपलब्ध है।
13. Main dashboard में API token डालने के बाद sidebar स्वतः छिपता है; “API Settings दिखाएँ” से sidebar फिर खोल सकते हैं।
14. NSE Futures OI Intelligence: nearest available FUTSTK contracts पर NFO_ quote codes से OI scan; Long Buildup, Short Buildup, Short Covering और Long Unwinding अलग-अलग Top 10। यदि API OI fields नहीं लौटाता तो स्पष्ट warning आएगी, fake/estimated OI नहीं दिखेगा।

WINDOWS 11 LOCAL RUN
1. ZIP को नए folder में Extract करें.
2. RUN_WINDOWS.bat पर double-click करें.
3. Sidebar में INDstocks access token डालें; token भरने के बाद dashboard full-width हो जाएगा। Settings बदलने के लिए “API Settings दिखाएँ” चालू करें।
4. Scanner auto-refresh या Scan Now से quotes लें.
5. Option Chain में underlying और expiry चुनकर Fetch Option Chain दबाएँ.

अगर Windows Smart App Control / Python package DLL block करे:
CMD में project folder खोलकर:
   py -m venv .venv
   .venv\\Scripts\\activate
   py -m pip install -r requirements.txt
   py -m streamlit run app.py

OPTION / RISK की सीमाएँ
- यह build historical backtest या Time-Machine replay नहीं देता।
- Option shortlist एक live-data आधारित screening है; यह guaranteed buy signal नहीं है। ₹10,000 में एक lot का premium ₹9,000 से अधिक नहीं रखा जाता, ताकि charges/spread के लिए buffer रहे।
- Lot size या liquidity verify न हो तो contract recommend नहीं होगा। Theta, IV, bid-ask spread, slippage, charges और expiry risk बने रहते हैं।

SECURITY
- API token को screenshot, chat, source code या public GitHub में न डालें।
- Public cloud deployment से पहले APP_PASSWORD और secret storage configure करें।
- यह app read-only है; कोई order place नहीं करता।


V2.4 में अतिरिक्त सुधार (19-Nov-2026)
-----------------------------------
1. Rising/Falling bug: 1m/3m momentum flat होने पर पुराना code पूरे stock को SIDEWAYS कर देता था और Day % direction भी मिट जाती थी। अब flat intraday snapshot, Day % direction को overwrite नहीं करता।
2. Refresh safety: नया API snapshot खाली/flat/failed हो तो पिछली valid Top 10 list मिटेगी नहीं; dashboard स्पष्ट status बताएगा कि last valid snapshot दिख रहा है।
3. Quote parsing: LTP, day change, previous close के documented fields और fallback aliases parse होते हैं; day % API field न दे तो day_change / prev_close से calculate होता है। LTP न होने वाली rows usable quote count में नहीं जुड़तीं।
4. Top tables compact किए गए हैं ताकि Stock नाम पहली column में साफ दिखे; Rising और Falling दोनों साथ में दिखते हैं।
5. Option Chain selector अब सिर्फ F&O master के OPTSTK matching column पर निर्भर नहीं है। पूरे matched NSE F&O stock universe से stock चुना जा सकता है। चुने हुए stock का cash SECURITY_ID साफ दिखेगा।
6. Expiry lookup पहले official INDstocks Expiries API, फिर official OPTSTK contract search और अंत में F&O master fallback से होगा। Fetch से पहले selected stock + expiry के OPTSTK contracts verify होंगे।
7. Option Chain load होने पर selected stock, expiry, cash SECURITY_ID, matched OPTSTK contracts और returned strikes की संख्या दिखेगी। Failure पर exact API response/error दिखेगा; गलत stock/expiry chain silently display नहीं होगी।
8. Option-chain renderer में missing/non-dictionary CE/PE legs और ATM spot unavailable cases के लिए guards जोड़े गए।

जाँच सीमा:
- Python compile/syntax check और local ranking logic test पास हुए।
- INDstocks live API token इस build/test environment में उपलब्ध नहीं था; इसलिए आपके account पर live OPTSTK availability, expiry और chain response का दावा नहीं किया जा रहा। इसे आपके PC पर token से verify करना होगा।


V2.5 CLEAN UI सुधार (19-Nov-2026)
--------------------------------
1. Matched F&O stock table अब clean view है: Stock, LTP, Day %, Direction (🟢 UP / 🔻 DOWN / ⚪ FLAT), Volume और उपलब्ध price/momentum fields। SECURITY_ID और SCRIP_CODE स्क्रीन टेबल से हटाए गए हैं; API के लिए अंदर सुरक्षित रहते हैं।
2. Full NSE F&O Universe का raw technical dump मुख्य स्क्रीन से हटाकर compact table में बदला गया है। Technical diagnostics अलग collapsed section में हैं।
3. Option Chain default view में केवल CE OI, OI Change, Volume, LTP, बीच में Strike, और PE LTP, Volume, OI Change, OI दिखेंगे।
4. IV, Delta, Theta, Vega, Gamma, Lot Size, Bid/Ask और Spread optional Advanced Option Greeks section में हैं। ATM Theta/lot/day भी Advanced section में रखा गया है।
5. Option Chain heading/caption में Cash SECURITY_ID और internal contract identifiers नहीं दिखेंगे। Selected Stock, Expiry और OPTSTK contract count उपयोगकर्ता को दिखेंगे।
6. ITM-only colour logic और ATM yellow divider बरकरार है; OTM cells dark रहते हैं।
7. API connection, quote collection और option-chain source बरकरार हैं। इस build में backtest/time-machine module हटाया गया है और Intelligent Adaptive Pick जोड़ा गया है।

V2.5 Validation
- Python syntax compile check पास।
- Live INDstocks API / broker account पर runtime validation अभी उपयोगकर्ता के PC पर करना होगा।

UBUNTU / LINUX RUN
------------------
इस ZIP में Ubuntu के लिए RUN_UBUNTU.sh और README_UBUNTU_HINDI.txt भी हैं।
1. ZIP Extract करें और project folder में Terminal खोलें।
2. जरूरत हो तो: sudo apt update && sudo apt install -y python3 python3-venv python3-pip
3. चलाएँ: chmod +x RUN_UBUNTU.sh && ./RUN_UBUNTU.sh
4. Browser में http://127.0.0.1:8501 खोलें।
5. रोकने के लिए Terminal में Ctrl+C दबाएँ।
विस्तृत निर्देश और troubleshooting के लिए README_UBUNTU_HINDI.txt देखें।

V2.5 INTELLIGENT PICK UPDATE
---------------------------
1. Rising और Falling दोनों Top 10 tables बने रहते हैं। प्रत्येक तरफ से एक leader compare होता है और एक ही overall candidate दिखता है।
2. Adaptive score में उपलब्ध 1m/3m momentum alignment और Futures OI setup शामिल हैं। Confirmation अधूरी हो तो WAIT / NO TRADE दिखेगा।
3. Option Chain default selected stock को Intelligent Pick से लेती है। ₹10,000 budget में verified lot size, premium, liquidity, bid-ask spread, Delta और Theta के आधार पर एक-lot shortlist बनती है; एक lot premium cap ₹9,000 है।
4. Risk-Managed Backtest और Time-Machine Replay UI व संबंधित historical backtest code हटाए गए हैं।
5. Order placement नहीं है; सभी outputs read-only screening हैं।
