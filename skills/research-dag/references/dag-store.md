# The shared DAG store

A hypothesis DAG kept as one YAML file in one repository has a single writer at a time. Two agents on two machines, or two branches of the same repository, each edit their copy and the second merge conflicts, or silently keeps one side. The DAG store removes the shared file: every change is a new, never-edited event file in a separate git repository, and the DAG is what replaying those events produces.

## Opting in

Add two keys to `research.yaml`:

```yaml
dag_store: "https://example.com/you/research-dags.git"
dag_project: "my-project"
```

`dag_store` is one of:

- a path to an existing clone, used as it is (relative paths resolve against the folder holding `research.yaml`);
- a git URL, or a path to a bare repository, cloned on first use into `$RESEARCH_DAG_HOME/<repo name>`, by default `~/.research-dags/<repo name>`.

`dag_project` is the project's folder in the store, so one store can hold many projects. With neither key set, every tool works on the plain YAML file at `dag_path`, exactly as before. With only one set, `dag_update.py` warns and uses the plain file.

## Seeding a project

Create the store once, as an empty private repository, then import the existing DAG:

```bash
python <skills>/research-dag/bin/dag_store.py import --from research/hypothesis-dag.yaml
python <skills>/research-dag/bin/dag_store.py view
```

`import` writes one `doc` event for the file's top-level keys and one `add` event per node, preserving every field and the order of nodes and fields, then replays them and refuses to commit unless replay reproduces the file's content. It only seeds an empty project. `verify --against <file>` repeats that check later.

The file's leading comment block, and the comment blocks directly above a top-level key or a node, travel with the events and are written back into the view. Comments elsewhere, such as between a node's fields, are not kept.

## Day to day

| Step | What happens |
|---|---|
| `dag_update.py --action ...` | Pull the store, replay, make the change, diff it into events, commit, push; on a rejected push, rebase and push again (up to five tries); regenerate the view |
| `dag_store.py view` | Pull and regenerate the view, for reading what others wrote |
| `dag_store.py report` | List concurrent edits, aliases, and events naming a node the store lacks |
| `dag_store.py record` | Turn edits a tool made to the view file directly into events |
| `dag_store.py prune` | Move the events of closed nodes into an archive file |
| `dag_store.py sync` | Push anything a previous write could not |

The view at `dag_path` is regenerated on every write. It opens with a banner and the store commit it was generated from, so do not edit it by hand: a direct edit is lost at the next write unless `record` turns it into events first. `record` diffs the edited view against the store as it stood at that commit, so changes others pushed since are kept, not reverted. Tools that rewrite the YAML themselves, such as `reconcile.py --migrate`, need `record` afterwards.

A write that cannot reach the remote is committed to the local clone and pushed by the next write or `sync`.

## Concurrent writers

Edits never merge-conflict, because every event is a new file. Two cases still need a rule.

Two writers change the same field. Each `update` event carries the value its writer saw (`prev`). When replay finds a different value in place, the two edits were concurrent: the later event (by timestamp) wins, and the value it replaced is reported by `report`, printed by `dag_update.py`, and written as a comment above the node in the view. List fields that only grow, such as `avenues` or a list of notes, are written as appends, so concurrent appends all survive.

Two writers add a node under the same id. Ids stay hierarchical (H-204.4.25) and are allocated after a fresh pull, so this only happens when two writers add under the same parent between one pull and the next push. The node already in the store keeps the id. The writer whose push was rejected finds the duplicate after the rebase, renames its own node with the next free letter suffix (H-204.4.25b), records an `alias` event, appends the new id to the parent's avenues, and pushes. `dag_update.py` prints the id the node ended up with, and `validate_dag_references.py` lists every alias, since a reference to the original id written before the rename may mean either node. A duplicate with no alias recorded, such as one written by hand, replays with the earlier event keeping the id and the later taking the suffix.

## Ids

A flat DAG, where every id is H-NNN, keeps sequential numbering. A DAG with hierarchical ids numbers a child under its parent: the next dotted number after the parent's existing children (H-204.4.26 after H-204.4.25); for a block parent H-N00 with no dotted children, the next free flat id in its block (H-705 under H-700); for the root H-000, the next free block; otherwise a new dotted level (H-204.1).

## Pruning

`dag_store.py prune` moves every event of the nodes that are closed (by default `discarded`, `ineffective` or `validated`) and untouched for `--days` (default 90) into one new archive file. Replay reads the archives as well, so the DAG and its view do not change; only the live `events/` folder shrinks. An archived node can still be changed: the new event goes in `events/` as usual. `--dry-run` lists the nodes first; `--statuses` changes the closed set.

## Format

```
<store>/README.md
<store>/<project>/events/YYYY-MM-DD/<utc-stamp>-<host>-<hex>[-NNNN].json
<store>/<project>/archive/<utc-stamp>-<host>-<hex>.jsonl
```

Each event is one JSON file. A write of several events shares one timestamp and numbers its files in order. Archive files hold one event per line, with `src`, the path it had under the project folder. The DAG is the live events and every archive replayed in (`ts`, `src`) order, de-duplicated by `src`.

| type | fields |
|---|---|
| `doc` | `fields` (top-level keys other than `nodes`), `order` (top-level key order), `header` (the file's leading comment), `comments` (key to the comment above it), `unset` |
| `add` | `id`, `node` (the whole node, fields in order), `comment` (the comment above it) |
| `update` | `id`, `set` (field to new value), `prev` (field to the value the writer saw), `unset` |
| `append` | `id`, `field`, `values` (items appended to a list field, skipping ones already there) |
| `alias` | `id` (the id the node goes by), `was` (the id it was added as), `target` (the `eid` of that `add`) |

Every event also carries `eid` (its file name without `.json`), `ts` (ISO-8601 UTC) and `host`. Values JSON cannot hold are tagged: `{"$date": "2026-01-31"}`, `{"$datetime": "..."}`, and `{"$map": [[key, value], ...]}` for a mapping whose keys are not all strings. [../schemas/dag_event.schema.json](../schemas/dag_event.schema.json) is the JSON Schema. The store's own `README.md`, written on first use, repeats the format for an agent without this skill.
