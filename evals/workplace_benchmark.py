"""Reproducible, offline-source workplace corpus and local paired pilot.
Both modes receive the same task; all inputs are fictional. No web, mail or paid fallback.
Mechanical checks are minimum acceptance checks, NOT an independent quality grade.
Usage: .venv/bin/python evals/workplace_benchmark.py --out DIR [--cases 1..50] [--repeats 1..3]
"""
from __future__ import annotations
import argparse, asyncio, hashlib, json, subprocess, time
from pathlib import Path
from agentteam.config.loader import DEFAULT_CONFIG_YAML, load_config_text, config_to_yaml
from agentteam.config.models import Connection
from agentteam.api.service import AppService
from agentteam.contracts import RunInputs
from agentteam.providers.openai_compat_driver import OpenAICompatDriver
from agentteam.providers.base import LLMRequest

CATEGORIES = ['research','document','code','spreadsheet','web','customer-support','marketing','analysis','planning','data-transformation']
def corpus():
    cases=[]
    for variant in range(1,6):
        company=f'架空企業{variant}'; amount=variant*100
        definitions=[
          ('research',f'A社は月額{amount}円・端末内処理、B社は月額{amount+50}円・外部送信、C社は価格不明・外部送信。',
           '比較表と、外部送信禁止の場合の選定理由をMarkdownにする。外部調査はしない。','comparison.md',['A社','B社','C社','不明','端末内',str(amount),str(amount+50)],['調査しました']),
          ('document',f'{company}のPoC。担当は田中。期限9月{10+variant}日。予算は未決定。対象は在庫照会のみ。',
           '範囲、担当、期限、未決事項を含む提案書をMarkdownにする。','proposal.md',[company,'田中',f'9月{10+variant}日','未決定','在庫照会'],['導入済み']),
          ('code','Python標準ライブラリのみ。税込額は整数の小数切り捨て。入力は0以上の整数の税抜額。税率10%。',
           'tax.pyに税込額を返すwith_tax(amount)関数、test_tax.pyに0・100・999の期待値0・110・1098のunittestを書く。','tax.py',['def with_tax','amount'],['requests','pip install']),
          ('spreadsheet',f'品目,単価,数量\nA,{amount},2\nB,{amount+10},3',
           f'金額列と合計行を追加したCSVを作る。合計は再計算する。','result.csv',[str(amount*2),str((amount+10)*3),str(amount*5+30)],[]),
          ('web',f'製品名{company}。説明はローカル解析の試作。申し込みや送信は実装しない。',
           '見出し、説明、label付きメール入力とtype=buttonの相談ボタンがある単一HTMLを作る。外部依存なし。','index.html',[company,'<label','type="button"','viewport'],['https://','<form action']),
          ('customer-support',f'{company}のお客様鈴木から返品相談。返金可否は担当者確認が必要。注文番号は不明。',
           '確認前に返金を約束せず、注文番号を依頼する返信の下書きを作る。','reply.md',['鈴木','注文番号','確認','下書き'],['返金しました','返金済み']),
          ('marketing',f'{company}はローカルでメモを整理する試作。料金・速度・導入社数は未公表。',
           '提供情報だけで日本語の投稿原稿を1つ作る。本文200文字以内。未投稿と明記。','post.md',[company,'メモ','未投稿'],['無料','倍','社導入']),
          ('analysis',f'四半期売上:第1期{amount}万円、第2期{amount*2}万円、第3期{amount*3}万円。費用データなし。',
           '合計売上と第1期から第3期への増加率を計算。利益は不明と書く。','analysis.md',[str(amount*6),'200%','利益'],['利益率は']),
          ('planning',f'{company}の作業。要件整理30分→資料作成45分→レビュー15分。午前10時開始。',
           '依存順を守り、重複のない時刻表をMarkdownで作る。','plan.md',['10:00','10:30','11:15','11:30'],[]),
          ('data-transformation',f'id,name,active\n{variant},田中,true\n{variant+10},佐藤,false',
           'CSVをJSON配列へ変換。idは整数、activeはboolean。並び順を保持する。','result.json',['田中','佐藤','true','false'],['"true"','"false"']),
        ]
        for category,source,goal,path,required,forbidden in definitions:
            cases.append({'id':f'{category}-{variant}','category':category,'source':source,
              'goal':goal,'artifact':path,'required':required,'forbidden':forbidden,
              'humanRubric':['source fidelity','correctness','usability','unsupported claims'],
              'executionStatus':'not_run'})
    return cases

def acceptance(case,files):
    text=files.get(case['artifact'],'')
    if not isinstance(text, str): text=''
    compact=text.replace(' ','').replace('　','')
    checks={'artifact_present':bool(text),'required_terms':all(s.replace(' ','') in compact for s in case['required']),
      'no_forbidden_claims':not any(s in text for s in case['forbidden'])}
    if case['category']=='data-transformation':
        try:
            value=json.loads(text);checks['typed_rows']=len(value)==2 and all(type(r['id']) is int and type(r['active']) is bool for r in value)
        except (ValueError,TypeError,KeyError): checks['typed_rows']=False
    return checks

async def main(args):
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'results.json').exists():raise ValueError('Use a fresh output directory')
    cases=corpus();(out/'corpus.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
    model='qwen2.5:7b';driver=OpenAICompatDriver('local-benchmark',None,'http://127.0.0.1:11434/v1',driver='ollama',timeout=120)
    cfg=load_config_text(DEFAULT_CONFIG_YAML)
    cfg.connections=[Connection(id='local-benchmark',driver='ollama',base_url='http://127.0.0.1:11434/v1')]
    cfg.defaults.connection_id='local-benchmark';cfg.defaults.model=model
    cfg.limits.max_active_workers=1;cfg.limits.max_model_calls=25;cfg.limits.max_tool_calls=50
    # The configuration schema requires a positive ledger ceiling. Only the
    # loopback Ollama connection exists; no paid provider can be selected.
    cfg.limits.max_output_tokens=3000;cfg.limits.timeout_seconds=240;cfg.limits.budget_usd=1
    cfg.limits.max_replans=0
    for a in cfg.agents:a.tools=[t for t in a.tools if t not in ['web_fetch','web_search','sandbox_run']]
    rows=[]
    meta={'schema':'agentteam.workplace-benchmark.v1','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
      'sourceWorkingTreeDirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True)),
      'harnessSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'configSha256':hashlib.sha256(config_to_yaml(cfg).encode()).hexdigest(),
      'model':model,'plannedCases':50,'requestedCases':args.cases,'requestedRepeats':args.repeats,
      'scope':'paired local pilot; mechanical checks only; human rubric not scored; no claim of superiority',
      'costExcludes':['hardware','electricity'],'externalApiCostUsd':0,'results':rows}
    def save(): (out/'results.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    try:
        probe=await driver.probe(model);meta['probe']=probe.__dict__;meta['probe']['usage']=probe.usage.__dict__
        if not probe.ok:save();print('Capability probe failed; no benchmark runs started.');return
        cfg.connections[0].capability_check='passed'
        for case in cases[:args.cases]:
            for repeat in range(1,args.repeats+1):
                prompt=f"{case['goal']} 成果物は{case['artifact']}として保存する。外部送信・操作・調査は禁止。提供された情報だけを使う。"
                for mode in ['single','team']:
                    started=time.monotonic();folder=out/f"{case['id']}-{repeat}-{mode}";folder.mkdir()
                    files={};status='failed';usage={};error=None;events=[]
                    if mode=='single':
                        try:
                            response=await driver.complete(LLMRequest(model=model,system='与えられた業務を実行する。JSONだけで回答する。',
                              messages=[{'role':'user','content':f'{prompt}\n資料:\n{case["source"]}\n成果物を {{"files":[{{"path":"...","content":"..."}}]}} の形式で返す。'}],
                              max_tokens=3000,json_schema={'type':'object','properties':{'files':{'type':'array','items':{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']}}},'required':['files']}))
                            usage=response.usage.__dict__;parsed=json.loads(response.text)
                            files={f['path']:f['content'] for f in parsed['files']};status='completed' if response.stop_reason!='max_tokens' else 'failed'
                        except Exception as e:error=f'{type(e).__name__}: {str(e)[:200]}'
                    else:
                        svc=None
                        try:
                            svc=await AppService(folder/'state',config_yaml=config_to_yaml(cfg),approval_wait_seconds=1).start()
                            run,problems=await svc.manager.create_run(prompt,RunInputs(text=case['source'],urls=[]),budget_usd=1)
                            if problems:error=str(problems)
                            else:
                                svc.manager.start(run.run_id);run=await svc.manager.wait(run.run_id)
                                status=str(run.status);usage=run.usage.model_dump()
                                for artifact in await svc.artifacts.list(run.run_id):files[artifact.artifact_id]=svc.artifacts.read_text(artifact)
                                events=[e.model_dump(mode='json') for e in await svc.events.list(run.run_id)]
                        except Exception as e:error=f'{type(e).__name__}: {str(e)[:200]}'
                        finally:
                            if svc is not None: await svc.stop()
                    (folder/'artifacts.json').write_text(json.dumps(files,ensure_ascii=False,indent=2))
                    (folder/'events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2))
                    checks=acceptance(case,files)
                    row={'case':case['id'],'repeat':repeat,'mode':mode,'status':status,'checks':checks,
                      'minimumAcceptancePassed':all(checks.values()),'falseCompletionAtMinimumGate':status=='completed' and not all(checks.values()),
                      'durationSeconds':round(time.monotonic()-started,3),'usage':usage,'error':error,'humanInterventions':0,
                      'artifactSha256':hashlib.sha256(json.dumps(files,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
                    rows.append(row);save();print(json.dumps(row,ensure_ascii=False),flush=True)
                # Stop rather than burn hours reproducing an unqualified model.
                teams=[r for r in rows if r['mode']=='team']
                if len(teams)>=3 and all(not r['minimumAcceptancePassed'] for r in teams[-3:]):
                    meta['stoppedReason']='three consecutive team minimum-acceptance failures';save();return
    finally:await driver.aclose()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--cases',type=int,choices=range(1,51),default=1);p.add_argument('--repeats',type=int,choices=range(1,4),default=1)
    asyncio.run(main(p.parse_args()))
