from pathlib import Path

app = Path("app.py")
text = app.read_text(encoding="utf-8")
anchor = "from cbb_dashboard.performance import (\n"
if "from cbb_dashboard.public_consensus import attach_aggregated_consensus" not in text:
    text = text.replace(anchor, "from cbb_dashboard.public_consensus import attach_aggregated_consensus\n" + anchor, 1)
needle = "                board = attach_market_to_board(board, display_snapshots, market_context)\n"
replacement = needle + "                try:\n                    board = attach_aggregated_consensus(store._public, board, slate_date)\n                except Exception:\n                    pass\n"
if needle not in text:
    raise SystemExit("Missing CBB market attachment anchor")
text = text.replace(needle, replacement, 1)
app.write_text(text, encoding="utf-8")

intel = Path("cbb_dashboard/intelligence.py")
text = intel.read_text(encoding="utf-8")
anchor = "from .market import context_flags, market_features\n"
if "from .public_consensus import aggregate_public_books_html" not in text:
    text = text.replace(anchor, anchor + "from .public_consensus import aggregate_public_books_html\n", 1)
needle = "        {betting_splits_html(row)}\n        {betting_snapshot_html(row)}\n"
replacement = "        {betting_splits_html(row)}\n        {aggregate_public_books_html(row)}\n        {betting_snapshot_html(row)}\n"
if needle not in text:
    raise SystemExit("Missing CBB game card split anchor")
text = text.replace(needle, replacement, 1)
intel.write_text(text, encoding="utf-8")
