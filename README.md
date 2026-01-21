# Gemini-Powered Customer Service System

This project is a comprehensive intelligent assistant developed for the **"Applications of Artificial Intelligence"** course. It bridges the gap between modern Large Language Models (LLMs) and traditional Machine Learning (ML) to automate complex customer service workflows, including logistics tracking, sentiment-driven interactions, and predictive analytics.

## 🚀 Key Features

* **Gemini-Flash Integration:** Leverages the **Google Gemini-Flash API** for advanced Natural Language Understanding (NLU) and generating context-aware, empathetic responses.
* **Hybrid Machine Learning Architecture:**
    * **Sentiment Analysis:** A custom-trained **Logistic Regression** model (using Scikit-learn) that detects user emotions (Happy, Angry, Neutral) to adjust response tone dynamically.
    * **Delivery Prediction:** A **Linear Regression** model that estimates package arrival times based on historical logistics data.
* **Multimodal Capabilities:** Integrated **gTTS (Google Text-to-Speech)** to provide natural language voice responses alongside text-based chat.
* **State-Aware Dialogue Management:** Implements session-based tracking to manage **multi-turn conversations**, ensuring the assistant remembers previous user inputs and context.
* **Operational Automation:** Supports functional tools such as real-time cargo tracking, international tax calculation, and automated complaint filing linked to a backend database.

## 🛠 Technology Stack

* **Backend:** Python, Flask
* **Generative AI:** Google Gemini API (Gemini-Flash)
* **Machine Learning:** Scikit-learn, Pandas, NumPy
* **Database:** SQLite (for customer records and complaint logs)
* **Voice Processing:** gTTS (Google Text-to-Speech)
* **Frontend:** HTML5, CSS3, JavaScript

## 📂 Project Structure

| File/Folder | Description |
| :--- | :--- |
| `webhook.py` | The main Flask server and API routing hub. |
| `modules/ml_modulu.py` | Training and prediction logic for Logistic and Linear Regression models. |
| `modules/gemini_ai.py` | LLM prompt engineering and Gemini API orchestration. |
| `modules/database.py` | Database schema management and CRUD operations. |
| `templates/index.html` | The web-based chat interface. |

## ⚙️ Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/dogaece-koca/customerservice_ai.git](https://github.com/dogaece-koca/customerservice_ai.git)
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure API Key:**
    Insert your Google AI Studio API key in the `modules/gemini_ai.py` file.
4.  **Run the application:**
    ```bash
    python webhook.py
    ```

## 📝 Learning Objectives

This project was engineered to demonstrate proficiency in:
* Integrating state-of-the-art LLMs into production-ready web frameworks.
* Implementing **Hybrid AI** systems that combine heuristic rules, custom ML models, and Generative AI.
* Designing stateful conversational agents for complex business logic.
* Applying Data Pre-processing and Feature Engineering for real-world predictive tasks.
