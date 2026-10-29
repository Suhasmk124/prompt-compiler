from .schema import Workflow

DEMOS = {
    'Invoice review': 'Read these invoices, extract vendor names and totals, flag invoices above INR 50,000, and produce an Excel report.',
    'High-value invoices': 'Read these invoices, extract vendor names and totals, keep only invoices above INR 50,000, and produce a CSV report.',
    'Vendor summary': 'Read these invoices, extract vendor names and totals, sum totals by vendor, and produce an Excel report.',
}


def sample_files():
    return {
        'invoice_001.txt': b'Invoice: 001\nVendor: Acme Supplies\nCurrency: INR\nTotal: 50,000\n',
        'invoice_002.txt': b'Invoice: 002\nVendor: Acme Supplies\nCurrency: INR\nTotal: 50,001\n',
        'invoice_003.txt': b'Invoice: 003\nVendor: Delta Labs\nCurrency: INR\nTotal: 12,500\n',
        'invoice_004.txt': b'Invoice: 004\nVendor: Delta Labs\nCurrency: INR\nTotal: 75,000\n',
    }


def demo_workflow(instruction, manifest):
    match = next((name for name, text in DEMOS.items() if text.strip() == instruction.strip()), None)
    if match is None:
        raise ValueError('Offline demo supports only the three exact sample instructions. Select a sample or connect an LLM for your own instruction.')
    documents = [name for name, meta in manifest.items() if meta['kind'] == 'document']
    if not documents:
        raise ValueError('The offline invoice demo requires TXT or text-based PDF invoices.')
    steps = [dict(id='read', label='Read invoice documents', operation='read', files=documents),
             dict(id='extract', label='Extract labeled invoice fields', operation='extract_invoices', source='read')]
    if match == 'Vendor summary':
        steps.append(dict(id='transform', label='Sum totals by vendor', operation='aggregate', source='extract',
                          group_by=['vendor'], column='total', function='sum', output_column='vendor_total'))
    else:
        step = dict(id='transform', label='Flag high-value invoices' if match == 'Invoice review' else 'Keep high-value invoices',
                    operation='flag' if match == 'Invoice review' else 'filter', source='extract', column='total', comparison='gt', value=50000)
        if match == 'Invoice review':
            step['output_column'] = 'needs_review'
        steps.append(step)
    steps.append(dict(id='report', label='Export report', operation='export', source='transform',
                      filename='invoice_report.csv' if match == 'High-value invoices' else 'invoice_report.xlsx'))
    return Workflow(version='1.0', title=match, steps=steps)
