import time
import urllib3
import urllib.parse
import xmltodict

import logging

from enum import Enum, auto
from io import BytesIO
from pikepdf.models.image import PdfImage
from pikepdf._qpdf import Pdf
from pyzbar import pyzbar

logger = logging.getLogger("scan")

class ScannerError(Exception):
    def __init__(self, message, response):
        self.message = message
        self.response = response

    def __str__(self):
        return f'{self.message}: {self.response.status} {self.response.info()}'

def get_scanner_caps(http):
    r = http.request('GET', '/eSCL/ScannerCapabilities')
    caps = xmltodict.parse(r.data)
    return caps['scan:ScannerCapabilities']

SOURCE_VAL = {
    'Flatbed': 'Platen',
    'ADF': 'Feeder',
}

def build_scan_request_body(source, resolution):
    return \
        '<?xml version="1.0" encoding="UTF-8"?>' + \
        '<scan:ScanSettings xmln:pwg="http://www.pwg.org/schema/2010/12/sm" ' + \
        'xmlns:scan="http://schema.hp.com/imaging/escl/2011/05/03">' + \
        '<pwg:Version>2.6</pwg:Version>' + \
        '<scan:Intent>Document</scan:Intent>' + \
        f'<pwg:InputSource>{source}</pwg:InputSource>' + \
        '<pwg:ScanRegions><pwg:ScanRegion>' + \
        '<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>' + \
        '<pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset>' + \
        '<pwg:Width>2550</pwg:Width><pwg:Height>4200</pwg:Height>' + \
        '</pwg:ScanRegion></pwg:ScanRegions>' + \
        '<pwg:DocumentFormat>application/pdf</pwg:DocumentFormat>' + \
        '<scan:DocumentFormatExt>application/pdf</scan:DocumentFormatExt>' + \
        '<scan:ColorMode>RGB24</scan:ColorMode>' + \
        f'<scan:XResolution>{resolution}</scan:XResolution><scan:YResolution>{resolution}</scan:YResolution>' + \
        '</scan:ScanSettings>'

def get_scanner_status(http):
    r = http.request('GET', '/eSCL/ScannerStatus')
    return xmltodict.parse(r.data)['scan:ScannerStatus']

def wait_for_status(http, f):
    status = get_scanner_status(http)
    while not f(status):
        time.sleep(1)
        status = get_scanner_status(http)

def scan_pdf(http, source, resolution):
    r = http.request('POST', '/eSCL/ScanJobs',
                     headers = {
                        'Content-Type': 'text/xml'
                     },
                     body = build_scan_request_body(SOURCE_VAL[source], resolution))
    if r.status != 201:
        raise ScannerError("Unexpected HTTP status for scan request", r)

    doc_location = urllib.parse.urlsplit(r.info()["location"]).path + '/NextDocument'
    pdf_data = http.request('GET', doc_location).data

    while http.request('GET', doc_location).status != 404:
        logger.warning("We don't handle multiple documents per scan request.")

    return pdf_data

def page_get_barcodes(page):
    out = []
    for img in page.images.values():
        for barcode in pyzbar.decode(PdfImage(img).as_pil_image()):
            code = barcode.data.decode("utf-8")
            logger.debug(code)
            out.append(code)
    return out

def page_contains_separator(page, opts):
    codes = page_get_barcodes(page)
    return opts.document_separator in codes

class PageClassification(Enum):
    DOCUMENT_SEPARATOR = auto()
    NEXT_DOCUMENT_SIMPLEX = auto()

def classify_page(page, opts):
    codes = page_get_barcodes(page)
    classification = set()

    if opts.document_separator in codes:
        classification.add(PageClassification.DOCUMENT_SEPARATOR)

    if opts.document_simplex in codes:
        classification |= { PageClassification.NEXT_DOCUMENT_SIMPLEX, PageClassification.DOCUMENT_SEPARATOR }

    return classification

def pdf_to_bytes(pdf):
    bytes = BytesIO()
    pdf.save(bytes)
    return bytes.getvalue()

def interleave_front_back(front_data, back_data, opts):
    docs = []

    dst = Pdf.new()
    front = Pdf.open(BytesIO(front_data))

    if back_data:
        back = Pdf.open(BytesIO(back_data))
    else:
        back = None

    do_duplex = opts.duplex

    for (front, back) in zip(front.pages, reversed(back.pages) if back else (None for _ in front.pages)):
        classification = classify_page(front, opts)
        if not classification:
            dst.pages.append(front)
            if do_duplex and back:
                dst.pages.append(back)
        else:
            if PageClassification.DOCUMENT_SEPARATOR in classification:
                do_duplex = opts.duplex
                if len(dst.pages) > 0:
                    docs.append(pdf_to_bytes(dst))
                    dst.close()
                    dst = Pdf.new()
            if PageClassification.NEXT_DOCUMENT_SIMPLEX in classification:
                do_duplex = False

    if len(dst.pages) > 0:
        docs.append(pdf_to_bytes(dst))
    return docs

def do_scan(opts):
    def status_check(status):
        return status["pwg:State"] == "Idle" and (status["scan:AdfState"] == "ScannerAdfLoaded" if opts.scanner_source == "ADF" else True)

    with urllib3.HTTPSConnectionPool(opts.scanner_host, cert_reqs='CERT_NONE', assert_fingerprint = opts.scanner_https_fingerprint) as http:
        caps = get_scanner_caps(http)
        SOURCE_CAPS_VAL = {
            "ADF": "scan:Adf",
            "Flatbed": "scan:Platen"
        }
        if SOURCE_CAPS_VAL[opts.scanner_source] not in caps:
            raise ValueError(f'Scanner does not support source type "{opts.scanner_source}"')

        wait_for_status(http, status_check)
        front_data = scan_pdf(http, opts.scanner_source, opts.scanner_dpi)

        if opts.duplex:
            if opts.scanner_source == "Flatbed":
                input("Press Enter to scan backside...")

            wait_for_status(http, status_check)
            back_data = scan_pdf(http, opts.scanner_source, opts.scanner_dpi)
        else:
            back_data = None

    return interleave_front_back(front_data, back_data, opts)

