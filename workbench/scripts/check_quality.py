"""Small deterministic retrieval/safety regression gate. Live evaluation is opt-in."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://localhost:8000')
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--dataset',required=True)
    parser.add_argument('--provider',choices=['offline','groq','openai','local'],default='offline')
    parser.add_argument('--min-pass-rate',type=float,default=1.0)
    parser.add_argument('--output',default='evaluation-report.json')
    args=parser.parse_args()
    token=os.environ.get('WORKBENCH_ACCESS_TOKEN')
    if not token:raise SystemExit('Set WORKBENCH_ACCESS_TOKEN; never put tokens in command arguments')
    with httpx.Client(base_url=args.url,headers={'Authorization':f'Bearer {token}'},timeout=30) as client:
        response=client.post(f'/api/w/{args.workspace}/evaluations',json={'dataset_id':args.dataset,'provider':args.provider})
        response.raise_for_status();job=response.json()
        deadline=time.time()+240
        while job['status'] in ['queued','running'] and time.time()<deadline:
            time.sleep(2)
            response=client.get(f'/api/w/{args.workspace}/jobs/{job["id"]}');response.raise_for_status();job=response.json()
    Path(args.output).write_text(json.dumps(job,indent=2))
    if job['status']!='succeeded':raise SystemExit(f'Evaluation did not complete: {job["status"]}')
    rate=job['result']['summary']['pass_rate']
    print(f'Pass rate: {rate:.2%}')
    if rate<args.min_pass_rate:raise SystemExit(1)

if __name__=='__main__':main()
