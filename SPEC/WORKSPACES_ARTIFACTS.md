# Workspaces and Artifacts

## Workspace

A Workspace is:

```text
workspace_id
host_id
root_path
display_name
git metadata
permissions
session links
```

All filesystem/shell operations are scoped to a Workspace unless explicitly elevated.

From phone/WebUI a user must be able to:
- choose host,
- browse allowed roots,
- create folder,
- select existing folder,
- initialize/open Git repository,
- start conversation,
- see file tree and diffs,
- approve edits/commands,
- download/view artifacts.

## Artifact

Typed first-class object:
- code/file
- image
- video
- screenshot
- document
- diff
- patch
- log
- test_report
- plan
- benchmark_report
- arbitrary_file

Artifacts have:
- ID
- MIME/type
- creator/run
- workspace path or managed-store location
- size/hash
- provenance
- preview metadata

Agents reference `artifact://<id>`; full contents are loaded only when requested.

## Transfer

Artifacts can move:
- remote host -> Harness,
- Harness -> remote host,
- creative host -> workspace,
- browser/client -> workspace.

Transfers are checksummed and evented.
