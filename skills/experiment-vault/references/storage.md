# Storage: where the vault lives

The vault is a folder layout ([capsule-format.md](capsule-format.md)), so it can live on a disk, in a synced folder, or in a bucket. For a lifetime of hypotheses that any agent on any machine can reach, use one Google Cloud Storage bucket with Autoclass, terminal class Archive.

## Why Google Cloud Storage with Autoclass

| Need | How the bucket meets it |
|---|---|
| Cheap, kept for years | Objects nobody reads move down on their own: Standard, then Nearline after 30 days, Coldline after 90, Archive after 365. Archive is roughly $0.0012 per GB per month, about a twentieth of Standard |
| Always available, never "thawed" | Every class, Archive included, is read immediately with the same API. There is no restore job, unlike S3 Glacier Flexible Retrieval and Deep Archive, which take hours |
| Pulled forward when worked on again | Autoclass moves an object back to Standard when it is read, so a replayed capsule is warm again with no command |
| One copy of shared data | Blobs are named by their SHA-256, so the same dataset or wheel in many capsules is one object |
| Already in use | Dermot's systems already run on Google Cloud and the gcloud CLI, so no new account or credentials |

Prices are approximate (October 2026, a single US region); check the [Cloud Storage pricing page](https://cloud.google.com/storage/pricing). Reading from colder classes costs a retrieval fee per GB (highest for Archive, around $0.05), and Autoclass charges a small monthly management fee per object over 128 KiB; manifests are smaller and stay in Standard. A capsule of a few hundred megabytes in Archive costs well under a cent a month.

Use a single region, not multi-region: the vault is a record, not a serving path. `us-central1` is among the cheapest.

## Create the bucket (Dermot, once)

Creating the bucket and granting access changes the cloud project, so it is a person's step, not an agent's. Replace the project and bucket names. PowerShell:

```powershell
$Project = "<your-gcp-project>"
$Bucket  = "<your-research-vault>"
gcloud storage buckets create "gs://$Bucket" --project=$Project --location=us-central1 `
  --uniform-bucket-level-access --public-access-prevention `
  --enable-autoclass --autoclass-terminal-storage-class=ARCHIVE `
  --soft-delete-duration=90d
# Agents create and read, and cannot delete or overwrite (overwriting needs delete).
gcloud storage buckets add-iam-policy-binding "gs://$Bucket" `
  --member="serviceAccount:<research-agents>@$Project.iam.gserviceaccount.com" --role=roles/storage.objectCreator
gcloud storage buckets add-iam-policy-binding "gs://$Bucket" `
  --member="serviceAccount:<research-agents>@$Project.iam.gserviceaccount.com" --role=roles/storage.objectViewer
python <skills>\experiment-vault\bin\vault.py --vault "gs://$Bucket/vault" init
```

bash is the same with `\` line breaks. Then add the vault to each research workspace's `research.yaml`:

```yaml
vault:
  uri: "gs://<your-research-vault>/vault"
  project: "my-project"   # defaults to dag_project
  vendor_wheels: true
  rtol: 1.0e-9
  atol: 1.0e-12
```

Soft delete keeps a deleted object recoverable for 90 days, against a mistake by a person with delete rights. Agents never have them: `objectCreator` plus `objectViewer` can write a new object and read any, and cannot replace or remove one. That makes "never overwritten" a property of the bucket, not only of the tool.

A cloud session reaches the bucket with a service account: the session's environment needs its key as a secret, and `gcloud auth activate-service-account --key-file=...` in the setup script.

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
