from pathlib import Path

p = Path(__file__).resolve().parents[1] / "sync" / "validate_phase9_mobile.py"
text = p.read_text(encoding="utf-8")
old = '        \'Text("×"\',\n'
new = '        \'"×"\',\n'
if text.count(old) != 1:
    raise SystemExit(f"expected one validator marker, found {text.count(old)}")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Fixed V6 validator marker")
