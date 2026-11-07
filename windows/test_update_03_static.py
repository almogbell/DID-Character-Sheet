from pathlib import Path
import ast
for name in ("frontend_2_8.py", "mobile_sync_frontend_adapter.py"):
    ast.parse(Path(name).read_text(encoding="utf-8"))
print("Syntax OK")
