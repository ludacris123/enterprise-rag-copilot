"""Measure one mode per process on CUDA; never treat output text as a quality score.
Install backend[quantization], then run this script on your own GPU.
"""
import argparse
import gc
import json
import subprocess
import sys
import time
from pathlib import Path


def measure(args):
    import torch
    import transformers
    import bitsandbytes
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    if not torch.cuda.is_available():
        raise SystemExit('A compatible CUDA GPU is required for this benchmark')
    if torch.cuda.device_count() != 1:
        raise SystemExit('Expose exactly one GPU using CUDA_VISIBLE_DEVICES for comparable measurements')
    torch.cuda.reset_peak_memory_stats()
    start=time.perf_counter()
    tokenizer=AutoTokenizer.from_pretrained(args.model,trust_remote_code=False)
    config=None
    if args.mode=='int8':config=BitsAndBytesConfig(load_in_8bit=True)
    if args.mode=='nf4':config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16)
    kwargs={'device_map':'auto','torch_dtype':torch.float16,'trust_remote_code':False}
    if config is not None:kwargs['quantization_config']=config
    model=AutoModelForCausalLM.from_pretrained(args.model,**kwargs).eval()
    # CPU offload would make the memory/performance comparison misleading.
    if hasattr(model,'hf_device_map') and any(str(v) in ('cpu','disk') for v in model.hf_device_map.values()):
        raise SystemExit('Model does not fit entirely on GPU; choose a smaller model')
    torch.cuda.synchronize();load=time.perf_counter()-start
    input_=tokenizer(args.prompt,return_tensors='pt').to(model.device)
    with torch.inference_mode():model.generate(**input_,max_new_tokens=8,do_sample=False,pad_token_id=tokenizer.eos_token_id)
    torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
    start=time.perf_counter()
    with torch.inference_mode():out=model.generate(**input_,max_new_tokens=args.max_tokens,do_sample=False,pad_token_id=tokenizer.eos_token_id)
    torch.cuda.synchronize();elapsed=time.perf_counter()-start
    generated=out[0,input_['input_ids'].shape[1]:]
    measurement={'mode':args.mode,'load_seconds':load,'peak_memory_mb':torch.cuda.max_memory_allocated()/1024**2,
                 'inference_seconds':elapsed,'generated_tokens':len(generated),'tokens_per_second':len(generated)/elapsed,
                 'output':tokenizer.decode(generated,skip_special_tokens=True)}
    report={'model':args.model,'device':torch.cuda.get_device_name(0),'prompt':args.prompt,'measurements':[measurement],
            'library_versions':{'torch':torch.__version__,'transformers':transformers.__version__,'bitsandbytes':bitsandbytes.__version__}}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,indent=2))
    print(f'Saved {args.mode} measurements to {args.output}')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',default='Qwen/Qwen2.5-0.5B-Instruct')
    parser.add_argument('--prompt',default='Explain retrieval augmented generation in three sentences.')
    parser.add_argument('--mode',choices=['all','fp16','int8','nf4'],default='all')
    parser.add_argument('--max-tokens',type=int,default=100)
    parser.add_argument('--output',default='benchmark-output/report.json')
    args=parser.parse_args()
    if args.mode!='all':return measure(args)
    files=[]
    for mode in ['fp16','int8','nf4']:
        output=str(Path(args.output).with_suffix(f'.{mode}.json'))
        subprocess.run([sys.executable,__file__,'--model',args.model,'--prompt',args.prompt,'--mode',mode,'--max-tokens',str(args.max_tokens),'--output',output],check=True)
        files.append(Path(output))
    reports=[json.loads(p.read_text()) for p in files]
    merged={**reports[0],'measurements':[r['measurements'][0] for r in reports]}
    Path(args.output).write_text(json.dumps(merged,indent=2))
    print(f'Import {args.output} into Model lab. Also evaluate answer quality before choosing a precision mode.')

if __name__=='__main__':main()
