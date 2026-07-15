# Personal Finance Copilot — Backend

An AI-powered Personal Finance Copilot backend that ingests a user's financial
documents (bank statements, credit card statements, salary slips, investment
and loan statements), runs them through a linear multi-agent pipeline (parse →
categorize → analyze → recommend), and assembles a financial profile and
dashboard from the results.

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env  # fill in SUPABASE_URL, SUPABASE_KEY, LLM_API_KEY
uvicorn app.main:app --reload
```
