# SHYAM AI — F&O Explosion Scanner V2.5 | Google Cloud Run

यह पैकेज मौजूदा Streamlit scanner को Google Cloud Run पर चलाने के लिए तैयार किया गया है।
Scanner का मूल `app.py` और strategy/ranking logic इस Cloud पैकेज के लिए नहीं बदला गया है।

## इसमें क्या है
- Cloud Run-compatible Dockerfile (PORT environment variable, default 8080)
- Streamlit headless configuration
- `.dockerignore` ताकि `.env`, API secrets, `.venv` और local cache image में न जाएँ
- सुरक्षित default deployment: unauthenticated/public access बंद
- INDstocks token ऐप के Sidebar में session के दौरान manually डालना होगा

## जरूरी सावधानियाँ
1. यह read-only dashboard है; कोई order place नहीं करता।
2. INDstocks API token किसी को साझा न करें और source code/ZIP में hard-code न करें।
3. Cloud Run पर app public न करें। Deploy command में `--no-allow-unauthenticated` है।
4. Streamlit session/browser refresh पर Sidebar token दोबारा डालना पड़ सकता है।
5. Cloud Run internet egress और INDstocks account/API permissions उपलब्ध होने पर ही live data मिलेगा।
6. Cloud Run deployment/Live API/Option Chain को वास्तविक Google Cloud account पर deploy करके जाँचना बाकी है।
7. Google Cloud billing चालू हो सकती है; Cloud Run, Artifact Registry और build usage के charges लागू हो सकते हैं।

## Google Cloud Console / Cloud Shell से Deployment

### A. पहले तैयारी
- Google Cloud project चुनें या बनाएँ।
- Billing enable करें।
- Cloud Run और Cloud Build APIs enable करें।
- Cloud Shell खोलें।
- ZIP को Cloud Shell में upload करें, फिर:

```bash
unzip SHYAM_AI_FO_EXPLOSION_SCANNER_V2_5_GOOGLE_CLOUD.zip
cd SHYAM_AI_FO_EXPLOSION_SCANNER_V2/SHYAM_AI_FO_EXPLOSION_SCANNER_V2
```

> यदि ZIP extract करने पर directory nesting अलग हो, तो `Dockerfile` और `app.py` वाले folder में `cd` करें।

### B. Project सेट करें
```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

### C. Private Cloud Run deployment
```bash
gcloud run deploy shyam-ai-fo-scanner \
  --source . \
  --region asia-south1 \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 1 \
  --max-instances 1 \
  --no-allow-unauthenticated
```

Deployment पूरा होने पर Cloud Run एक HTTPS URL देगा। उस URL को browser में खोलें। Access के लिए Google account को Cloud Run Invoker permission चाहिए।

### D. Invoker access देना
अपने Google account को अनुमति दें (EMAIL बदलें):
```bash
gcloud run services add-iam-policy-binding shyam-ai-fo-scanner \
  --region asia-south1 \
  --member="user:YOUR_EMAIL@gmail.com" \
  --role="roles/run.invoker"
```

### E. INDstocks token
App खुलने के बाद बाईं ओर Sidebar में INDstocks API Access Token डालें। Token को Dockerfile, GitHub repository या ZIP में न लिखें।

## Update deploy
जब नया app.py/Dockerfile आए, उसी project folder में फिर चलाएँ:
```bash
gcloud run deploy shyam-ai-fo-scanner --source . --region asia-south1 --port 8080 --memory 1Gi --cpu 1 --timeout 300 --concurrency 1 --max-instances 1 --no-allow-unauthenticated
```

## Troubleshooting
- **Container failed to start / port error:** Cloud Run को `PORT=8080` चाहिए; इस package का Dockerfile उसी port पर सुनता है।
- **403:** अपने Google account को `roles/run.invoker` दें और सही account से login करें।
- **INDstocks disconnected:** token, API access, outbound network और API status जाँचें।
- **App session/token reset:** Streamlit session reconnect या नया browser session होने पर token फिर डालें।
- **Cloud Run logs:** Google Cloud Console → Cloud Run → shyam-ai-fo-scanner → Logs.

## Local Ubuntu पर चलाना
इस Cloud ZIP का मुख्य उद्देश्य Cloud Run है। Local Ubuntu के लिए मौजूदा `RUN_UBUNTU.sh` उपलब्ध है।
