from pathlib import Path

p = Path(__file__).with_name("app") / "setup_wizard.py"
text = p.read_text(encoding="utf-8")
for pack in ("photoreal", "anime", "cinematic"):
    old = (
        f'source_repo="adept://marketplace/pack_essential_{pack}",\n'
        '        license="Curated / check sources",\n'
        '        install_kind="path_link",'
    )
    new = old.replace('install_kind="path_link"', 'install_kind="asset_pack"')
    if old not in text:
        raise SystemExit(f"missing {pack}")
    text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
print("updated")
