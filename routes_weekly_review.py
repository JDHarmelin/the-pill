"""
Weekly AI portfolio review route.
Integrate into app.py by importing and registering:
    app.route("/api/weekly-review")(weekly_review_route)
"""

from flask import jsonify


def weekly_review_route():
    """Generate weekly AI portfolio review."""
    # Late imports to avoid circular dependency if this module is imported by app.py
    from app import get_portfolio_mgr, get_claude_client

    pm = get_portfolio_mgr()
    portfolios = pm.get_all()
    if not portfolios:
        return jsonify({"error": "No portfolios"}), 400

    # Gather data
    all_data = []
    for p in portfolios:
        positions, cash = pm.get_positions_with_returns(p["id"])
        summary = pm.get_summary(p["id"], positions, cash)
        all_data.append({"portfolio": p, "positions": positions, "summary": summary})

    # Build prompt
    from tools.ai_portfolio_prompts import build_weekly_review_prompt
    prompt = build_weekly_review_prompt(all_data, "Market summary placeholder")

    # Call Claude
    client = get_claude_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system="You are a sharp, no-BS hedge fund manager writing a weekly letter.",
        messages=[{"role": "user", "content": prompt}],
    )
    review = "".join(
        getattr(b, "text", "")
        for b in response.content
        if getattr(b, "type", "") == "text"
    )
    return jsonify({"review": review})
