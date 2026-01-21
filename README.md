# Gemini-Powered Customer Service System

This project is an end-to-end intelligent customer service assistant that integrates modern Large Language Models (LLMs) with traditional Machine Learning (ML) algorithms. Developed as part of the "Applications of Artificial Intelligence" course, it demonstrates how to build stateful, multimodal agents for industrial use cases such as logistics and sentiment-driven customer support.

------------------------------------------------------------

KEY TECHNICAL HIGHLIGHTS

- Hybrid AI Architecture: Combines Google Gemini API for natural language generation with custom Scikit-learn models (Logistic Regression & Linear Regression) for sentiment analysis and delivery time forecasting.
- Multimodal Interaction: Integrated gTTS (Google Text-to-Speech) to provide natural-sounding voice responses alongside text-based chat.
- State-Aware Dialogue: Session-based conversation management to maintain context across multi-turn user interactions.
- Operational Intelligence: Automated modules for cargo tracking, tax calculation, and database-driven complaint logging.

------------------------------------------------------------

PREREQUISITES & INSTALLATION

API KEY ACQUISITION

This project requires a Google Gemini API Key.

1) Go to: https://aistudio.google.com/
2) Log in with your Google account.
3) Click "Get API Key" and generate a new key.

------------------------------------------------------------

CLONE THE REPOSITORY

git clone https://github.com/dogaece-koca/ai_customerservice.git
cd ai_customerservice
pip install -r requirements.txt

------------------------------------------------------------

ENVIRONMENT CONFIGURATION

Create a file named .env in the root directory and add:

GEMINI_API_KEY=your_actual_api_key_here

Ensure .env is included in .gitignore to prevent key exposure.

------------------------------------------------------------

PROJECT STRUCTURE

webhook.py
Main Flask server handling API routing and frontend interaction

modules/gemini_ai.py
LLM orchestration and prompt engineering logic

modules/ml_modulu.py
Training and inference for Logistic & Linear Regression models

modules/database.py
SQLite integration for persistence of customer and complaint data

------------------------------------------------------------

RUNNING THE APPLICATION

INITIALIZE THE DATABASE

python db_simulasyon_kurulum.py

START THE SERVER

python webhook.py

ACCESS THE WEB INTERFACE

Open in your browser:
http://127.0.0.1:5000

------------------------------------------------------------

FEATURES DEMONSTRATED

- LLM-powered conversational agent with structured intent handling
- Classical ML integration inside LLM-driven workflows
- Context-aware multi-turn conversation management
- Database-backed customer service simulation
- Voice-enabled assistant responses

------------------------------------------------------------

NOTES

This project is developed for academic and demonstration purposes.
Model performance and dataset size can be extended for production deployment.

------------------------------------------------------------

AUTHOR

Doğa Ece Koca
GitHub: https://github.com/dogaece-koca
