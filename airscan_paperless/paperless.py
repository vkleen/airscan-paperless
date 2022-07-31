import logging
import pynentry
import urllib3

logger = logging.getLogger("paperless")

def push_to_paperless(docs, opts):
    with pynentry.PynEntry() as p:
        p.description = f'Enter password to unlock {opts.paperless_cert}'
        p.prompt = 'Password'
        key_password = p.get_pin()

    with urllib3.PoolManager(cert_file=opts.paperless_cert, key_password=key_password) as http:
        for doc in docs:
            http.request('POST', f'{opts.paperless_endpoint}/api/documents/post_document/', headers={
                             "Authorization": f'Token {opts.paperless_token}'
                         }, fields = {
                             'document': ('document.pdf', doc, 'application/pdf')
                         })
