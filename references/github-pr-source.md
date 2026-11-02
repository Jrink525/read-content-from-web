# GitHub PR / issue as source

Trigger: the shared URL matches `github.com/<owner>/<repo>/pull/<n>` or `/issues/<n>`. Treat it as a document, not a blog page: the PR body is usually the write-up, and the added files are the substance.

## 1. Read the body first

```bash
curl -s https://api.github.com/repos/<owner>/<repo>/pulls/<n> | python3 -c "
import sys,json
d=json.load(sys.stdin)
for k in ('number','title','state','merged_at','created_at','additions','deletions','changed_files'): print(k+':', d.get(k))
print('author:', d['user']['login'])
print('---BODY---'); print(d.get('body') or '')"
```

PR bodies carry sections that replace your own analysis: `Summary`, `Evidence`, `Merge danger`, `Left out on purpose`, `Not in this PR`. Quote them as the author's limits instead of inferring limits of your own. Print the body whole; piped output truncates long bodies silently, so check the tail before concluding it is short.

For an issue, the same call without `/pulls` returns body and comments; fetch comments with `.../issues/<n>/comments?per_page=100` when the discussion carries the argument.

## 2. List the files to see the shape

```bash
curl -s "https://api.github.com/repos/<owner>/<repo>/pulls/<n>/files?per_page=100" | python3 -c "
import sys,json
for f in json.load(sys.stdin): print(f['filename'], f['status'], f['additions'])"
```

Markdown and config files added by the PR are the document set; skip lockfiles, generated output and tests unless the piece is about them. The count of added lines per file tells you which one carries the argument.

## 3. Fetch files at the head SHA, not main

```bash
SHA=$(curl -s https://api.github.com/repos/<owner>/<repo>/pulls/<n> | python3 -c "import sys,json;print(json.load(sys.stdin)['head']['sha'])")
curl -sfL "https://raw.githubusercontent.com/<owner>/<repo>/$SHA/<path>" -o "$SHA-$(basename <path>)"
```

A file added on an unmerged branch does not exist on `main` and returns 404 there. Record the SHA in the note, because the PR changes under you.

If the head branch was deleted after merge, use `merge_commit_sha` from the same response; when that is null, read the PR's Files-changed page.

## 4. Follow the body's reading order

The author often says which file to read first and which to skim last; obey it rather than reading alphabetically.

## 5. Skeleton for a PR that is itself a design document

1. 速览 6–8 条：状态（open / merged）、规模（文件数、增删行数）、这份文档定义了什么。
2. 词汇或定义表：每个术语给定义，并把 `Avoid` 列表一起抄下来，那是作者的设计约束。
3. 设计步骤：每步写决策加可检查的完成判据。
4. 示例表：问题 → 任务 / 方案，保留原文分档。
5. 明确不做什么：作者声明的排除项与搁置项，单独一节。
6. 证据与合并风险：原文自述的验证方式、two-way/one-way door、blast radius。
7. 可迁移原则 4–6 条，标明是自己的提炼。
8. 局限：PR 未合并时文件不在主干、无代码可跑、调研快照日期、价格与 beta 状态会过期。

## 6. Report

In the reply give the PR number, its state at read time (open / merged / closed), and the commit it was read at, then the four to six findings. An open PR is a moving target; the state line is what makes the digest checkable later.
