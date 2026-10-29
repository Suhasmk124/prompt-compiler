"""Regenerate the fictional PDF fixture. Requires reportlab (authoring only)."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4


def create_invoice(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    page = canvas.Canvas(str(destination), pagesize=A4)
    page.setTitle('Cedar and Coast invoice CC-2026-1048')
    width, height = A4
    navy, grey, green = HexColor('#20334a'), HexColor('#64748b'), HexColor('#247f70')
    def text(x, y, value, size=10, bold=False, color=navy):
        page.setFillColor(color)
        page.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        page.drawString(x, y, value)
    page.setFillColor(HexColor('#edf5f2'))
    page.rect(0, height-145, width, 145, fill=1, stroke=0)
    text(45, height-53, 'CEDAR & COAST', 22, True)
    text(45, height-75, 'Office systems and workspace equipment', 10, color=grey)
    text(45, height-101, 'Supplier: Cedar & Coast Office Systems', 10, True)
    text(width-190, height-53, 'TAX INVOICE', 14, True, green)
    text(width-190, height-76, 'CC-2026-1048', 11)
    text(width-190, height-97, 'Issued: 29 October 2026', 9, color=grey)
    text(45, height-183, 'BILL TO', 9, True, grey)
    text(45, height-207, 'Harbor Research Studio', 12, True)
    text(45, height-226, 'Procurement team - demonstration account', 9, color=grey)
    text(365, height-183, 'PAYMENT DETAILS', 9, True, grey)
    text(365, height-207, 'Currency: INR', 10, True)
    text(365, height-226, 'Terms: Net 15 days', 9, color=grey)
    y = height-279
    page.setFillColor(navy)
    page.roundRect(45, y-14, width-90, 30, 4, fill=1, stroke=0)
    for x, label in [(57,'Description'),(323,'Qty'),(381,'Unit price'),(477,'Amount')]:
        text(x, y-3, label, 9, True, HexColor('#ffffff'))
    rows = [('24-inch business monitor', '6', '8,200.00', '49,200.00'),
            ('USB-C docking station', '4', '3,150.00', '12,600.00')]
    for index, row in enumerate(rows):
        row_y = y-48-index*43
        for x, value in zip([57,329,381,477],row):
            text(x,row_y,value,10)
        page.setStrokeColor(HexColor('#e3e9ee'))
        page.line(45,row_y-16,width-45,row_y-16)
    subtotal_y = y-161
    for offset, label, value in [(0,'Subtotal','61,800.00'),(-25,'GST (18%)','11,124.00')]:
        text(330,subtotal_y+offset,label,10,color=grey)
        text(477,subtotal_y+offset,value,10)
    page.setFillColor(HexColor('#edf5f2'))
    page.roundRect(45,subtotal_y-94,width-90,45,6,fill=1,stroke=0)
    text(61,subtotal_y-76,'Amount due: INR 72,924.00',14,True,green)
    text(45,170,'Notes',10,True)
    text(45,150,'Equipment supplied for an internal workspace refresh.',9,color=grey)
    text(45,135,'The amount due includes tax. All amounts are in INR.',9,color=grey)
    page.setStrokeColor(HexColor('#e3e9ee'))
    page.line(45,91,width-45,91)
    text(45,70,'FICTIONAL SAMPLE - software validation only. No payment is due.',8,True,grey)
    text(width-75,70,'1 / 1',8,color=grey)
    page.showPage()
    page.save()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('destination')
    create_invoice(parser.parse_args().destination)
