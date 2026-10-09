with open(r'C:\D copy\YtMTUI\ytmtui\ui\library.py', 'rb') as f:
    content = f.read()
    lines = content.splitlines()
    for i, line in enumerate(lines[218:235], 218):
        print(f'Line {i}: {repr(line[:80])}')
        # Check for non-space whitespace in leading part
        leading = line[:len(line) - len(line.lstrip(b' '))]
        if leading != b' ' * len(leading):
            print(f'  Line {i}: NON-SPACE LEADING: {leading.hex()}')
        # Check for tabs
        if b'\t' in line[:len(line) - len(line.lstrip())]:
            print(f'  Line has TAB in leading whitespace')
        # Show leading bytes
        print(f'  Leading hex: {leading.hex()}')