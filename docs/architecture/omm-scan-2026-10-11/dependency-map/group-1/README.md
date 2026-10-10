# dependency-map/group-1

[解析トップへ戻る](../../README.md)

このグループは表示用の区切りです。独立した実行モジュールではありません。


```mermaid
graph TD
    n-frontend-src-main-tsx-d34671["main.tsx\nfrontend/src/main.tsx"]
    n-backend-agentteam-api-app-py-880fa2["app.py\nbackend/agentteam/api/app.py"]
    n-backend-agentteam-security-server-py-3b0154["server.py\nbackend/agentteam/security/server.py"]
    n-backend-agentteam-cli-py-3dd889["cli.py\nbackend/agentteam/cli.py"]
    n-frontend-src-app-tsx-b9c538["App.tsx\nfrontend/src/App.tsx"]
    n-backend-agentteam-contracts-py-c82b22["contracts.py\nbackend/agentteam/contracts.py"]
    n-backend-agentteam-ids-py-07f43f["ids.py\nbackend/agentteam/ids.py"]
    n-backend-agentteam-projections-views-py-dd7796["views.py\nbackend/agentteam/projections/views.py"]
```

## 要素の説明

### n-backend-agentteam-api-app-py-880fa2

確認済みファイル: `backend/agentteam/api/app.py`

解析: Python AST。静的なimport／export参照です。関数の実行順序やHTTP通信は表していません。

宣言: `CreateRunBody`, `PatchAgentBody`, `CreateAgentBody`, `PutConnectionBody`, `PutLimitsBody`, `ResolveApprovalBody`, `ForkBody`, `AdoptArtifactBody`, `InstructionBody`, `LoginBody`, `GrantBody`, `create_app`

- `__future__` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `asyncio` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `difflib` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `io` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `json` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `secrets` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `ipaddress` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `shutil` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `re` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `zipfile` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `urllib.parse` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `contextlib` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `pathlib` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `typing` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `fastapi` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `fastapi.responses` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `fastapi.staticfiles` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `pydantic` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `sse_starlette.sse` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `__version__` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `config.loader` → `backend/agentteam/config/loader.py`（一覧確認・内容未読）
- `config.models` → `backend/agentteam/config/models.py`（一覧確認・内容未読）
- `contracts` → `backend/agentteam/contracts.py`（内容確認済み）
- `ids` → `backend/agentteam/ids.py`（内容確認済み）
- `projections.views` → `backend/agentteam/projections/views.py`（内容確認済み）
- `providers.registry` → `backend/agentteam/providers/registry.py`（内容確認済み）
- `service` → `backend/agentteam/api/service.py`（一覧確認・内容未読）
- `security.accounts` → `backend/agentteam/security/accounts.py`（一覧確認・内容未読）
- `security.server` → `backend/agentteam/security/server.py`（内容確認済み）
- `store.job_store` → `backend/agentteam/store/job_store.py`（一覧確認・内容未読）
- `runtime.sandbox` → `backend/agentteam/runtime/sandbox.py`（一覧確認・内容未読）

[詳細な図と説明を見る](n-backend-agentteam-api-app-py-880fa2/README.md)

### n-backend-agentteam-cli-py-3dd889

確認済みファイル: `backend/agentteam/cli.py`

解析: Python AST。静的なimport／export参照です。関数の実行順序やHTTP通信は表していません。

宣言: `main`, `_probe_hint`, `_probe`, `_run`, `_quickstart`

- `__future__` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `argparse` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `asyncio` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `json` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `sys` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `pathlib` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `api.service` → `backend/agentteam/api/service.py`（一覧確認・内容未読）
- `config.loader` → `backend/agentteam/config/loader.py`（一覧確認・内容未読）
- `contracts` → `backend/agentteam/contracts.py`（内容確認済み）
- `providers.registry` → `backend/agentteam/providers/registry.py`（内容確認済み）
- `shutil` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `threading` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `webbrowser` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `uvicorn` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `api.app` → `backend/agentteam/api/app.py`（内容確認済み）
- `time` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `operations.observer` → `backend/agentteam/operations/observer.py`（一覧確認・内容未読）
- `operations.encrypted_backup` → `backend/agentteam/operations/encrypted_backup.py`（一覧確認・内容未読）
- `operations.retention` → `backend/agentteam/operations/retention.py`（一覧確認・内容未読）
- `security.accounts` → `backend/agentteam/security/accounts.py`（一覧確認・内容未読）
- `operations.backup` → `backend/agentteam/operations/backup.py`（一覧確認・内容未読）
- `providers.base` → `backend/agentteam/providers/base.py`（一覧確認・内容未読）

[詳細な図と説明を見る](n-backend-agentteam-cli-py-3dd889/README.md)

### n-backend-agentteam-contracts-py-c82b22

確認済みファイル: `backend/agentteam/contracts.py`

解析: Python AST。静的なimport／export参照です。関数の実行順序やHTTP通信は表していません。

宣言: `is_readiness_assessment`, `task_id_problem`, `ArtifactRef`, `AcceptanceCriterion`, `TaskSpec`, `TeamPlan`, `TaskStatus`, `RunStatus`, `EventType`, `Event`, `Message`, `ArtifactManifest`, `ApprovalStatus`, `Approval`, `ReviewResult`, `Review`, `TaskResult`, `Usage`, `TaskState`, `DeliveryRequirement`, `RunInputs`, `Run`

- `__future__` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `enum` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `json` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `re` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `pathlib` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `typing` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `pydantic` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定

[詳細な図と説明を見る](n-backend-agentteam-contracts-py-c82b22/README.md)

### n-backend-agentteam-ids-py-07f43f

確認済みファイル: `backend/agentteam/ids.py`

解析: Python AST。静的なimport／export参照です。関数の実行順序やHTTP通信は表していません。

宣言: `now_utc`, `now_iso`, `new_id`

- `__future__` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `secrets` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `time` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `datetime` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定

[詳細な図と説明を見る](n-backend-agentteam-ids-py-07f43f/README.md)

### n-backend-agentteam-projections-views-py-dd7796

確認済みファイル: `backend/agentteam/projections/views.py`

解析: Python AST。静的なimport／export参照です。関数の実行順序やHTTP通信は表していません。

宣言: `chat_view`, `timeline_view`, `artifact_review_ledger`, `evidence_view`, `_count`

- `__future__` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `typing` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `contracts` → `backend/agentteam/contracts.py`（内容確認済み）

[詳細な図と説明を見る](n-backend-agentteam-projections-views-py-dd7796/README.md)

### n-backend-agentteam-security-server-py-3b0154

確認済みファイル: `backend/agentteam/security/server.py`

解析: Python AST。静的なimport／export参照です。関数の実行順序やHTTP通信は表していません。

宣言: `ServerAccess`

- `__future__` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `json` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `logging` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `secrets` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `time` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `pathlib` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `fastapi` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `accounts` → `backend/agentteam/security/accounts.py`（一覧確認・内容未読）
- `oidc` → `backend/agentteam/security/oidc.py`（一覧確認・内容未読）

[詳細な図と説明を見る](n-backend-agentteam-security-server-py-3b0154/README.md)

### n-frontend-src-app-tsx-b9c538

確認済みファイル: `frontend/src/App.tsx`

解析: 字句抽出。静的なimport／export参照です。関数の実行順序やHTTP通信は表していません。

宣言: `App`, `Workspace`

- `./lib/i18n` → `frontend/src/lib/i18n.ts`（一覧確認・内容未読）
- `react` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `./lib/api` → `frontend/src/lib/api.ts`（一覧確認・内容未読）
- `./lib/router` → `frontend/src/lib/router.tsx`（一覧確認・内容未読）
- `./pages/Home` → `frontend/src/pages/Home.tsx`（一覧確認・内容未読）
- `./pages/WorkList` → `frontend/src/pages/WorkList.tsx`（一覧確認・内容未読）
- `./pages/Workroom` → `frontend/src/pages/Workroom.tsx`（一覧確認・内容未読）
- `./pages/Settings` → `frontend/src/pages/Settings.tsx`（一覧確認・内容未読）
- `./pages/Welcome` → `frontend/src/pages/Welcome.tsx`（一覧確認・内容未読）
- `./pages/Operations` → `frontend/src/pages/Operations.tsx`（一覧確認・内容未読）
- `./components/AuthGate` → `frontend/src/components/AuthGate.tsx`（一覧確認・内容未読）

[詳細な図と説明を見る](n-frontend-src-app-tsx-b9c538/README.md)

### n-frontend-src-main-tsx-d34671

確認済みファイル: `frontend/src/main.tsx`

解析: 字句抽出。静的なimport／export参照です。関数の実行順序やHTTP通信は表していません。

- `react` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `react-dom/client` → 外部・標準ライブラリ・別名など。ローカル対応先は未確定
- `./styles.css` → `frontend/src/styles.css`（内容確認済み）
- `./workroom.css` → `frontend/src/workroom.css`（内容確認済み）
- `./quiet-cinema.css` → `frontend/src/quiet-cinema.css`（内容確認済み）
- `./ui-polish.css` → `frontend/src/ui-polish.css`（内容確認済み）
- `./bot-polish.css` → `frontend/src/bot-polish.css`（内容確認済み）
- `./App` → `frontend/src/App.tsx`（内容確認済み）
- `./obsidian.css` → `frontend/src/obsidian.css`（内容確認済み）
- `./paper.css` → `frontend/src/paper.css`（内容確認済み）

[詳細な図と説明を見る](n-frontend-src-main-tsx-d34671/README.md)

