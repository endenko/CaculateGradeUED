import os,sys,json,glob,time
from paddleocr import TextDetection
from PIL import Image
from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg
det=TextDetection(model_name='PP-OCRv6_medium_det',engine_config={'run_mode':'paddle'})
c=Cfg.load_config_from_name('vgg_transformer');c['device']='cpu';c['predictor']['beamsearch']=False;p=Predictor(c)
out=json.load(open('/tmp/ctdt/ocr2.json')) if os.path.exists('/tmp/ctdt/ocr2.json') else {}
for pth in sorted(glob.glob('/tmp/ctdt/img/*.png')):
    k=os.path.basename(pth);t=time.time()
    if k in out: continue
    r=list(det.predict(pth))[0]
    polys=r['dt_polys']
    im=Image.open(pth).convert('RGB');boxes=[];crops=[]
    for q in polys:
        xs=[v[0] for v in q];ys=[v[1] for v in q]
        b=[min(xs),min(ys),max(xs),max(ys)]
        if b[3]-b[1]>90 or b[2]-b[0]>0.8*im.size[0]: continue
        boxes.append([float(v) for v in b])
        crops.append(im.crop((b[0]-3,b[1]-3,b[2]+3,b[3]+3)))
    texts=p.predict_batch(crops) if crops else []
    out[k]=[{'t':t2,'b':b} for t2,b in zip(texts,boxes)]
    json.dump(out,open('/tmp/ctdt/ocr2.json','w'),ensure_ascii=False)
    print(k,len(out[k]),round(time.time()-t,1),flush=True)
