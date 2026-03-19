content = open('tests/_verify_evolution.py', encoding='utf-8').read()
content = content.replace(
    'manifest = json.loads(tmp_manifest.read_text())',
    "manifest = json.loads(tmp_manifest.read_text(encoding='utf-8'))"
)
open('tests/_verify_evolution.py', 'w', encoding='utf-8').write(content)
print('fixed, lines:', content.count('\n'))
