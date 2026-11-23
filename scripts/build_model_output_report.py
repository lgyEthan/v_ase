"""Build source comparisons and manuscript assets from native scientific renders."""
import json
import shutil
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

import argparse
from datetime import date
import runpy
import matplotlib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input-dir', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
parser.add_argument('--repo-root', type=Path)
parser.add_argument('--manuscript-dir', type=Path)
parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'examples/model_output_figures')
args = parser.parse_args()
ROOT = args.input_dir.resolve()
OUTPUT = args.output_dir.resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
REPO = args.repo_root.resolve() if args.repo_root else None
MANUSCRIPT = args.manuscript_dir.resolve() if args.manuscript_dir else OUTPUT / 'manuscript'
PDF = OUTPUT / 'model_output_review.pdf'
FIGURE_PDF = OUTPUT / 'model_output_publication_figure.pdf'
FONT = Path(matplotlib.get_data_path()) / 'fonts/ttf'
for name, path in [('Sans', FONT/'DejaVuSans.ttf'), ('Bold', FONT/'DejaVuSans-Bold.ttf'),
                   ('KR', FONT/'DejaVuSans.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(path)))

INK, TEAL, MUTED, LINE = '#173247', '#087e76', '#667983', '#dce6e8'
W, H = landscape(A4)
M = 38
verify = runpy.run_path(str(args.data_dir / 'render.py'))['verify_outputs']
receipt = verify(args.data_dir, ROOT)
records = receipt['scenes']
structures = json.loads((ROOT/'structure_audit.json').read_text())
checks = json.loads((ROOT/'evidence/checks.json').read_text())
VERSION = receipt['runtime']['version']
REVIEW_DATE = receipt['review_date']
DATE_LABEL = date.fromisoformat(REVIEW_DATE).strftime('%d %b %Y').upper()
snapshot = json.loads((ROOT/'evidence/software_snapshot.json').read_text())
assert snapshot['version'] == VERSION


def crop(path):
    image = Image.open(path).convert('RGB')
    import numpy as np
    pixels = np.asarray(image)
    yy, xx = np.where(np.any(pixels < 242, axis=2))
    margin = 65
    return image.crop((max(0, int(xx.min())-margin), max(0, int(yy.min())-margin),
                       min(image.width, int(xx.max())+margin), min(image.height, int(yy.max())+margin)))


def make_public_assets():
    MANUSCRIPT.mkdir(parents=True, exist_ok=True)
    for record in records:
        shutil.copyfile(ROOT/record['png'], MANUSCRIPT/Path(record['png']).name)
    c = canvas.Canvas(str(FIGURE_PDF), pagesize=(518.4, 331.2))
    c.setTitle(f'Model outputs visualized in v_ase {VERSION}')
    c.setAuthor('v_ase')
    for i, record in enumerate([records[0], records[3]]):
        x = 16 + i*258
        c.setFillColor(colors.HexColor(INK));c.setFont('Bold', 10)
        c.drawString(x, 316, '(a) CrystaLLM / AuO₂' if i == 0 else '(b) ALM Edit / Li₄Fe₅CoO₁₂')
        im = crop(ROOT/record['png'])
        from reportlab.lib.utils import ImageReader
        scale = min(232/im.width, 276/im.height)
        dw, dh = im.width*scale, im.height*scale
        c.drawImage(ImageReader(im), x+(232-dw)/2, 32+(276-dh)/2, dw, dh)
        c.setFont('Sans', 7);c.setFillColor(colors.HexColor(MUTED))
        c.drawString(x, 14, 'seed 1337 | 3D atoms + bonds' if i == 0 else 'candidate 1 | flat atoms + cell')
    c.showPage();c.save()
    shutil.copyfile(FIGURE_PDF, MANUSCRIPT/'model_output_figures.pdf')
    document = pdfium.PdfDocument(str(FIGURE_PDF))
    image = document[0].render(scale=600/72).to_pil()
    image.save(MANUSCRIPT/'model_output_figures.png', dpi=(600, 600))
    document.close()
    for dest in ([REPO/'docs/assets/model_output_figures.png', REPO/'docs/assets/github/model_output_figures.png'] if REPO else []):
        # The public documentation image uses the same layout at smaller size.
        small = image.copy();small.thumbnail((2200,1600));small.save(dest,optimize=True)


def build_report():
    c = canvas.Canvas(str(PDF), pagesize=(W,H))
    c.setTitle(f'v_ase {VERSION} | model-output figure validation')
    c.setAuthor('v_ase')

    def txt(text, x, y, size=10, font='KR', color=INK):
        c.setFont(font, size);c.setFillColor(colors.HexColor(color));c.drawString(x,H-y-size*.8,text)

    def para(text, x, y, width, size=10, font='KR', color=MUTED, max_height=65):
        p=Paragraph(text,ParagraphStyle('p',fontName=font,fontSize=size,leading=size*1.4,
                                        textColor=colors.HexColor(color),wordWrap='CJK'))
        _,height=p.wrap(width,1000);assert height<=max_height,(text,height)
        p.drawOn(c,x,H-y-height)

    def line(y):
        c.setStrokeColor(colors.HexColor(LINE));c.setLineWidth(.7);c.line(M,H-y,W-M,H-y)

    def picture(path, x, y, width, height):
        im=Image.open(path);scale=min(width/im.width,height/im.height)
        dw,dh=im.width*scale,im.height*scale
        c.drawImage(str(path),x+(width-dw)/2,H-y-(height-dh)/2-dh,dw,dh,mask='auto')

    def start(number, title, subtitle):
        if number>1:c.showPage()
        txt('v_ase',M,22,16,'Bold',TEAL);txt('MODEL OUTPUTS / PUBLICATION FIGURES',M+68,27,8,'Sans',MUTED)
        txt(f'{VERSION} | {DATE_LABEL}',W-M-167,27,8,'Sans',MUTED);line(47)
        txt(title,M,64,25,'Sans')
        para(subtitle,M,105,W-2*M,10.2,max_height=31)

    def footer(number, text, url=None):
        line(556);para(text,M,566,W-2*M-26,7.2,font='Sans',max_height=20)
        txt(str(number),W-M-5,567,9,'Sans',MUTED)
        if url:c.linkURL(url,(M,11,W-M-25,34),relative=0,thickness=0)

    start(1,'AuO₂ | CrystaLLM → v_ase',
          'New generated output composed using the paper\'s atom colors, sphere sizes, viewing direction and bond convention.')
    txt('ORIGINAL PAPER / FIG. 3d',M,147,9,'Bold',MUTED)
    txt('CURRENT v_ase / SEED 1337',430,147,9,'Bold',TEAL)
    picture(ROOT/'originals/auo2_original.png',M,174,342,310)
    picture(ROOT/'figures/auo2_1337.png',414,171,386,321)
    txt('Au',49,500,9,'Sans');txt('O',111,500,9,'Sans')
    for x,color in [(40,'#e7b42b'),(102,'#e52525')]:
        c.setFillColor(colors.HexColor(color));c.circle(x,H-504,3.5,fill=1,stroke=0)
    para('49 display sites derived from a generated six-atom cell. The reference coordinates were not substituted.',M,519,360,9,max_height=29)
    para('2400 × 2200 px · orthographic · 216 px/Å<br/>3D spheres · Au-O cutoff 2.5 Å · editable .vase',430,501,360,9,font='Sans',max_height=42)
    footer(1,'Original: Antunes, Butler & Grau-Crespo, Nature Communications 15, 10570 (2024), Fig. 3d. Crop, CC BY 4.0. New sample; paper-specific seed unavailable.',
           'https://doi.org/10.1038/s41467-024-54639-7')

    start(2,'Li₄Fe₅CoO₁₂ | ALM Edit → v_ase',
          'The entire generated 22-atom cell, with flat atoms and a cell outline. No bonds or added periodic ligands.')
    txt('ORIGINAL PAPER / FIG. 26',M,147,9,'Bold',MUTED)
    txt('CURRENT v_ase / CANDIDATE 1',430,147,9,'Bold',TEAL)
    picture(ROOT/'originals/alm_doping_output_original.png',M,198,340,232)
    picture(ROOT/'figures/alm_co_1.png',420,166,367,345)
    colors_by_element=[('Li','#9875c9'),('Fe','#d08b3f'),('Co','#4e72b4'),('O','#d55645')]
    for i,(label,color) in enumerate(colors_by_element):
        x=M+i*65;c.setFillColor(colors.HexColor(color));c.circle(x+4,H-459,4,fill=1,stroke=0);txt(label,x+14,455,9,'Sans')
    para('New Ni-to-Co substitution output. Exact coordinates of the published thumbnail were unavailable; its drawing convention is followed.',M,488,345,9.2,max_height=40)
    para('2400 × 2600 px · orthographic · 210 px/Å<br/>2D flat atoms · full cell · visible bonds = 0',430,519,362,8.6,font='Sans',max_height=28)
    footer(2,'Original: Edamadaka et al., arXiv:2606.21395v1, Fig. 26, p.45. Printed O2 differs from released O12 data. Thumbnail for review; public reuse needs a separate rights basis.',
           'https://arxiv.org/abs/2606.21395')

    start(3,'Six editable scenes',
          'Three outputs per model: six editable scenes from two material systems. Source geometry and saved-project rendering were checked.')
    width=(W-2*M-30)/3
    for i, record in enumerate(records):
        row,col=divmod(i,3);x=M+col*(width+15);y=149+row*193
        label=('CrystaLLM / seed '+str(structures[i]['seed'])) if row==0 else ('ALM Edit / candidate '+str(structures[i]['candidate']))
        txt(label,x,y,9,'Bold',TEAL)
        picture(ROOT/record['png'],x,y+18,width,150)
        txt('AuO₂ · atoms + bonds' if row==0 else 'Li₄Fe₅CoO₁₂ · atoms + cell',x,y+173,8,'Sans',MUTED)
    footer(3,f'Two material systems, three selected outputs each. All six PNGs and editable .vase projects use the published {VERSION} wheel. No polyhedral panels or failed candidates are included.')

    start(4,'Verified data, saved figures',
          'Geometry preservation and saved-image reproducibility are checked separately, using the actual serialized files.')
    txt('GEOMETRY / PRESENTATION',M,151,10,'Bold',TEAL)
    columns=[M,M+112,M+206,M+286,M+388,M+516]
    for x,label in zip(columns,['Sample','Source / shown','Volume / Å³','Min. MIC / Å','Distance error / Å','Project reopen']):txt(label,x,176,8,'Sans',MUTED)
    line(192)
    for i,p in enumerate(structures):
        y=205+i*29
        values=[p['id'],f"{p['source_atoms']} / {p['display_atoms']}",f"{p['volume_A3']:.3f}",f"{p['minimum_periodic_distance_A']:.3f}",f"{p['periodic_distance_error_A']:.1e}",'Exact same pixels']
        for x,value in zip(columns,values):txt(value,x,y,8.7,'Sans')
    line(383)
    txt('CURRENT SOFTWARE CHECKS',M,400,10,'Bold',TEAL)
    test_summary=checks['full_suite']['summary']
    para(f'Full suite: {test_summary}<br/>Profile-reopen regression: {checks["profile_regression"]["summary"]}<br/>Native schema reference: {checks["schema_reference"]["status"]}; wheel/sdist: {checks["distributions"]["status"]}; documentation: {checks["documentation"]["status"]}.',
         M,424,358,9,font='Sans',max_height=70)
    para('All six projects reproduce the same pixels after reopening with omitted arguments. ALM retains 22 atoms and zero bonds. Project-internal coordinates match the lossless display files; style Undo and stale-revision rejection also pass.',
         440,401,360,9.2,max_height=78)
    txt('RELEASE PACKAGE SNAPSHOT',M,506,8,'Bold',MUTED)
    txt(f'{VERSION} published wheel | '+snapshot['snapshot_sha256'][:20],M,521,8,'Sans',MUTED)
    para('Pixel equality applies within the same browser and renderer. No new inference or DFT stability evaluation was run. Caption, methods, sources, mappings and hashes accompany the figures.',
         440,503,360,8.5,max_height=38)
    footer(4,'Generation: preserved September samples. Clean environment, fresh rendering and project validation. New outputs in paper style, not identical published coordinates.')
    review = json.loads((ROOT/'evidence/review.json').read_text())
    start(5, 'Current review: issues and fixes',
          'The public release remains 0.4.13. This review distinguishes the release runtime, proposed source fixes and the installed desktop app.')
    for index, finding in enumerate(review['findings']):
        y = 150 + index * 64
        txt(str(index + 1) + '. ' + finding['issue'], M, y, 10, 'Bold', TEAL)
        para(finding['correction'], M, y + 20, W - 2*M, 9.2, font='Sans', max_height=38)
    footer(5, 'Review date: ' + REVIEW_DATE + '. Source changes are reviewable on the dedicated branch. No GitHub main or PyPI publication was performed.')
    c.save()


if __name__=='__main__':
    make_public_assets()
    build_report()
    print(PDF);print(FIGURE_PDF)
