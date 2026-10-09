import json

from ytmusicapi import setup

raw = open("_headers_raw.txt", encoding="utf-8").read()
lines = raw.splitlines()

out = []
i = 0
while i < len(lines):
    line = lines[i]
    if not line.strip():
        i += 1
        continue
    if line.startswith(":"):  # HTTP/2 pseudo-header -> skip name + its value line
        i += 2
        continue
    if line.startswith("Decoded:"):  # chrome decoded-proto dump -> skip to closing brace
        i += 1
        while i < len(lines) and lines[i].strip() != "}":
            i += 1
        i += 1
        continue
    name = line.strip()
    value = lines[i + 1] if i + 1 < len(lines) else ""
    out.append(f"{name}: {value}")
    i += 2

cleaned = "\n".join(out)
headers = json.loads(setup(filepath="browser.json", headers_raw=cleaned))
print("browser.json written with keys:")
for k in sorted(headers):
    if k in ("cookie", "authorization"):
        print(f"  {k}: <{len(headers[k])} chars>")
    else:
        print(f"  {k}: {headers[k][:70]}")
