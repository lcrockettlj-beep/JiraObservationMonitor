from pathlib import Path

root = Path(__file__).resolve().parents[1]
change = (root / "JOM Living Guide" / "JOM Change History.md").read_text(encoding="utf-8-sig")
progress = (root / "JOM Living Guide" / "JOM Progress and Improvements.md").read_text(encoding="utf-8-sig")
marker = "## 18 August 2026 - Estate Configuration inventory and evidence refinement"
required = [
    "Estate Configuration remains accepted.",
    "This refinement is presentation-only.",
    "estate_monitored_product_authority_v1.json",
    "After a chat reset, resume from BOOKSYNC installation and commit validation.",
]
for name, text in [("JOM Change History.md", change), ("JOM Progress and Improvements.md", progress)]:
    assert text.count(marker) == 1, (name, "entry count", text.count(marker))
    for value in required:
        assert value in text, (name, value)
    assert "[APPEND THIS ENTRY" not in text, name
print("PASS: Complete Estate Configuration refinement BOOKSYNC owners validated.")
