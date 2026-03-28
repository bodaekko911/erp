# POS System (FastAPI)

A simple but powerful POS system built with FastAPI.

## Features
- Product search (name / SKU / barcode)
- Cart system (add / edit qty / remove)
- Checkout with receipt
- Stock tracking
- Customer management
- Cash + change calculation
- Login system

## Tech Stack
- FastAPI
- SQLAlchemy
- HTML + JavaScript

## Run Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload