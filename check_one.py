#!/usr/bin/env python3
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
from app.utils.msg_parser import MSGParser

p = r"c:\Apps\Email_reader_app\sample_emails\00063f00c21f1536.msg"
email = MSGParser.parse_msg_file(p)
if not email:
    print('PARSE_ERROR')
else:
    subj = email.get('subject') or ''
    print('subject_len', len(subj))
    print('body_len', len(email.get('body') or ''))
    print('html_len', len(email.get('html_body') or ''))
    print('starts_with_html', (email.get('html_body') or '').strip()[:15])
