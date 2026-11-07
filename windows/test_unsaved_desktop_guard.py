from pathlib import Path
import ast
p=Path(__file__).resolve().parents[1]/"windows/mobile_sync_frontend_adapter.py"
tree=ast.parse(p.read_text())
method=next(n for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="DesktopSyncAdapter" for n in c.body if isinstance(n,ast.FunctionDef) and n.name=="_save_phone_snapshot")
assert any(isinstance(n,ast.Attribute) and n.attr=="unsaved_changes" for n in ast.walk(method))
assert any(isinstance(n,ast.Constant) and isinstance(n.value,str) and "unsaved changes on Windows" in n.value for n in ast.walk(method))
print("PASS: active unsaved desktop conflict guard")
