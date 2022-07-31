import argparse
import logging
import os

from .scan import do_scan
from .paperless import push_to_paperless

DEFAULT_SCANNER = 'forst.forstheim.kleen.org'
DEFAULT_SCAN_FP = 'E4:17:14:E2:89:C3:54:FD:22:F2:9B:DF:5E:0F:7B:D2:33:C3:59:4C:AF:B9:14:34:EA:46:92:A6:7D:38:14:98'
DEFAULT_SCAN_SOURCE = 'ADF'
DEFAULT_SCAN_DPI = 300

DEFAULT_PAPERLESS_ENDPOINT = 'https://paperless.kleen.org'
DEFAULT_PAPERLESS_CERT_FILE = 'client_cert.pem'

DEFAULT_SEPARATOR_CODE = "Document separator 5d6067b98de37c129051ff34f78dddd86ce9fb6f4c9802b4f67a80bcae89bea93909b4ad84c124afdb40f02fe19a9a100c9eb2bfa399dab12bee67e9816f601a"
DEFAULT_SIMPLEX_CODE = "Simplex Document 9b9466ff1dfcbb765c74f2bc529f92146c217e8d1ab71bf99e428cb6b524f52026653230fee8f8e80ed802ffacc78503a6cbc8e56b83cff5aaee85671f70c4b7"

def parse_options():
    p = argparse.ArgumentParser(description='Scan from AirScan scanner and upload to paperless')
    p.add_argument('-u', '--scanner-host', help=f'Address of the scanner, defaults to {DEFAULT_SCANNER}', default=DEFAULT_SCANNER)
    p.add_argument('-S', '--scanner-source', help=f'Scanner source, can be "Flatbed" or "ADF", defaults to "{DEFAULT_SCAN_SOURCE}"', default=DEFAULT_SCAN_SOURCE)
    p.add_argument('-r', '--scanner-dpi', help=f'Scan resolution in DPI, defaults to {DEFAULT_SCAN_DPI}', default=DEFAULT_SCAN_DPI)
    p.add_argument('-f', '--scanner-https-fingerprint', help=f'Scanner certificate fingerprint, defaults to {DEFAULT_SCAN_FP}', default=DEFAULT_SCAN_FP)
    p.add_argument('-s', '--simplex', help=f'Run simplex cycle', action='store_false', dest='duplex', default=True)
    p.add_argument('-p', '--document-separator', help=f'Page separator barcode value', default=DEFAULT_SEPARATOR_CODE)
    p.add_argument('--document-simplex', help=f'Barcode value for a simplex document', default=DEFAULT_SIMPLEX_CODE)
    p.add_argument('-e', '--paperless-endpoint', help=f'Paperless endpoint, defaults to {DEFAULT_PAPERLESS_ENDPOINT}', default=DEFAULT_PAPERLESS_ENDPOINT)
    p.add_argument('-c', '--paperless-cert', help=f'Paperless client certificate path, defaults to {DEFAULT_PAPERLESS_CERT_FILE}', default=DEFAULT_PAPERLESS_CERT_FILE)
    return p.parse_args()

def app():
    logging.basicConfig(level=logging.DEBUG)
    opts = parse_options()
    opts.paperless_token = os.getenv('AIRSCAN_PAPERLESS_TOKEN')
    
    docs = do_scan(opts)
    push_to_paperless(docs, opts)
