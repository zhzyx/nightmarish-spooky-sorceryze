"""Explicit reviewed color mask/crop for generated product-photo derivatives.

Does not synthesize garment geometry or overwrite the original AI image.
"""
import argparse, hashlib, io, json
from pathlib import Path
from PIL import Image

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source'); p.add_argument('output'); p.add_argument('--mode',choices=['blue','brown','padding'],required=True)
    p.add_argument('--bottom',type=int,default=512); p.add_argument('--top',type=int,default=0)
    a=p.parse_args(); src=Path(a.source).resolve(); dst=Path(a.output).resolve()
    outputs=[dst,dst.with_suffix('.mask.png'),dst.with_suffix('.prepare.json')]
    if len(set(outputs+[src]))!=4: raise ValueError('Source and all derivative paths must be distinct')
    for target in outputs:
        if target.exists(): raise FileExistsError(target)
    original=src.read_bytes(); source_sha=hashlib.sha256(original).hexdigest()
    im=Image.open(io.BytesIO(original)).convert('RGB'); mask=Image.new('L',im.size)
    for y in range(im.height):
        for x in range(im.width):
            r,g,b=im.getpixel((x,y))
            keep=a.top<=y<a.bottom and (a.mode=='padding' or a.mode=='blue' and b>r*1.12 and b>g*1.02 or a.mode=='brown' and r>b*1.15 and r>g*1.05)
            if keep: mask.putpixel((x,y),255)
    box=mask.getbbox()
    if box is None: raise ValueError('empty garment selection')
    selected=Image.new('RGB',im.size,'white'); selected.paste(im,mask=mask)
    selected=selected.crop(box); selected.thumbnail((410,410))
    result=Image.new('RGB',(512,512),'white'); result.paste(selected,((512-selected.width)//2,(512-selected.height)//2))
    encoded=[]
    for bitmap in (result,mask):
        buffer=io.BytesIO(); bitmap.save(buffer,format='PNG'); encoded.append(buffer.getvalue())
    receipt=dict(operation='reviewed_color_mask_crop_padding',source_sha256=source_sha,output_sha256=hashlib.sha256(encoded[0]).hexdigest(),mask_sha256=hashlib.sha256(encoded[1]).hexdigest(),mode=a.mode,top=a.top,bottom=a.bottom,bounds=box,geometry_generated=False)
    encoded.append(json.dumps(receipt,indent=2).encode('utf-8'))
    # Each publication uses atomic no-replace hardlink, including sidecars.
    from extensions import publish_new
    class BytesAdapter:
        def __init__(self,data): self.data=data
        def encode(self,manifest): return self.data
    for target,data in zip(outputs,encoded): publish_new(BytesAdapter(data),{'schema_version':1,'artifacts':[]},target)

if __name__=='__main__': main()
