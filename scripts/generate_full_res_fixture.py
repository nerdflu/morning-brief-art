"""Generate a 1536x1024 high-resolution line-art fixture to test the publishing pipeline."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import io, base64
w,h=1536,1024
im=Image.new("RGB",(w,h),"white")
d=ImageDraw.Draw(im)
# Rainy coastal window, headland, ocean and a tiny imaginary character.
d.rounded_rectangle((85,65,1450,945),radius=25,outline="black",width=20)
d.line((105,490,1430,490),fill="black",width=15)
d.line((800,85,800,930),fill="black",width=14)
d.arc((810,420,1490,900),180,315,fill="black",width=18)
d.line([(830,740),(970,680),(1100,670),(1240,595),(1430,575)],fill="black",width=16,joint="curve")
for y in [785,830,875]:
    d.arc((900,y,1410,y+70),180,345,fill="black",width=8)
for x in range(150,750,90):
    for y in range(150,450,95):
        d.line((x,y,x-28,y+55),fill="black",width=9)
d.ellipse((300,620,490,810),outline="black",width=16)
d.ellipse((348,695,365,712),fill="black")
d.ellipse((420,695,437,712),fill="black")
d.arc((358,722,426,767),5,170,fill="black",width=9)
d.line((395,620,395,570),fill="black",width=13)
d.ellipse((355,540,398,582),outline="black",width=12)
out=Path("incoming/2026-10-22-full-resolution-fixture.b64")
out.parent.mkdir(exist_ok=True)
buf=io.BytesIO()
im.save(buf,format="PNG",optimize=True)
out.write_text(base64.b64encode(buf.getvalue()).decode())
print("Source dimensions:",im.size,"bytes:",len(buf.getvalue()))

# Trigger full-resolution integration test.
