# Multi-Agent AI System for Document Processing

This system uses multiple AI agents to classify and process documents from PDF, JSON, or Email (text) formats. It identifies the intent and routes the document to the appropriate agent for further action, maintaining a shared context.

## Features

*   **Input Formats:** PDF, JSON, Email (text files or raw text).
*   **Classifier Agent:**
    *   Detects file format.
    *   Uses Google Gemini to classify document intent (e.g., Invoice, RFQ, Complaint).
    *   Routes to specialized agents.
*   **JSON Agent:**
    *   Processes structured JSON payloads.
    *   Extracts data based on a target schema (example schemas for Invoice, RFQ).
    *   Flags anomalies or missing fields.
*   **Email Agent:**
    *   Processes email content (from .eml files or text).
    *   Extracts sender, subject (if available).
    *   Uses Google Gemini to determine urgency and generate a CRM-style summary.
*   **Shared Memory:**
    *   Logs actions from all agents.
    *   Maintains context (sender, topic, last extracted fields, etc.) per processing thread.
    *   Implemented in-memory (can be upgraded to Redis/SQLite).

## Tech Stack

*   Python 3.x
*   Google Gemini API (via `google-generativeai` SDK)
*   PyPDF2 (for PDF text extraction)
*   Standard Python libraries (`json`, `email`)

## Folder Structure