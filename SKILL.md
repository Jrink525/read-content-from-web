---
name: read-content-from-web
description: Read long-form content from paywalled or login-walled sites. Supports Medium articles (via freedium mirror), X/Twitter long-form articles (via fxtwitter API), and general web pages. When user shares any URL for reading/extraction/note-taking, handle everything automatically without asking for repeated instructions.
---

# Read Content from Web

## ⚡ Default Behavior (No Questions Asked)

When the user shares a URL and asks to read/extract/note/summarize it:

1. **Auto-detect** the site type (Medium / X / other)
2. **Fetch full content** using the best available method
3. **Translate to Chinese** (if English original) with natural, idiomatic flow
4. **Enhance** — clarify, structure, add glosses, extract key points
5. **Save** to `knowledges/<category>/` with proper YAML frontmatter
6. **Classify & push** — run `_organize.py` to auto-classify and push to GitHub

No need to ask the user "should I translate?" or "where should I save?" — these are the defaults.

---

## Supported Sites & Fetch Methods

### Medium

**Primary:** Freedium mirror
```
web_fetch(url="https://freedium-mirror.cfd/https://medium.com/...", maxChars=100000)
```

**Fallback chain** (try in order):
```
1. https://freedium-mirror.cfd/https://medium.com/...
2. https://freedium.cfd/https://medium.com/...
3. https://freedium-tnrt.onrender.com/https://medium.com/...
4. https://webcache.googleusercontent.com/search?q=cache:https://medium.com/...
```

### X/Twitter

**For long-form articles** (detect by checking if response has `tweet.article`):
```
https://api.fxtwitter.com/{username}/status/{tweet_id}
```

Content extraction (Python):
```python
import json, sys
data = json.loads(sys.stdin.read())
# Long-form article
blocks = data['tweet']['article']['content']['blocks']
# Regular tweet
text = data['tweet']['text']
```

**For regular tweets** — same fxtwitter API, extract `tweet.text`.

**Fallback:** `https://api.vxtwitter.com/{username}/status/{tweet_id}`

### Image Extraction (X/Twitter)

fxtwitter API returns media in `tweet.media.all` (array) for tweet-level images, and `tweet.article.content.media` (array) for article-level images. Each entry has:
- `url`: direct image URL
- `type`: mime type (e.g. `image/jpeg`, `image/png`)
- `altText`: optional alt text
- `width` / `height`: dimensions

**Extraction pattern:**

```python
media = []
# Tweet-level media
if 'media' in tweet and 'all' in tweet['media']:
    media.extend(tweet['media']['all'])
# Article-level media
if 'article' in tweet and 'content' in tweet['article'] and 'media' in tweet['article']['content']:
    media.extend(tweet['article']['content']['media'])
```

For general web pages, extract `<img>` src URLs from HTML content.

### General Web Pages

`web_fetch` with appropriate `maxChars` (default 100000 for articles, 15000 for quick lookups).

---

## OpenClaw Tool Notes & Workarounds

### web_fetch truncation

`web_fetch` has a hard cap (~100-400KB depending on content). For articles that may exceed this:

1. First try `web_fetch(url="...", maxChars=100000)`
2. If truncated (detect by incomplete sentence at end or missing closing content), use `exec` + `curl` + Python for full extraction:

```python
# Full extraction via curl
import subprocess, json
result = subprocess.run([
    "curl", "-s",
    "https://api.fxtwitter.com/{username}/status/{tweet_id}"
], capture_output=True, text=True, timeout=15)
data = json.loads(result.stdout)
# Now extract blocks even if large
```

### curl SSL issues

If curl returns SSL errors, add `-k` flag:
```
curl -sk "https://..."
```

---

---

## YouTube Videos

### Detection

YouTube URLs match:
- `youtu.be/<id>` (short link)
- `youtube.com/watch?v=<id>` (full link)
- `youtube.com/embed/<id>` (embed link)
- `m.youtube.com/watch?v=<id>` (mobile link)

### Pipeline Overview

```
YouTube URL
  → Check available captions (yt-dlp --list-subs)
  → Download auto-generated captions (yt-dlp --write-auto-subs)
  → Extract pure text (strip timestamps, deduplicate)
  → Analyze topics & organize into sections
  → Create bilingual knowledge base document (EN+CN)
  → Save to knowledges/<category>/ and push to GitHub
```

### Prerequisites

| Tool | Path | Notes |
|------|------|-------|
| `yt-dlp` | `./yt-dlp` (2026.03.17) | YouTube download tool |
| `ffmpeg` / `ffprobe` | `./ffmpeg` / `./ffprobe` (7.0.2 musl) | Audio processing |
| Node.js | `/usr/local/bin/node` v24.14.0 | JS Runtime for yt-dlp EJS challenge |
| Cookies | `/tmp/yt_cookies3.txt` | YouTube auth cookies (Netscape format) |

> **Note:** All paths assume the workspace root (`/home/node/.openclaw/workspace/`).
> Export PATH before use: `export PATH="/home/node/.openclaw/workspace:$PATH"`

### Step-by-Step Flow

#### 1. Check Available Subtitles

```bash
export PATH="/home/node/.openclaw/workspace:$PATH"

./yt-dlp \
  --js-runtimes node:/usr/local/bin/node \
  --cookies /tmp/yt_cookies3.txt \
  --list-subs \
  "https://youtu.be/<VIDEO_ID>"
```

If English captions (`en`) are listed under "Available automatic captions":
→ **Proceed with Step 2** (auto-captions are free, fast, and reliable for English)

If **no captions** exist:
→ Download audio and use Whisper API for transcription:
  - Read the `openai-whisper-api` skill (`/app/skills/openai-whisper-api/SKILL.md`)
  - Note: Requires a real OpenAI API key; DeepSeek keys won't work (DeepSeek has no Whisper API)

#### 2. Download Subtitles

```bash
export PATH="/home/node/.openclaw/workspace:$PATH"

./yt-dlp \
  --js-runtimes node:/usr/local/bin/node \
  --cookies /tmp/yt_cookies3.txt \
  --write-auto-subs \
  --sub-langs en \
  --skip-download \
  --convert-subs srt \
  -o "/home/node/.openclaw/workspace/downloads/%(id)s_subs" \
  "https://youtu.be/<VIDEO_ID>"
```

Output SRT file: `downloads/<VIDEO_ID>_subs.en.srt`

**Flags explained:**
- `--write-auto-subs` — download YouTube's auto-generated captions
- `--sub-langs en` — only English captions
- `--skip-download` — don't download the video itself (only captions)
- `--convert-subs srt` — convert to SRT format (most parseable)

#### 3. Extract Pure Text from SRT

SRT files have this structure:
```
1
00:00:01,500 → 00:00:04,200
Hello fellow Java developers.

2
00:00:04,300 → 00:00:07,800
What if I told you that you could start building AI applications?
```

**Cleaning steps:**

```bash
# 1. Remove timestamp lines (contain →)
sed -n '/^[0-9][0-9]:[0-9][0-9]:[0-9][0-9]/!p' <srt_file> | \
  # 2. Remove segment number lines (bare numeric)
  grep -v '^[0-9]*$' | \
  # 3. Remove empty lines
  sed '/^$/d' > /tmp/raw_text.txt
```

**Deduplication in Python:**

Auto-captions often repeat consecutive lines. Clean with:

```python
def clean_subtitles(input_file, output_file):
    with open(input_file) as f:
        lines = [l.strip() for l in f if l.strip()]
    
    # Deduplicate consecutive near-identical lines
    cleaned = []
    for line in lines:
        if cleaned and (line == cleaned[-1] or 
                        line.replace('\r','') == cleaned[-1].replace('\r','')):
            continue
        cleaned.append(line)
    
    # Write cleaned text
    with open(output_file, 'w') as f:
        for line in cleaned:
            f.write(line + '\n')
    
    print(f"Original: {len(lines)} lines")
    print(f"Deduped:  {len(cleaned)} lines")
    return cleaned
```

#### 4. Analyze Topics & Structure

Scan the deduplicated text to identify major sections:

```python
def scan_topics(cleaned_lines, interval=2000):
    """Sample text every N lines to identify chapter transitions."""
    for i in range(0, len(cleaned_lines), interval):
        chunk = cleaned_lines[i:i+3]
        print(f"\n--- Lines {i+1} ---")
        for c in chunk:
            print(c[:200])
```

Also search for chapter-like keywords:
```python
keywords = ['section', 'chapter', 'part', 'project', 'demo', 
            'now we', 'next', 'let\'s build', 'agenda',
            'introduction to', 'rag', 'mcp', 'tool calling',
            'agents', 'observability', 'evaluation', 'testing',
            'structured output', 'getting started with',
            'project 1', 'project 2', 'project 3']
```

For long videos (>2h), use keyword scanning to find chapter boundaries rather than reading the full text.

#### 5. Create Knowledge Base Document

Structure for each section:

```markdown
# [Video Title] — 精要

> **视频**: [title](original-url)  
> **主讲**: author | **时长**: duration  
> **中文整理**: 根据字幕归纳核心内容

---

## 一、[Major Topic 1]

### 1.1 [Subtopic]

> "[Key English quote from speaker]"

**中文解读：** [Chinese explanation with technical insight]

```java
// code example from the video, enhanced if needed
```

## 二、[Major Topic 2]

...
```

**Guidelines:**
- Each section: English key quote → Chinese translation + technical insight → code example → practical notes
- Keep code original from the video (add missing imports/comments in Chinese)
- For very long courses, include a "Chapter Overview" table at the top
- Add a "总结" (Summary) section at the end with learning path recommendations

#### 6. Save to Knowledge Base

```
knowledges/<category>/<video-slug>.md
```

Example categories:
- `knowledges/spring/ai-agent/...` — Spring AI workshop/tutorial
- `knowledges/ai-tools/...` — AI tooling/tutorials
- `knowledges/database/...` — Database related

Update the category README and push:

```bash
cd /home/node/.openclaw/workspace/knowledges
GH_CONFIG_DIR=/home/node/.openclaw/gh-config git add <files>
GH_CONFIG_DIR=/home/node/.openclaw/gh-config git commit -m "feat: add <video> notes"
GH_CONFIG_DIR=/home/node/.openclaw/gh-config git push
```

> **Note:** `_organize.py` may time out for large repos. Use direct git commands as shown above.

### Video Metadata Check

```bash
# Get title and duration in seconds
export PATH="/home/node/.openclaw/workspace:$PATH"
./yt-dlp \
  --js-runtimes node:/usr/local/bin/node \
  --cookies /tmp/yt_cookies3.txt \
  --print title --print duration \
  "https://youtu.be/<VIDEO_ID>"
```

### Word Count & Scope Estimation

After text extraction, estimate how much content you're dealing with:
- **< 30K words** (~1h video) → Full detail, paragraph-level
- **30K-80K words** (~1-2h) → Section-level detail, paragraph-level for key parts
- **80K-150K words** (~3-6h) → Chapter-level summary, code+concepts only
- **> 150K words** (>6h) → High-level outline + links to timestamps

### Cookie Renewal

YouTube cookies expire. The user needs to re-export cookies from browser when:
- `yt-dlp` returns "Sign in to confirm you're not a bot"
- Captions download fails with 403 error
- User gets redirected to consent page

Cookie file location: `/tmp/yt_cookies3.txt` (Netscape format)

### Cleanup

After processing, remove temporary files to save tmpfs space (only 256MB available):
```bash
rm -f /home/node/.openclaw/workspace/downloads/<VIDEO_ID>*.srt
rm -f /home/node/.openclaw/workspace/downloads/<VIDEO_ID>*.mp3
rm -f /home/node/.openclaw/workspace/downloads/<VIDEO_ID>*.webm
rm -f /tmp/raw_text.txt
```

Keep only the final knowledge base `.md` file and `downloads/<VIDEO_ID>.txt` (if kept for reference).

---

## Translation Principles

- **No literal/机械翻译** — produce natural, idiomatic Chinese
- Preserve technical terms in English when appropriate (add Chinese gloss on first use)
- Keep code blocks in original language (only translate comments)
- For author voice/personality, preserve the tone
- For technical concepts: accuracy over elegance

---

## Enhancement Patterns

Apply automatically after fetching + translating:

| Content Type | Enhancement |
|-------------|-------------|
| Technical article | Add code examples, best practices, interview Q&A |
| Comparison/review | Reorganize as comparison table |
| Tutorial | Add prerequisite notes, common pitfalls |
| News/announcement | Add context, significance analysis |
| Long-form analysis | Structured summary with key takeaways |
| Paper list / paper roundup | Extract each paper as a separate entry with: core contribution, key design, why it matters. Save to `knowledges/papers/` with per-paper section anchors. Add topic-level observation at end. |

---

### Paper List / Conference Roundup Processing

When the X/Twitter or web content is a **list of papers** (e.g. DAIR.AI weekly top papers, conference highlights):

1. **Extract each paper** — parse the article/text into individual paper entries with title and description
2. **Search for paper links** — for each paper, search for its arxiv/paper URL (use `web_search` or `web_fetch` to find the paper on arxiv, openai.com, huggingface.co/papers, etc.)
3. **Per-paper structure**: paper title & link, core contribution, key design/innovation details, why it matters
4. **Save** to `knowledges/papers/<slug>.md`
5. **Add topic-level observation** at end — identify the overarching themes of the week/event
6. **Push**: `cd knowledges && git add papers/ && git commit && git push` (papers dir is NOT covered by `_organize.py`)
7. **Create `knowledges/papers/README.md`** on first use if missing

**Output format per paper**:
```markdown
## N. Paper Title

- **链接：** [arXiv:XXXX.XXXXX](URL)
- **类型：** 综述/原始研究/系统发布

### Core Contribution

...

### Why It Matters

...
```

---

## Output Structure

When saving to knowledge base, use this format:

```markdown
---
title: "Translated Title"
tags:
  - auto-detected-tags
date: YYYY-MM-DD
source: "original-url"
authors: "author-name"
---

# Chinese Title

> **来源：** [original-title](original-url)

Translated and enhanced content...

---

*Processed on {date} from {source-url}*
```

---

## 🖼️ Image Handling — Extract, Save, Reference

### Image Storage

Images from articles are saved to a unified directory:
```
knowledges/image/
```

This directory is excluded from `_organize.py` classification (images are not articles).

### Naming Convention

```
{article-slug}-{n}.{ext}
```

Where `article-slug` is the markdown filename without `.md`, `n` is a 1-based index, and `ext` is the original extension (`jpg`, `png`, `gif`).

### Step-by-Step Flow

1. **Extract** image URLs from the fetched content
2. **Download** via `curl -s -o <path> <url>`
3. **Save** to `knowledges/image/`
4. **Reference** in markdown with relative path: `![description](../image/filename.jpg)`

### X/Twitter Image Extraction

From fxtwitter JSON response, extract media URLs:

```python
import json, subprocess, os

def extract_and_save_images(tweet_data, article_slug):
    """
    Extract image URLs from fxtwitter response and save them.
    Returns list of (local_path, alt_text) tuples for markdown insertion.
    """
    images = []
    tweet = tweet_data.get('tweet', {})
    image_dir = '/home/node/.openclaw/workspace/knowledges/image'
    os.makedirs(image_dir, exist_ok=True)
    
    # 1. Collect media from tweet-level (all media types)
    if 'media' in tweet and 'all' in tweet['media']:
        for m in tweet['media']['all']:
            if m.get('type', '').startswith('image'):
                images.append({
                    'url': m['url'],
                    'alt': m.get('altText', ''),
                    'ext': m['url'].rsplit('.', 1)[-1].split('?')[0]
                })
    
    # 2. Collect media from article-level content
    if ('article' in tweet and 'content' in tweet['article'] 
            and 'media' in tweet['article']['content']):
        for m in tweet['article']['content']['media']:
            if m.get('type', '').startswith('image'):
                images.append({
                    'url': m['url'],
                    'alt': m.get('altText', ''),
                    'ext': m['url'].rsplit('.', 1)[-1].split('?')[0]
                })
    
    # 3. Deduplicate by URL
    seen_urls = set()
    unique_images = []
    for img in images:
        if img['url'] not in seen_urls:
            seen_urls.add(img['url'])
            unique_images.append(img)
    
    # 4. Download and save
    saved = []
    for i, img in enumerate(unique_images):
        filename = f"{article_slug}-{i+1}.{img['ext']}"
        local_path = os.path.join(image_dir, filename)
        subprocess.run([
            "curl", "-s", "-o", local_path,
            img['url']
        ], capture_output=True, timeout=15)
        
        if os.path.exists(local_path) and os.path.getsize(local_path) > 100:
            saved.append({
                'rel_path': f"../image/{filename}",
                'alt': img['alt']
            })
            print(f"  🖼️  Saved: image/{filename}")
        else:
            print(f"  ⚠️  Failed to save: {img['url']}")
    
    return saved


# Usage after fetching article:
# saved_images = extract_and_save_images(data, "article-slug-here")
# Then use saved_images in markdown: f"![alt]({img['rel_path']})"
```

### General Web Page Images

For non-X articles (Medium, general web):
1. Scan the fetched markdown content for image URLs
2. Download relevant images (infographics, diagrams, screenshots — skip avatars, icons, ads)
3. Save to `knowledges/image/`
4. Replace absolute URLs in markdown with relative paths

### Link Format in Markdown

```markdown
<!-- Article images use relative paths from their category subdirectory -->

![Claude Code Routines architecture](../image/claude-code-routines-full-course-1.jpg)

<!-- The ../image/ path works because articles are in subdirectories like:
     ai-tools/claude/article.md → ../image/image.jpg → knowledges/image/image.jpg -->
```

### Push to GitHub

When using `_organize.py push`, images in `knowledges/image/` are NOT auto-uploaded via the GitHub API (binary content). Use git directly for the initial seed:

```bash
cd /home/node/.openclaw/workspace/knowledges
git add image/
git commit -m "feat: add article images"
git push
```

For subsequent pushes with `_organize.py`, images can be committed via the same git flow alongside the API-based push, or add a post-push script to the organize script to `git push` the images dir separately if the API approach is used.

---

## GitHub Push

After saving to `knowledges/`:

```bash
cd /home/node/.openclaw/workspace/knowledges
python3 _organize.py
```

This auto-classifies, updates README, and pushes to GitHub. No manual git steps needed.

### Push with Images

Since `_organize.py` uses the GitHub Content API (no git client needed for markdown), images must be pushed via git when present:

```bash
cd /home/node/.openclaw/workspace/knowledges
# Markdown files: use organize script API push
python3 _organize.py push
# Images: use git directly
GH_CONFIG_DIR=/home/node/.openclaw/gh-config git add image/
GH_CONFIG_DIR=/home/node/.openclaw/gh-config git commit -m "feat: add article images"
GH_CONFIG_DIR=/home/node/.openclaw/gh-config git push
```

---

## 📂 Directory Size Management

### Threshold Rule

When any knowledge base directory (including subdirectories) exceeds **20 files**, automatically trigger a re-classification/split into finer-grained subdirectories.

### Current Subdirectory Structure (ai-tools example)

```
ai-tools/
├── agent-engineering/   (agent architecture, patterns, survival guide)
├── claude/              (Claude Code specific guides)
├── frameworks/          (agent framework comparisons)
└── ml-research/         (ML/RL papers)
```

### When to Split

| Threshold | Action |
|-----------|--------|
| > 20 files in any dir | Analyze content themes → create subdirectories → move files → update `_organize.py` subdirectory profiles |
| > 40 files in a subdir | Further split: e.g. `agent-engineering/` → `agent-engineering/patterns/` + `agent-engineering/practice/` |

### Implementation

During `_organize.py` execution, after classification:

```python
# Pseudo-logic
for directory in classified_dirs:
    count = len(list((KNOWLEDGES_DIR / directory).rglob("*.md")))
    if count > 20:
        print(f"  ⚠️  {directory}/ 达到 {count} 篇，建议拆分")
        # Trigger subdirectory audit or split routine
```

### When It Runs

- After every `_organize.py` run (implicitly checked)
- Also check explicitly when adding files manually
- The threshold is per-directory, not total — `agent-engineering/` 18 篇 + `spring/` 5 篇 = 各自独立计算

---

## Quick Reference: URL Detection

| URL Pattern | Site | Method |
|-------------|------|--------|
| `medium.com/...` | Medium | Freedium mirror |
| `towardsdatascience.com/...` | Medium (custom domain) | Freedium mirror |
| `x.com/.../status/...` | X/Twitter | fxtwitter API |
| `twitter.com/.../status/...` | X/Twitter | fxtwitter API |
| anything else | General | web_fetch |
| `youtu.be/...` or `youtube.com/watch?v=...` | YouTube | yt-dlp + auto-captions + transcript |
