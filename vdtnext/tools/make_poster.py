"""QR code (SVG/PNG) and A4 poster PDF: python3 make_poster.py URL OUTDIR  (needs: pip install segno reportlab)"""
import os, sys, segno
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

url, out = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '.'
qr = segno.make(url, error='m')
qr.save(os.path.join(out, 'vdtnext-qr.svg'), scale=10, border=4)
qr.save(os.path.join(out, 'vdtnext-qr.png'), scale=20, border=4)

pdfmetrics.registerFont(TTFont('G', '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'))
W, H = A4
c = canvas.Canvas(os.path.join(out, 'vdtnext-poster-A4.pdf'), pagesize=A4)
c.setTitle('vdtNext ZIP提出 QRコード')
c.setFillColorRGB(0.09, 0.42, 0.57); c.rect(0, H - 48 * mm, W, 48 * mm, stroke=0, fill=1)
c.setFillColorRGB(1, 1, 1); c.setFont('G', 34); c.drawCentredString(W / 2, H - 25 * mm, 'vdtNext 計測データの提出')
c.setFont('G', 16); c.drawCentredString(W / 2, H - 38 * mm, '集中講義 — ZIPファイル（約10MB）をスマホ・PCから提出')
size = 120 * mm
w = QrCodeWidget(url, barLevel='M'); b = w.getBounds(); d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0]); d.add(w)
renderPDF.draw(d, c, (W - size) / 2, H - 58 * mm - size)
c.setFillColorRGB(0.1, 0.17, 0.23); c.setFont('G', 12); c.drawCentredString(W / 2, H - 62 * mm - size, url)
y = H - 78 * mm - size
c.setFont('G', 15)
for line in ['① QRコードを読み取り、ブラウザで開く', '② 学籍番号・研究用ID・満年齢・計測日・文字サイズの順序を入力',
             '③ 計測アプリが作ったZIPを選び、研究利用への同意／不同意を選ぶ', '④「提出する」→ 受付番号が表示されたら完了（撮影して控える）']:
    c.drawString(28 * mm, y, line); y -= 9.5 * mm
c.setFont('G', 11); c.setFillColorRGB(0.35, 0.42, 0.47)
for line in ['GitHub等の操作・アカウント登録は不要です。提出ファイルは非公開領域に保存されます。',
             '研究利用への同意は任意です。同意しなくても提出は受け付けられ、成績には影響しません。']:
    y -= 2 * mm; c.drawCentredString(W / 2, y, line); y -= 6 * mm
c.showPage(); c.save()
print('wrote', out)
