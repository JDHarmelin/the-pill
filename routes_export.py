"""
Standalone export route functions for portfolio data.
Wire these into app.py via app.route(...)(func).
"""

from flask import request, make_response, jsonify
from tools.portfolio_manager import PortfolioManager
from tools.export_utils import (
    export_positions_csv,
    export_trades_csv,
    export_performance_csv,
    generate_portfolio_pdf,
    generate_tax_lot_report,
)

_mgr = None


def _get_mgr():
    global _mgr
    if _mgr is None:
        _mgr = PortfolioManager()
    return _mgr


def export_positions_csv_route(pid):
    fmt = request.args.get("format", "csv")
    mgr = _get_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    positions, _ = mgr.get_positions_with_returns(pid)
    filename = f"{portfolio['name']}_positions.csv".replace(" ", "_")
    if fmt == "csv":
        csv_data = export_positions_csv(positions, portfolio["name"])
        response = make_response(csv_data)
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    return jsonify({"error": "Unsupported format"}), 400


def export_trades_csv_route(pid):
    fmt = request.args.get("format", "csv")
    mgr = _get_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    trades = mgr.get_trade_history(pid)
    filename = f"{portfolio['name']}_trades.csv".replace(" ", "_")
    if fmt == "csv":
        csv_data = export_trades_csv(trades, portfolio["name"])
        response = make_response(csv_data)
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    return jsonify({"error": "Unsupported format"}), 400


def export_performance_csv_route(pid):
    fmt = request.args.get("format", "csv")
    mgr = _get_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    nav_history = mgr.get_nav_history(pid)
    filename = f"{portfolio['name']}_performance.csv".replace(" ", "_")
    if fmt == "csv":
        csv_data = export_performance_csv(nav_history, portfolio["name"])
        response = make_response(csv_data)
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    return jsonify({"error": "Unsupported format"}), 400


def export_portfolio_pdf_route(pid):
    mgr = _get_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    positions, cash = mgr.get_positions_with_returns(pid)
    summary = mgr.get_summary(pid, positions=positions, cash=cash)
    try:
        pdf_bytes = generate_portfolio_pdf(portfolio, positions, summary)
    except ImportError as e:
        return jsonify({"error": str(e)}), 400
    filename = f"{portfolio['name']}_report.pdf".replace(" ", "_")
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_tax_lot_route(pid):
    method = request.args.get("method", "FIFO")
    mgr = _get_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    positions, _ = mgr.get_positions_with_returns(pid)
    trades = mgr.get_trade_history(pid)
    csv_data = generate_tax_lot_report(positions, trades, method)
    filename = f"{portfolio['name']}_taxlots.csv".replace(" ", "_")
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
