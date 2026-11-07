from pathlib import Path
import ast

source = Path(__file__).parent / "windows" / "mobile_sync_server.py"
text = source.read_text(encoding="utf-8")
ast.parse(text)
assert "DEFAULT_PORT <= self.port <= DEFAULT_PORT + FALLBACK_PORT_SPAN" in text
assert "range(preferred_port, final_port + 1)" in text
print("PASS: port fallback source invariants and syntax")
