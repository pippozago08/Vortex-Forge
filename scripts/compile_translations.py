import ast
import struct
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
LOCALE_DIR = BASE_DIR / "locale"


def parse_po(po_path):
    messages = {}
    msgid = ""
    msgstr = ""
    state = None
    fuzzy = False

    def flush():
        nonlocal msgid, msgstr, fuzzy
        if state == "msgstr" and not fuzzy:
            messages[msgid] = msgstr
        msgid = ""
        msgstr = ""
        fuzzy = False

    with po_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()

            if not line:
                flush()
                state = None
                continue

            if line.startswith("#,") and "fuzzy" in line:
                fuzzy = True
                continue

            if line.startswith("#"):
                continue

            if line.startswith("msgid "):
                if state == "msgstr":
                    flush()
                msgid = ast.literal_eval(line[5:].strip())
                msgstr = ""
                state = "msgid"
                continue

            if line.startswith("msgstr "):
                msgstr = ast.literal_eval(line[6:].strip())
                state = "msgstr"
                continue

            if line.startswith('"'):
                value = ast.literal_eval(line)
                if state == "msgid":
                    msgid += value
                elif state == "msgstr":
                    msgstr += value

    if state == "msgstr":
        flush()

    return messages


def write_mo(messages, mo_path):
    keys = sorted(messages.keys())
    ids = b""
    strs = b""
    offsets = []

    for key in keys:
        value = messages[key]
        key_bytes = key.encode("utf-8")
        value_bytes = value.encode("utf-8")
        offsets.append((len(ids), len(key_bytes), len(strs), len(value_bytes)))
        ids += key_bytes + b"\0"
        strs += value_bytes + b"\0"

    keystart = 7 * 4
    orig_table_offset = keystart
    trans_table_offset = orig_table_offset + len(keys) * 8
    ids_offset = trans_table_offset + len(keys) * 8
    strs_offset = ids_offset + len(ids)

    output = [struct.pack("<Iiiiiii", 0x950412DE, 0, len(keys), orig_table_offset, trans_table_offset, 0, 0)]
    output.extend(struct.pack("<ii", length, ids_offset + offset) for offset, length, _, _ in offsets)
    output.extend(struct.pack("<ii", length, strs_offset + offset) for _, _, offset, length in offsets)
    output.append(ids)
    output.append(strs)

    mo_path.parent.mkdir(parents=True, exist_ok=True)
    mo_path.write_bytes(b"".join(output))


def compile_all():
    count = 0
    for po_path in LOCALE_DIR.rglob("*.po"):
        mo_path = po_path.with_suffix(".mo")
        messages = parse_po(po_path)
        write_mo(messages, mo_path)
        print(f"Compiled {po_path.relative_to(BASE_DIR)} -> {mo_path.relative_to(BASE_DIR)}")
        count += 1
    if count == 0:
        print("No translation files found.")


if __name__ == "__main__":
    compile_all()
