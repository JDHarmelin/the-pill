"""
Export utilities for portfolio data.
"""

import csv
import io
from collections import defaultdict, deque
from datetime import datetime


def export_positions_csv(positions: list[dict], portfolio_name: str) -> str:
    """Export positions to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Portfolio", "Ticker", "Shares", "Avg Cost", "Current Price",
        "Cost Basis", "Market Value", "Gain/Loss $", "Gain/Loss %", "Sector"
    ])
    for pos in positions:
        writer.writerow([
            portfolio_name,
            pos.get("ticker", ""),
            pos.get("shares", ""),
            pos.get("avg_cost", ""),
            pos.get("current_price", ""),
            pos.get("cost_basis", ""),
            pos.get("current_value", ""),
            pos.get("gain", ""),
            f"{pos.get('gain_pct', '')}%" if pos.get("gain_pct") is not None else "",
            pos.get("sector", ""),
        ])
    return output.getvalue()


def export_trades_csv(trades: list[dict], portfolio_name: str) -> str:
    """Export trade history to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Portfolio", "Date", "Ticker", "Action", "Shares", "Price", "Value", "Notes"
    ])
    for t in trades:
        value = float(t.get("shares", 0)) * float(t.get("price", 0))
        writer.writerow([
            portfolio_name,
            t.get("date", ""),
            t.get("ticker", ""),
            t.get("action", ""),
            t.get("shares", ""),
            t.get("price", ""),
            round(value, 2),
            t.get("notes", ""),
        ])
    return output.getvalue()


def export_performance_csv(nav_history: list[dict], portfolio_name: str) -> str:
    """Export NAV snapshots to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Portfolio", "Date", "Total Value", "Cash", "Benchmark Value"
    ])
    for row in nav_history:
        writer.writerow([
            portfolio_name,
            row.get("date", ""),
            row.get("total_value", ""),
            row.get("cash", ""),
            row.get("benchmark_value", ""),
        ])
    return output.getvalue()


def generate_portfolio_pdf(portfolio_data: dict, positions: list, summary: dict) -> bytes:
    """Generate a PDF report using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except Exception as exc:
        raise ImportError("reportlab is required for PDF generation") from exc

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        rightMargin=72, leftMargin=72,
        topMargin=72, bottomMargin=18
    )
    styles = getSampleStyleSheet()
    story = []

    # Cover header
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#000000"),
        spaceAfter=12,
    )
    story.append(
        Paragraph(f"Portfolio Report: {portfolio_data.get('name', 'Unnamed')}", title_style)
    )
    story.append(
        Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"])
    )
    story.append(Spacer(1, 12))

    # Summary box
    total_value = float(summary.get("total_value", 0)) if summary else 0.0
    total_gain = float(summary.get("total_gain", 0)) if summary else 0.0
    total_gain_pct = float(summary.get("total_gain_pct", 0)) if summary else 0.0
    story.append(
        Paragraph(f"<b>Total Value:</b> ${total_value:,.2f}", styles["Normal"])
    )
    story.append(
        Paragraph(
            f"<b>Total Return:</b> ${total_gain:,.2f} ({total_gain_pct:,.2f}%)",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 12))

    # Position table with P&L
    if positions:
        data = [
            ["Ticker", "Shares", "Avg Cost", "Price", "Cost Basis", "Mkt Value", "Gain $", "Gain %"]
        ]
        for pos in positions:
            data.append([
                pos.get("ticker", ""),
                f"{float(pos.get('shares', 0)):,.2f}",
                f"${float(pos.get('avg_cost', 0)):,.2f}",
                f"${float(pos.get('current_price', 0)):,.2f}" if pos.get("current_price") is not None else "—",
                f"${float(pos.get('cost_basis', 0)):,.2f}",
                f"${float(pos.get('current_value', 0)):,.2f}" if pos.get("current_value") is not None else "—",
                f"${float(pos.get('gain', 0)):,.2f}" if pos.get("gain") is not None else "—",
                f"{float(pos.get('gain_pct', 0)):,.2f}%" if pos.get("gain_pct") is not None else "—",
            ])
        t = Table(data, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    # Allocation (text-based bars)
    if positions and total_value:
        story.append(Paragraph("<b>Allocation</b>", styles["Heading3"]))
        alloc_data = [["Ticker", "% of Portfolio", "Bar"]]
        for pos in positions:
            mkt = float(pos.get("current_value") or pos.get("cost_basis") or 0)
            pct = (mkt / total_value * 100) if total_value else 0
            bar = "█" * int(pct / 2)
            alloc_data.append([pos.get("ticker", ""), f"{pct:.1f}%", bar])
        alloc_table = Table(alloc_data, hAlign="LEFT", colWidths=[80, 80, 200])
        alloc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ]))
        story.append(alloc_table)
        story.append(Spacer(1, 12))

    # Risk metrics box
    risk = summary.get("risk", {}) if summary else {}
    if risk:
        story.append(Paragraph("<b>Risk Metrics</b>", styles["Heading3"]))
        story.append(
            Paragraph(f"Volatility: {risk.get('volatility', 'N/A')}%", styles["Normal"])
        )
        story.append(Paragraph(f"Beta: {risk.get('beta', 'N/A')}", styles["Normal"]))
        story.append(Paragraph(f"Sharpe: {risk.get('sharpe', 'N/A')}", styles["Normal"]))
        story.append(Spacer(1, 12))

    # Disclaimer footer
    story.append(Paragraph(
        "<i>Disclaimer: This report is for informational purposes only and does not constitute investment advice.</i>",
        styles["Normal"],
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()


def generate_tax_lot_report(positions: list[dict], trades: list[dict], method: str = "FIFO") -> str:
    """Generate tax lot report (FIFO or LIFO)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Ticker", "Shares", "Avg Cost", "Date Acquired", "Cost Basis",
        "Current Price", "Unrealized Gain/Loss", "Method"
    ])

    lots = defaultdict(deque)
    for t in sorted(trades, key=lambda x: x.get("date", "")):
        action = t.get("action", "").lower()
        ticker = t.get("ticker", "")
        shares = float(t.get("shares", 0))
        price = float(t.get("price", 0))
        date = t.get("date", "")
        if action in ("buy", "add"):
            lots[ticker].append({"shares": shares, "price": price, "date": date})
        elif action == "sell":
            remaining = shares
            while remaining > 0 and lots[ticker]:
                if method.upper() == "LIFO":
                    lot = lots[ticker].pop()
                else:
                    lot = lots[ticker].popleft()
                if lot["shares"] <= remaining:
                    remaining -= lot["shares"]
                else:
                    lot["shares"] -= remaining
                    remaining = 0
                    if method.upper() == "LIFO":
                        lots[ticker].append(lot)
                    else:
                        lots[ticker].appendleft(lot)

    price_map = {p["ticker"]: p.get("current_price") for p in positions}
    for pos in positions:
        ticker = pos.get("ticker", "")
        total_shares = float(pos.get("shares", 0))
        avg_cost = float(pos.get("avg_cost", 0))
        current_price = price_map.get(ticker)
        if ticker in lots and lots[ticker]:
            for lot in lots[ticker]:
                cost_basis = lot["shares"] * lot["price"]
                unrealized = (
                    (current_price * lot["shares"] - cost_basis)
                    if current_price is not None else None
                )
                writer.writerow([
                    ticker,
                    lot["shares"],
                    round(lot["price"], 2),
                    lot["date"],
                    round(cost_basis, 2),
                    current_price if current_price is not None else "—",
                    round(unrealized, 2) if unrealized is not None else "—",
                    method.upper(),
                ])
        else:
            cost_basis = total_shares * avg_cost
            unrealized = (
                (current_price * total_shares - cost_basis)
                if current_price is not None else None
            )
            writer.writerow([
                ticker,
                total_shares,
                round(avg_cost, 2),
                pos.get("added_date", ""),
                round(cost_basis, 2),
                current_price if current_price is not None else "—",
                round(unrealized, 2) if unrealized is not None else "—",
                method.upper(),
            ])

    return output.getvalue()
