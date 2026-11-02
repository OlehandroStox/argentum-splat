"""Lossless scene-linear training copies; calibration always uses display images."""
import shutil
import struct
import zlib
from pathlib import Path
import numpy as np
from PIL import Image


def srgb_to_linear(values):
    values=np.asarray(values,dtype=np.float32)
    return np.where(values <= .04045, values/12.92, ((values+.055)/1.055)**2.4)


def write_rgb16(path, pixels):
    a=np.asarray(pixels)
    if a.ndim!=3 or a.shape[2]!=3 or not np.all(np.isfinite(a)):
        raise ValueError('Expected finite RGB image data.')
    h,w=a.shape[:2]
    raw=np.round(np.clip(a,0,1)*65535).astype('>u2').tobytes()
    stride=w*6
    scanlines=b''.join(b'\0'+raw[y*stride:(y+1)*stride] for y in range(h))
    def chunk(name,data):
        return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+
        chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,16,2,0,0,0))+
        chunk(b'IDAT',zlib.compress(scanlines,3))+chunk(b'IEND',b''))


def linear_dataset(dataset, colmap, progress=None):
    dataset=Path(dataset)
    output=dataset.parent/'training-linear'
    (output/'images').mkdir(parents=True,exist_ok=False)
    (output/'sparse').mkdir()
    reconstruction=colmap.Reconstruction(dataset/'sparse')
    for index,image in enumerate(reconstruction.images.values()):
        with Image.open(dataset/'images'/image.name) as bitmap:
            pixels=np.asarray(bitmap.convert('RGB'),dtype=np.float32)/255.
        name=Path(image.name).stem+'.png'
        write_rgb16(output/'images'/name,srgb_to_linear(pixels))
        image.name=name
        if progress:progress('colour',None,'Preparing linear training photo %d / %d' % (index+1,reconstruction.num_reg_images()))
    reconstruction.write(output/'sparse')
    return output


def mark_ply(path, linear):
    """Persist the renderer contract in the PLY itself, not just a sidecar."""
    path=Path(path);temporary=path.with_suffix('.tagged.ply')
    with path.open('rb') as source, temporary.open('xb') as target:
        if source.readline().strip()!=b'ply':raise ValueError('Invalid trainer PLY.')
        target.write(b'ply\ncomment argentum_profile brush_classic_v1\n')
        target.write(b'comment color_space '+(b'linearRGB' if linear else b'sRGB')+b'\n')
        shutil.copyfileobj(source,target,1024*1024)
    temporary.replace(path)
