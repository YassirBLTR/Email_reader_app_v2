#!/usr/bin/env python3
import os, sys, json
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
from pathlib import Path
from app.utils.msg_parser import MSGParser

def main():
    samples = Path(r"c:\Apps\Email_reader_app\sample_emails")
    files = sorted(samples.glob("*.msg"))
    rows = []
    for p in files:
        data = MSGParser.parse_msg_file(str(p))
        if not data:
            rows.append((p.name, 'PARSE_ERROR', 0, 0))
            continue
        body_len = len(data.get('body') or '')
        html_len = len(data.get('html_body') or '')
        rows.append((p.name, data.get('subject',''), body_len, html_len))
    print("filename\tsubject_snippet\tbody_len\thtml_len")
    for name, subj, bl, hl in rows:
        subj_snip = (subj[:60] + ('…' if len(subj) > 60 else '')) if isinstance(subj, str) else ''
        print(f"{name}\t{subj_snip}\t{bl}\t{hl}")

if __name__ == '__main__':
    main()
