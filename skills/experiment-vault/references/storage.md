# Storage: where the vault lives

The vault is a folder layout ([capsule-format.md](capsule-format.md)), so it can live on a disk, in a synced folder, or in a bucket. For a lifetime of hypotheses that any agent on any machine can reach, use one Google Cloud Storage bucket with Autoclass, terminal class Archive.

## Why Google Cloud Storage with Autoclass

| Need | How the bucket meets it |
|---|---|
| Cheap, kept for years | Objects nobody reads move down on their own: Standard, then Nearline after 30 days, Coldline after 90, Archive after 365. Archive is roughly $0.0012 per GB per month, about a twentieth of Standard |
| Always available, never "thawed" | Every class, Archive included, is read immediately with the same API. There is no restore job, unlike S3 Glacier Flexible Retrieval and Deep Archive, which take hours |
| Pulled forward when worked on again | Autoclass moves an object back to Standard when it is read, so a replayed capsule is warm again with no command |
| One copy of shared data | Blobs are named by their SHA-256, so the same dataset or wheel in many capsules is one object |
| Code that costs its changes, not its size | Code is kept as git bundles per repository: the history once, then only the commits each capture adds |
| Already in use | Dermot's systems already run on Google Cloud and the gcloud CLI, so no new account or credentials |

Prices are approximate (October 2026, a single US region); check the [Cloud Storage pricing page](https://cloud.google.com/storage/pricing). Reading from colder classes costs a retrieval fee per GB (highest for Archive, around $0.05), and Autoclass charges a small monthly management fee per object over 128 KiB; manifests are smaller and stay in Standard. A capsule of a few hundred megabytes in Archive costs well under a cent a month.

Use a single region, not multi-region: the vault is a record, not a serving path. `us-central1` is among the cheapest.

## Setting it up (a person, once)

Creating a project and a bucket and granting access change a cloud account, so they are a person's steps, never an agent's. This is the sequence that set up the first vault, in PowerShell; bash is the same with `\` line breaks. Each step says how to check it.

### 1. A project of its own

A dedicated project keeps the vault's cost visible on its own and its access apart from everything else. Skip to step 2 to use an existing project.

```powershell
gcloud auth login
gcloud billing accounts list                     # note the ACCOUNT_ID
gcloud organizations list                        # note the ID, if there is one
$Project = "my-research"                        # globally unique, 6 to 30 characters, permanent
$Billing = "<ACCOUNT_ID>"
gcloud projects create $Project --name="Research" --organization=<ID>   # leave out --organization without one
gcloud billing projects link $Project --billing-account=$Billing
gcloud config set project $Project
gcloud services enable storage.googleapis.com iam.googleapis.com iamcredentials.googleapis.com billingbudgets.googleapis.com
gcloud billing accounts describe $Billing --format="value(currencyCode)"   # the budget must use this currency
gcloud billing budgets create --billing-account=$Billing --display-name="Research vault" `
  --budget-amount=15USD --filter-projects="projects/$Project" `
  --threshold-rule=percent=0.5 --threshold-rule=percent=1.0
```

- `Cloud billing quota exceeded` when linking: the billing account has as many projects as it may. Unlink one that is no longer used (`gcloud billing projects list --billing-account=$Billing`, then `gcloud billing projects unlink <id>`; that stops everything in it), or ask Google for more at the link in the message.
- `INVALID_ARGUMENT` on the budget: the amount is not in the billing account's currency.
- `gcloud config set project` warns that the Application Default Credentials quota project differs: leave it. The vault uses gcloud itself, and other local code may rely on that file.

Check: `gcloud billing projects describe $Project` shows `billingEnabled: true`.

### 2. The bucket

```powershell
$Bucket  = "my-research-vault"                    # globally unique
$Region  = "us-central1"                         # among the cheapest; it cannot change later
gcloud storage buckets create "gs://$Bucket" --location=$Region `
  --uniform-bucket-level-access --public-access-prevention `
  --enable-autoclass --autoclass-terminal-storage-class=ARCHIVE `
  --soft-delete-duration=90d
```

Check: `gcloud storage buckets describe "gs://$Bucket"` shows the location, `autoclass` enabled with `terminalStorageClass: ARCHIVE`, `public_access_prevention: enforced`, `uniform_bucket_level_access: true` and `retentionDurationSeconds: '7776000'`.

### 3. The agents' account, which can add and read and never delete

```powershell
$SaEmail = "research-agents@$Project.iam.gserviceaccount.com"
gcloud iam service-accounts create research-agents --display-name="Research agents (experiment vault)"
gcloud storage buckets add-iam-policy-binding "gs://$Bucket" --member="serviceAccount:$SaEmail" --role=roles/storage.objectCreator
gcloud storage buckets add-iam-policy-binding "gs://$Bucket" --member="serviceAccount:$SaEmail" --role=roles/storage.objectViewer
```

The roles are on the bucket, not the project, so the account can reach nothing else. Replacing an object needs delete permission, which neither role has, so "never overwritten" is a property of the bucket, not only of the tool. Check: `gcloud storage buckets get-iam-policy "gs://$Bucket"` lists the account under exactly those two roles.

### 4. Initialise the vault

```powershell
python -m pip install PyYAML
$Vault = "<clone of ai-assisted-research>\skills\experiment-vault\bin\vault.py"
python $Vault --vault "gs://$Bucket/vault" init
```

Check: it prints `Initialised gs://<bucket>/vault`, and `gcloud storage ls "gs://$Bucket/vault/"` shows `VAULT.md`.

### 5. Prove it, once

A throwaway experiment through the whole cycle. In an empty folder, make a git repository with a `data/` folder, a script that writes `out/metrics.json`, and a commit; then, with `$env:PYTHONHASHSEED = "0"` and `$V = @("--vault", "gs://$Bucket/vault", "--project", "smoke-test")`:

```powershell
python $Vault @V run --node H-001 --data data --outputs out --metrics out/metrics.json --metric score --no-link --dry-run '--' python train.py
python $Vault @V run --node H-001 --data data --outputs out --metrics out/metrics.json --metric score --no-link '--' python train.py
$Id = (python $Vault @V list --node H-001 | Select-Object -First 1)
python $Vault @V verify $Id --deep
python $Vault @V replay $Id --setup none --no-record
```

They print `ready`, `Capsule H-001/<id>`, `ok ... code rebuilt and its tree checked`, and `Verdict: identical`. Quote `'--'`: PowerShell can drop a bare `--`. Do not name a variable `$Args`, which PowerShell reserves.

Then prove the account's limits, acting as it. That needs the credentials API (enabled in step 1) and, once, the right to act as the account; it can take a few minutes to apply:

```powershell
gcloud iam service-accounts add-iam-policy-binding $SaEmail --member="user:<you>" --role=roles/iam.serviceAccountTokenCreator
gcloud storage rm "gs://$Bucket/vault/VAULT.md" --impersonate-service-account=$SaEmail        # must be denied
gcloud storage ls -r "gs://$Bucket/vault/**" --impersonate-service-account=$SaEmail            # must list
"test" | Set-Content "$env:TEMP\t.txt"
gcloud storage cp "$env:TEMP\t.txt" "gs://$Bucket/vault/checks/t.txt" --impersonate-service-account=$SaEmail   # must succeed
gcloud storage cp "$env:TEMP\t.txt" "gs://$Bucket/vault/checks/t.txt" --impersonate-service-account=$SaEmail   # must be denied
```

If the delete or the second copy succeeds, the account has more access than this page grants somewhere else, such as a project-wide Storage role: remove it before any agent uses the vault.

### 6. A key for cloud sessions

Agents in cloud sessions use the account through a key. The key can add and read in this one bucket and nothing more; if it leaked, records could be read and added, and none lost.

```powershell
$KeyDir = "$env:USERPROFILE\.secrets"
New-Item -ItemType Directory -Force $KeyDir | Out-Null
gcloud iam service-accounts keys create "$KeyDir\research-agents.json" --iam-account=$SaEmail
```

Organisations created since 2024 block keys (`Key creation is not allowed on this service account`, `constraints/iam.disableServiceAccountKeyCreation`). Lift the block for this project only, create the key, and put the block back; the key keeps working:

```powershell
gcloud projects get-ancestors $Project                       # the organization's ID
gcloud organizations add-iam-policy-binding <ORG_ID> --member="user:<you>" --role=roles/orgpolicy.policyAdmin
gcloud resource-manager org-policies disable-enforce iam.disableServiceAccountKeyCreation --project=$Project
gcloud iam service-accounts keys create "$KeyDir\research-agents.json" --iam-account=$SaEmail
gcloud resource-manager org-policies enable-enforce iam.disableServiceAccountKeyCreation --project=$Project
```

Give the key to the cloud environment as a secret environment variable, never in a chat or a repository: `Get-Content "$KeyDir\research-agents.json" -Raw | Set-Clipboard`, then the environment's settings (the cloud environment menu in the session's title bar, then Edit), and a variable `RESEARCH_VAULT_GCP_KEY` whose value is the whole JSON. Keep the file in a password manager and delete it from disk. A session's setup script cannot read saved variables, so nothing signs gcloud in at start: `vault.py` reads the key itself (below). With a restricted network setting, the environment must also allow `storage.googleapis.com` and `oauth2.googleapis.com`.

To rotate or revoke: `gcloud iam service-accounts keys list --iam-account=$SaEmail`, then `gcloud iam service-accounts keys delete <KEY_ID> --iam-account=$SaEmail`.

### How vault.py uses the key

When `RESEARCH_VAULT_GCP_KEY` holds a service account key (or `RESEARCH_VAULT_GCP_KEY_FILE` names a key file), `vault.py` writes it to a private temporary file, readable by its owner only and deleted when the command ends, and points its own gcloud calls at it (`CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE`). The machine's own gcloud sign-in is left as it is, the experiment is started without either variable, and the key is never printed or recorded in a capsule. Without either variable, the vault uses whichever account gcloud is signed in as, which is how a person runs it.

### 7. Point workspaces at the vault

```yaml
vault:
  uri: "gs://my-research-vault/vault"
  project: "my-project"   # defaults to dag_project
  vendor_wheels: true
  rtol: 1.0e-9
  atol: 1.0e-12
```

Soft delete keeps a deleted object recoverable for 90 days, against a mistake by a person with delete rights; agents never have them.

## Lifecycle rules instead of Autoclass

Autoclass is the default because it pulls objects forward on read. With a predictable access pattern and no wish for the management fee, use age-based rules instead; `vault.py lifecycle` prints them (`--nearline 30 --coldline 90 --archive 365` by default):

```powershell
python <skills>\experiment-vault\bin\vault.py lifecycle > vault-lifecycle.json
gcloud storage buckets update "gs://$Bucket" --no-enable-autoclass --lifecycle-file=vault-lifecycle.json
```

With rules, a replayed capsule stays in its cold class, and every read pays that class's retrieval fee. To work on an old hypothesis for a while, pull its capsule forward by hand (a person's step):

```powershell
gcloud storage objects update "gs://$Bucket/vault/capsules/<project>/<node>/**" --storage-class=STANDARD
```

Its blobs follow when a later rule or an Autoclass bucket moves them; blobs are shared, so do not move a blob down by hand.

## Retention and deletion

Nothing in the vault is deleted in normal use: a superseded capsule stays, as history. If a capsule must go (data that should never have been stored), a person deletes its manifest, then any blob no other manifest names; there is no tool for it on purpose. A bucket retention policy (`--retention-period`) makes even that impossible for its duration; add one only once the vault's layout is settled, and do not lock it (`--lock-retention-period` cannot be undone).

## A local vault

`--vault <folder>` or `vault.uri: "../vault"` uses a folder with the same layout, for offline work or tests. Copy it into the bucket later with `gcloud storage rsync --recursive --no-clobber <folder> gs://<bucket>/vault`; capsule ids and blob names are the same everywhere.
