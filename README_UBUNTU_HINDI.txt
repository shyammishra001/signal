SHYAM AI — F&O EXPLOSION SCANNER V2.5 (UBUNTU EDITION)
=====================================================

यह Ubuntu/Linux के लिए V2.5 का रनर पैकेज है। app.py, scanner logic,
ranking और option-chain logic मूल V2.5 से रखे गए हैं। Backtest / Time-Machine module इस build से हटा दिया गया है।
केवल Windows .bat launcher के स्थान पर Linux shell launcher दिया गया है।

1) आवश्यकताएँ
-------------
- Ubuntu 20.04 या नया (अनुशंसित)
- Python 3.8 या नया (Python 3.11/3.12 अनुशंसित; Python 3.8 के लिए compatibility package शामिल है)
- इंटरनेट कनेक्शन (पहली बार Python packages install करने के लिए)
- INDstocks API access token

2) पहली बार तैयारी
-----------------
ZIP को Extract करें। फिर Extract किए गए folder में Terminal खोलें।
यदि Python/venv उपलब्ध नहीं है, तो ये commands चलाएँ:

  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip

यदि आपके ऑफिस PC पर sudo/admin अधिकार नहीं हैं, तो IT administrator से
ऊपर के Ubuntu packages install करवाएँ।

3) Dashboard चलाएँ
------------------
Terminal में project folder के अंदर:

  chmod +x RUN_UBUNTU.sh
  ./RUN_UBUNTU.sh

पहली बार script .venv बनाएगी और requirements.txt से packages install करेगी।
Python 3.8 पर timezone compatibility package भी install होगा। इसके बाद Streamlit dashboard शुरू होगा। Browser में यह address खुलेगा:

  http://127.0.0.1:8501

यदि browser अपने-आप न खुले तो ऊपर दिया address Firefox/Chrome में खोलें।
Dashboard रोकने के लिए Terminal में Ctrl+C दबाएँ। अगली बार केवल
./RUN_UBUNTU.sh चलाएँ।

4) API Token सुरक्षा
--------------------
- Sidebar में INDstocks access token डालें।
- Token को screenshot, WhatsApp, ChatGPT message या public GitHub में न डालें।
- यह build READ-ONLY है; कोई order place नहीं करता।
- Token session में उपयोग होता है। Dashboard बंद करने के बाद जरूरत हो तो
  token फिर दर्ज करें।

5) Troubleshooting
------------------
A. “ensurepip” या “venv” error:
   sudo apt install -y python3-venv python3-pip

B. pandas/numpy या package install error:
   इंटरनेट/Proxy जाँचें। फिर project folder में:
   rm -rf .venv
   ./RUN_UBUNTU.sh

C. Port 8501 पहले से उपयोग में है:
   दूसरे Streamlit process को Ctrl+C से रोकें। यदि वह उपलब्ध नहीं है,
   तो RUN_UBUNTU.sh में --server.port 8501 को 8502 करें और browser में
   http://127.0.0.1:8502 खोलें।

D. Browser में page नहीं खुलता:
   Terminal में Streamlit का error देखें। यह local app है; address
   127.0.0.1 पर ही bind होता है।

6) महत्वपूर्ण सीमाएँ
-------------------
- यह Ubuntu package live INDstocks API response की गारंटी नहीं देता;
  आपके token, account permissions, network और API availability पर निर्भर है।
- Option chain में केवल API से लौटे वास्तविक contracts/strikes दिखेंगे।
- इस build में backtest / Time-Machine replay उपलब्ध नहीं है।
- ₹10,000 budget shortlist में एक lot premium अधिकतम ₹9,000 रखा जाता है; charges,
  spread और slippage अलग हैं। Greeks/Theta indicative हैं; IV, liquidity, charges,
  expiry और gap risk वास्तविक P&L को प्रभावित करते हैं।
- Trading से पहले paper validation करें।

7) Windows संस्करण
------------------
Windows उपयोग के लिए RUN_WINDOWS.bat उपलब्ध है। Linux के लिए
RUN_UBUNTU.sh इस्तेमाल करें। दोनों एक ही app.py और strategy logic चलाते हैं।

नया Historical Risk Guard / secrets.toml Fix:
- Local run के लिए `.streamlit/secrets.toml` आवश्यक नहीं है। Optional app password केवल `APP_PASSWORD` environment variable से लिया जाएगा।
- Intelligent Adaptive Pick के दोनों संभावित leaders पर INDstocks Historical Data API के `1day` candles से हाल के दैनिक उतार-चढ़ाव की जाँच होती है।
- बड़ा daily fall अपने-आप BUY PE signal नहीं है। सिस्टम आज के move की तुलना पिछले sessions के typical move से करता है और 1m/3m/5m confirmation न होने पर chase score घटाता है।
- OHLCV से गिरावट का कारण सिद्ध नहीं होता; कंपनी announcement/news की अलग पुष्टि जरूरी है।
