"""Integration tests for the retrieval pipeline against live data.

These tests require a running Supabase instance and ingested corpus.
Run with: pytest tests/retrieval/test_integration.py -m integration
"""

import os
import pytest
from openai import OpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.retrieval.retriever import DocumentRetriever


@pytest.mark.integration
def test_apple_revenue_query():
    """Retrieve passages for Apple revenue question."""
    if not settings.database_url or not settings.openai_api_key:
        pytest.skip("Database or OpenAI API key not configured")

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        openai_client = OpenAI(api_key=settings.openai_api_key)
        retriever = DocumentRetriever(openai_client)

        passages = retriever.retrieve(
            "Apple iPhone revenue Services Mac iPad Wearables",
            db,
            top_k=5,
        )

        assert len(passages) > 0, "No passages retrieved for Apple revenue query"
        tickers = {p.ticker for p in passages}
        assert "AAPL" in tickers, f"AAPL not in tickers: {tickers}"

        assert all(p.filing_year >= 2021 for p in passages), "Retrieved old filings"
    finally:
        db.close()


@pytest.mark.integration
def test_amazon_aws_query():
    """Retrieve passages for Amazon AWS question."""
    if not settings.database_url or not settings.openai_api_key:
        pytest.skip("Database or OpenAI API key not configured")

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        openai_client = OpenAI(api_key=settings.openai_api_key)
        retriever = DocumentRetriever(openai_client)

        passages = retriever.retrieve(
            "Amazon AWS operating income margin North America International",
            db,
            top_k=5,
        )

        assert len(passages) > 0, "No passages retrieved for AWS query"
        tickers = {p.ticker for p in passages}
        assert "AMZN" in tickers, f"AMZN not in tickers: {tickers}"
    finally:
        db.close()


@pytest.mark.integration
def test_multi_company_query():
    """Retrieve passages for a multi-company comparison."""
    if not settings.database_url or not settings.openai_api_key:
        pytest.skip("Database or OpenAI API key not configured")

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        openai_client = OpenAI(api_key=settings.openai_api_key)
        retriever = DocumentRetriever(openai_client)

        passages = retriever.retrieve(
            "capital expenditure AI cloud infrastructure investment Microsoft Alphabet Amazon NVIDIA",
            db,
            top_k=10,
        )

        assert len(passages) > 0, "No passages retrieved for capex query"
        tickers = {p.ticker for p in passages}
        assert len(tickers) >= 2, f"Expected multiple companies, got {tickers}"
    finally:
        db.close()
