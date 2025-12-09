import asyncio
from datetime import datetime
from fastapi import Body
from treehopper.treehopper import agent, get_agent_id
from treehopper.middleware.cancellation_guard import th_sleep
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id
from .schema import ReportGeneratorRequest

agent_name = "report_generator"
agent_id = get_agent_id(agent_name)


@agent("report_generator", method="POST", goal="Generate formatted report")
async def handle(payload: ReportGeneratorRequest = Body(...)):
    run_id = get_run_id()

    print("[report_generator] READY")
    await th_sleep(0)

    # Pre-check cancellation
    if run_id and await is_run_cancelled(run_id):
        print("[report_generator] CANCEL detected before starting")
        raise asyncio.CancelledError()

    print(f"[report_generator] Generating report for {payload.file_name}")

    try:
        # Generate report sections
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        # Sentiment emoji
        sentiment_emoji = {"positive": "✅", "negative": "❌", "neutral": "⚖️"}.get(
            payload.sentiment.lower(), "ℹ️"
        )

        # Build markdown report
        report = f"""# Document Analysis Report

## Document Information
- **File**: `{payload.file_name}`
- **Pages**: {payload.page_count}
- **Analyzed**: {timestamp}

---

## Executive Summary

{payload.summary}

---

## Sentiment Analysis

{sentiment_emoji} **Overall Sentiment**: {payload.sentiment.upper()}

---

## Key Entities Identified

"""

        if payload.key_entities:
            for entity in payload.key_entities:
                report += f"- {entity}\n"
        else:
            report += "*No entities identified*\n"

        report += "\n---\n\n## Main Themes\n\n"

        if payload.themes:
            for i, theme in enumerate(payload.themes, 1):
                report += f"{i}. {theme}\n"
        else:
            report += "*No themes identified*\n"

        report += "\n---\n\n## Metadata\n\n"
        report += "- **Analysis Engine**: Treehopper Document Intelligence\n"
        report += f"- **Report ID**: {run_id or 'N/A'}\n"

        # Simulate some processing time (in real app, might format/style)
        for i in range(5):
            if run_id and await is_run_cancelled(run_id):
                print("[report_generator] CANCEL detected during generation")
                raise asyncio.CancelledError()
            await th_sleep(0.2)

        report_title = f"Analysis: {payload.file_name}"

        print(f"[report_generator] Report complete: {len(report)} characters")

        return {"report_markdown": report, "report_title": report_title}

    except asyncio.CancelledError:
        print("[report_generator] CANCELLED during generation")
        raise
    except Exception as e:
        print(f"[report_generator] ERROR: {e}")
        raise
