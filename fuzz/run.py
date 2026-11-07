#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded differential tests of owned core APIs, with reproducible case replay."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import re
import resource
import signal
import shutil
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reference', ROOT/'tests/oracle.py')
REF = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(REF)
BOUNDARIES = (-(1 << 63), -1, 0, 1, 2, 3, 15, 16, 17, 255, 256, 257, 511, 512, 513, (1 << 63)-2, (1 << 63)-1)
MODES = ('optimized', 'debug', 'asan')
MAX_BYTES = 8388608


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(args,timeout=180):
    with tempfile.TemporaryFile() as log:
        proc=subprocess.Popen(list(map(str,args)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try: code=proc.wait(timeout=timeout)
        except BaseException:
            try: os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait(timeout=10);raise
        log.seek(0);data=log.read(262145)
        if len(data)>262144: raise RuntimeError('command log exceeds256KiB')
        if code: raise subprocess.CalledProcessError(code,args,output=data)
        return data


def identity(goose):
    expected=(ROOT/'GOOSE_REVISION').read_text().strip()
    compiler_source=goose.parent.parent
    actual=command(['git','-C',compiler_source,'rev-parse','HEAD']).decode().strip()
    if actual!=expected or command(['git','-C',compiler_source,'status','--porcelain']):
        raise ValueError('compiler source must be a clean checkout at GOOSE_REVISION')
    version=command([goose,'version']).decode().strip()
    matched=re.search(r'goose ([0-9a-f]{7,40})',version)
    if not matched or not expected.startswith(matched.group(1)): raise ValueError('compiler version disagrees with pinned source')
    backends={}
    for role,name in (('normal','gcc'),('sanitizer',os.environ.get('SANITIZER_CC','gcc'))):
        resolved=shutil.which(name)
        if not resolved: raise ValueError('missing C backend '+name)
        resolved=Path(resolved).resolve()
        backends[role]=dict(binary_sha256=sha(resolved.read_bytes()),version=command([resolved,'--version']).decode())
    names = ('terminal.goose','GOOSE_REVISION','tests/oracle.py','fuzz/driver.goose','fuzz/run.py','scripts/sanitizer-cc.sh')
    return dict(c_backends=backends,commit=command(['git','rev-parse','HEAD']).decode().strip(),
                status=command(['git','status','--porcelain']).decode(),
                source_sha256={n:sha((ROOT/n).read_bytes()) for n in names},
                compiler_sha256=sha(goose.read_bytes()), compiler_version=version, compiler_source_commit=actual,
                expected_revision=(ROOT/'GOOSE_REVISION').read_text().strip())


def corpus():
    values = [dict(op=op,color=0,live=0,final=0,columns=80,a=2 if op==1 else 0,b=1,c=12,
                   cells=[] if op==4 else [b'a',b'\\\x1b\xff'] if op==1 else [b'hello']) for op in range(5)]
    values += [dict(values[0],cells=[bytes([c])]) for c in range(256)]
    values += [dict(values[1],a=1,columns=512,cells=[b'a'*256]*256),
               dict(values[1],a=1,columns=512,cells=[b'a'*256]*255+[b'a'*257]),
               dict(values[1],a=2,columns=512,cells=[b'a'*509,b'']+[b'',b'']*255),
               dict(values[2],a=(1<<63)-1,b=(1<<63)-1,c=256,columns=512),
               dict(values[0],cells=[b'\xff'*4096]),dict(values[0],cells=[b'\xff'*4097])]
    values += [dict(values[0],color=1,a=style) for style in range(1,5)]
    values += [dict(values[4],color=policy,live=tty,final=dumb,a=no_color,columns=width)
               for policy in range(3) for tty in (0,1) for dumb in (0,1) for no_color in (0,1)
               for width in (-1,2,80,512,513)]
    return values


def mutate(rng, original):
    case = copy.deepcopy(original); choice = rng.randrange(8)
    if choice == 0: case['columns'] = rng.choice(BOUNDARIES)
    elif choice == 1: case[rng.choice(('b','c'))] = rng.choice(BOUNDARIES)
    elif choice == 2:
        case['color']=rng.randrange(3 if case['op']==4 else 2)
        case['live']=rng.randrange(2);case['final']=rng.randrange(2)
    elif choice == 3:
        case['a']=rng.randrange(5) if case['op']==0 else rng.randrange(2) if case['op']==4 else rng.choice(BOUNDARIES)
    elif case['op'] != 4:
        if choice == 4 and case['op']==1:
            case['cells']=[rng.choice((b'',b'x',b'\x1b',b'\\'))]*rng.choice((0,1,2,16,17,255,256,257,1024,1025))
        elif case['cells']:
            index=rng.randrange(len(case['cells']));data=case['cells'][index]
            if choice==5: data=bytes([rng.randrange(256)])*rng.choice((0,1,4095,4096,4097,16384,65536))
            elif choice==6: data=rng.randbytes(rng.randrange(257))
            else:
                at=rng.randrange(len(data)+1);data=data[:at]+bytes([rng.randrange(256)])+data[at+1:]
            case['cells'][index]=data[:65536]
    remaining=1048576
    for index,cell in enumerate(case['cells']):
        case['cells'][index]=cell[:min(65536,remaining)];remaining-=len(case['cells'][index])
    return case


def encode(cases):
    if not 1<=len(cases)<=32: raise ValueError('case count outside1..32')
    for v in cases:
        if set(v)!={'op','color','live','final','columns','a','b','c','cells'}: raise ValueError('invalid case fields')
        if v['op'] not in range(5) or v['live'] not in (0,1) or v['final'] not in (0,1): raise ValueError('invalid header')
        if v['color'] not in range(3 if v['op']==4 else 2): raise ValueError('invalid policy')
        if not all(isinstance(v[n],int) and -(1<<63)<=v[n]<(1<<63) for n in ('columns','a','b','c')): raise ValueError('invalid integer')
        if len(v['cells'])>1025 or any(not isinstance(c,bytes) or len(c)>65536 for c in v['cells']) or sum(map(len,v['cells']))>1048576: raise ValueError('invalid payload budget')
        if (v['op']==4 and (v['cells'] or v['a'] not in (0,1))) or (v['op'] not in (1,4) and len(v['cells'])!=1) or (v['op']==0 and v['a'] not in range(5)): raise ValueError('invalid operation parameters')
    data=bytearray()
    for v in cases:
        data.extend(struct.pack('<BBBBqqqqI',v['op'],v['color'],v['live'],v['final'],v['columns'],v['a'],v['b'],v['c'],len(v['cells'])))
        for cell in v['cells']: data.extend(struct.pack('<I',len(cell)));data.extend(cell)
    if len(cases)>32 or len(data)>MAX_BYTES: raise ValueError('batch exceeds bounds')
    return data


def expected(cases):
    data=bytearray()
    for v in cases:
        if v['op']==4:
            known=2<=v['columns']<=512
            color=v['color']==1 or (v['color']==0 and v['live'] and not v['final'] and not v['a'])
            redraw=v['live'] and not v['final'] and known
            code,out=0,bytes([bool(color),bool(redraw)])+struct.pack('<I',v['columns'] if known else 80)
        else:
            code,out=REF.reference(v['op'],v['color'],v['live'],v['final'],v['columns'],v['a'],v['b'],v['c'],v['cells'])
        data.extend(struct.pack('<BI',code,len(out)));data.extend(out)
    return data


def limits(path):
    requested={resource.RLIMIT_CPU:(5,5),resource.RLIMIT_FSIZE:(MAX_BYTES,MAX_BYTES),resource.RLIMIT_NOFILE:(32,32),resource.RLIMIT_CORE:(0,0)}
    for key,value in requested.items(): resource.setrlimit(key,value)
    effective={str(key):list(resource.getrlimit(key)) for key in requested}
    effective['RLIMIT_AS']='unrestricted: Goose data stacks and ASan reserve large virtual regions'
    path.write_text(json.dumps(effective))


def execute(binary,cases,scratch,mode):
    source=scratch/'input.bin';source.write_bytes(encode(cases));target=scratch/'actual.bin';target.unlink(missing_ok=True)
    started=time.monotonic()
    with (scratch/'stdout').open('wb') as stdout,(scratch/'stderr').open('wb') as stderr:
        proc=subprocess.Popen([str(binary),str(source),str(target)],cwd=ROOT,stdout=stdout,stderr=stderr,
                              start_new_session=True,preexec_fn=lambda:limits(scratch/'limits.json'))
        try: code=proc.wait(timeout=8)
        except BaseException:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10);raise
    stdout=(scratch/'stdout').read_bytes()[:65536]
    actual=target.read_bytes() if target.exists() and target.stat().st_size<=MAX_BYTES else b''
    wanted=expected(cases)
    category='pass'
    if code or (scratch/'stdout').stat().st_size>65536 or (scratch/'stderr').stat().st_size>65536 or stdout!=f'fuzz batch rendered: {len(cases)}\n'.encode() or (scratch/'stderr').read_bytes()!=b''.join(f'case {i}\n'.encode() for i in range(len(cases))): category='driver-or-runtime-failure'
    elif actual!=wanted: category='api-output-mismatch'
    return dict(category=category,mode=mode,exit_status=code,cases=len(cases),elapsed_seconds=time.monotonic()-started,
                input_sha256=sha(source.read_bytes()),actual_sha256=sha(actual),expected_sha256=sha(wanted))


def failure_bundle(output,scratch,cases,details):
    bundle=output/'failure';bundle.mkdir(exist_ok=True)
    for name in ('input.bin','actual.bin','stdout','stderr','limits.json'):
        if (scratch/name).exists(): (bundle/name).write_bytes((scratch/name).read_bytes())
    (bundle/'cases.json').write_text(json.dumps([dict(v,cells=[c.hex() for c in v['cells']]) for v in cases]))
    try: (bundle/'expected.bin').write_bytes(expected(cases))
    except Exception as error: (bundle/'reference-error.txt').write_text(repr(error))
    (bundle/'failure.json').write_text(json.dumps(details,indent=2)+'\n')
    (bundle/'REPLAY.txt').write_text('python3 fuzz/run.py --goose /absolute/pinned/goose --replay '+str((bundle/'cases.json').resolve())+' --output .build/replay-new\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--goose',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=600);parser.add_argument('--max-cases',type=int,default=1000000)
    parser.add_argument('--seed',type=int,default=0x6005E2);parser.add_argument('--replay',type=Path)
    args=parser.parse_args()
    if platform.system()!='Linux': parser.error('resource controls qualified only on Linux')
    if not 1<=args.seconds<=86400 or not 1<=args.max_cases<=10000000: parser.error('budget out of range')
    goose=args.goose.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    try: before=identity(goose)
    except BaseException as error:
        (output/'results.json').write_text(json.dumps(dict(cases=0,failure=dict(category='identity-rejected',exception=repr(error))),indent=2)+'\n')
        raise SystemExit('identity rejected; evidence in '+str(output))
    replay=None
    if args.replay:
        if args.replay.stat().st_size>33554432: parser.error('replay exceeds32MiB')
        replay=[dict(v,cells=[bytes.fromhex(c) for c in v['cells']]) for v in json.loads(args.replay.read_text())];encode(replay)
    flags={'optimized':['--cc','gcc','-O2'],'debug':['--cc','gcc','--debug','--no-bce'],'asan':['--standalone','--debug','--no-bce','--cc','./scripts/sanitizer-cc.sh']}
    binaries={}
    try:
        for mode in MODES:
            binary=output/('driver-'+mode)
            (output/('build-'+mode+'.log')).write_bytes(command([goose,'build','fuzz/driver.goose',*flags[mode],'-o',binary]));binaries[mode]=binary
    except BaseException as error:
        (output/'results.json').write_text(json.dumps(dict(source=before,failure=dict(category='build-or-startup-failure',mode=mode,exception=repr(error)),cases=0),indent=2)+'\n')
        if getattr(error,'output',None): (output/'build-failure.log').write_bytes(error.output)
        raise SystemExit('driver build failed; evidence in '+str(output))
    hashes={m:sha(p.read_bytes()) for m,p in binaries.items()}
    rng=random.Random(args.seed);seeds=corpus();total=batches=0;per_mode=dict.fromkeys(MODES,0);per_target=dict.fromkeys(range(5),0)
    started=time.monotonic();last_cases=[];details={};failure=None
    with tempfile.TemporaryDirectory(prefix='batch-',dir=output) as raw:
        scratch=Path(raw)
        try:
            while total<args.max_cases and (batches==0 or time.monotonic()-started<args.seconds):
                if replay is not None: cases=replay
                elif total<len(seeds): cases=copy.deepcopy(seeds[total:min(total+16,args.max_cases,len(seeds))])
                else:
                    cases=[mutate(rng,mutate(rng,rng.choice(seeds))) for _ in range(min(16,args.max_cases-total))]
                    if len(cases)>=5: cases[:5]=[mutate(rng,v) for v in seeds[:5]]
                last_cases=cases;encode(cases)
                for mode,binary in binaries.items():
                    details=dict(category='driver-or-timeout-failure',mode=mode,cases=len(cases))
                    details=execute(binary,cases,scratch,mode)
                    if details['category']!='pass': raise RuntimeError(details['category'])
                    per_mode[mode]+=len(cases)
                    with (output/'batches.jsonl').open('a') as stream: stream.write(json.dumps(dict(batch=batches,**details))+'\n')
                for v in cases: per_target[v['op']]+=1
                total+=len(cases);batches+=1
                if replay is not None: break
        except BaseException as error:
            failure=dict(details,exception=repr(error));failure['category']=failure.get('category') if failure.get('category')!='pass' else 'campaign-or-timeout-failure'
            failure_bundle(output,scratch,last_cases,failure)
        effective=json.loads((scratch/'limits.json').read_text()) if (scratch/'limits.json').exists() else {}
    identity_error=None
    try: drift=identity(goose)!=before or any(sha(p.read_bytes())!=hashes[m] for m,p in binaries.items())
    except BaseException as error: drift=True;identity_error=repr(error)
    report=dict(source=before,c_compilers=before['c_backends'],binaries_sha256=hashes,build_flags=flags,seed=args.seed,requested_seconds=args.seconds,seed_case_count=len(seeds),stop_reason="failure" if failure else "identity-drift" if drift else "replay" if replay is not None else "case-budget" if total>=args.max_cases else "duration",
                elapsed_seconds=time.monotonic()-started,max_cases=args.max_cases,cases=total,batches=batches,
                per_mode_cases=per_mode,per_target_cases=per_target,effective_child_limits=effective,
                platform=platform.platform(),memory_isolation='No hard RSS or virtual-memory containment qualified',
                scope='Mutation-based differential core API testing; not coverage-guided; adapter behavior tested separately',
                failure=failure,identity_drift=drift,identity_error=identity_error)
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    if failure or drift or not total or any(not n for n in per_mode.values()) or (replay is None and any(not n for n in per_target.values())): raise SystemExit('campaign failed; evidence in '+str(output))
    print(f'Campaign passed: {total} cases x3 modes, {batches} batches, {report["elapsed_seconds"]:.1f}s')


if __name__=='__main__': main()
