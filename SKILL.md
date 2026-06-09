---
name: read-content-from-web
description: Read long-form content from paywalled, login-walled, or Cloudflare-protected sites. Supports Medium (freedium mirror), X/Twitter long-form (fxtwitter API), Cloudflare-protected pages (Baeldung etc. via JinAI reader), WeChat articles (direct HTML extraction), and general web pages. When user shares any URL for reading/extraction/note-taking, handle everything automatically without asking for repeated instructions.
---

# Read Content from Web

## ⚡ Default Behavior (No Questions Asked)

When the user shares a URL and asks to read/extract/note/summarize it:

1. **Auto-detect** the site type (Medium / X / other)
2. **Fetch full content** using the best available method
3. **Translate to Chinese** (if English original) with natural, idiomatic flow
4. **Enhance** — clarify, structure, add glosses, extract key points
5. **Save to workspace root** as `<category>/<slug>.md` (e.g. `ai-tools/article.md`)
6. **Commit & push** via git

No need to ask the user "should I translate?" or "where should I save?" — these are the defaults.

---

## Directory Structure

```
📂 /home/node/.openclaw/workspace/     ← 知识库根目录 (git repo: knowledges)
├── ai-tools/           AI 工具 & 编程助手
│   ├── autoresearch/
│   ├── career/
│   ├── codex/
│   ├── enterprise/
│   └── harness/
├── database/           数据库
├── spring/             Spring Boot（15篇）
├── sre/                运维 & SRE
├── system-design/      系统设计
├── programming/        编程语言 & 范式
├── infrastructure/     基础设施架构
├── image/              文章图片
├── papers/             论文笔记
├── skills/             OpenClaw Skills
└── memory/             会话记忆
```

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

先尝试 `web_fetch`。如果返回 403 且包含 `"Just a moment..."` 或 Cloudflare challenge，说明被 Cloudflare 拦截了，自动降级到 JinAI Reader。

`web_fetch` with appropriate `maxChars` (default 100000 for articles, 15000 for quick lookups).

---

### Cloudflare-Protected Pages (Baeldung 等)

**问题**：Baeldung、某些技术博客挂了 Cloudflare WAF（JS challenge），`web_fetch` 和 `curl` 都只能拿到 `"Just a moment..."` 页面。

**解决方案：JinAI Reader API** (`r.jina.ai`)

向 `r.jina.ai` 发 POST 请求（空 JSON body），它的渲染引擎能过 Cloudflare：

```bash
# 关键：不需要 API key！POST 空 JSON body 即可
curl -sL --max-time 20 \
  "https://r.jina.ai/https://www.baeldung.com/spring-boot-log-properties" \
  -H "Content-Type: application/json" \
  -d '{}'
```

返回格式（Markdown 文本）：
```
Title: ...
URL Source: ...
Published Time: ...

Markdown Content:
## 1. Overview
...
```

**注意**：
- 必须用 `POST`（JinAI 默认会要求 auth header，POST 空 body 能绕过 auth 检查）
- 有些页面也会被 `r.jina.ai` 反爬（WeChat 文章就不行）
- 响应有长度限制，长文章可能被截断

---

### WeChat 公众号文章

**问题**：`mp.weixin.qq.com` 需要登录态 + JS 渲染，`web_fetch` / JinAI 都拿不到实际内容。

**解决方案**：直接下载 HTML → Python 正则提取 `id="js_content"` div 内容 → strip HTML tags

```python
import re, html

def extract_wechat_content(url):
    """从 WeChat 文章 URL 提取纯文本内容"""
    import subprocess
    
    # 1. 用 curl 下载完整 HTML（~750KB）
    result = subprocess.run([
        "curl", "-sL", "--max-time", "15",
        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        url
    ], capture_output=True, text=True, timeout=20)
    html_text = result.stdout
    
    # 2. 提取 id="js_content" 内部的 HTML
    match = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', html_text, re.DOTALL)
    if not match:
        return None
    
    content_html = match.group(1)
    
    # 3. Strip HTML tags，保留纯文本
    text = re.sub(r'<[^>]+>', ' ', content_html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = html.unescape(text)
    
    return text
```

**注意事项**：
- HTML 很大（750KB+），需要足够的网络超时
- 微信公众平台可能更新 HTML 结构，正则需要适配
- 如果文章需要付费或关注，提取不到完整内容
- 提取到的中文内容含有一些零宽空格，需要 `\u200b` 等去除

### WeChat 文章图片

WeChat 文章中的图片通常是 `mmbiz.qpic.cn` 或 `mmbiz.qlogo.cn` 域名，需要在 HTML 中提取：

```python
# 从 HTML 中提取 WeChat 文章图片
img_pattern = re.compile(r'data-src=["\'](https?://mmbiz\.qpic\.cn[^"\']+)["\']')
images = img_pattern.findall(html_text)
```

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
```

### curl SSL issues

If curl returns SSL errors, add `-k` flag:
```
curl -sk "https://..."
```

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
| Paper list / paper roundup | Extract each paper as a separate entry, save to `papers/` |

---

## Output Structure

When saving, use this format:

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

Save to workspace root under the appropriate category directory, e.g.:
- `ai-tools/<slug>.md` — AI tools & coding
- `spring/<slug>.md` — Spring Boot related
- `database/<slug>.md` — Database articles
- `sre/<slug>.md` — SRE & DevOps
- `system-design/<slug>.md` — System design
- `programming/<slug>.md` — Programming languages
- `infrastructure/<slug>.md` — Infrastructure
- `papers/<slug>.md` — Paper notes (not covered by organize.py)

---

## 🖼️ Image Handling

### Image Storage Path

Images from articles are saved to:
```
/home/node/.openclaw/workspace/image/
```

### Naming Convention

```
{article-slug}-{n}.{ext}
```

Where `article-slug` is the markdown filename without `.md`, `n` is a 1-based index, and `ext` is the original extension (`jpg`, `png`, `gif`).

### Link Format in Markdown

```markdown
<!-- Articles use relative paths from their category subdirectory back to image/ -->
![description](../image/article-slug-1.jpg)

<!-- e.g. ai-tools/article.md → ../image/article-slug-1.jpg -->
```

### Image Download for X/Twitter

From fxtwitter JSON response, extract and download media:

```python
import json, subprocess, os

def extract_and_save_images(tweet_data, article_slug):
    images = []
    tweet = tweet_data.get('tweet', {})
    image_dir = '/home/node/.openclaw/workspace/image'
    os.makedirs(image_dir, exist_ok=True)
    
    # Collect media from tweet-level
    if 'media' in tweet and 'all' in tweet['media']:
        for m in tweet['media']['all']:
            if m.get('type', '').startswith('image'):
                images.append({
                    'url': m['url'],
                    'alt': m.get('altText', ''),
                    'ext': m['url'].rsplit('.', 1)[-1].split('?')[0]
                })
    
    # Collect media from article-level content
    if ('article' in tweet and 'content' in tweet['article'] 
            and 'media' in tweet['article']['content']):
        for m in tweet['article']['content']['media']:
            if m.get('type', '').startswith('image'):
                images.append({
                    'url': m['url'],
                    'alt': m.get('altText', ''),
                    'ext': m['url'].rsplit('.', 1)[-1].split('?')[0]
                })
    
    # Deduplicate
    seen_urls = set()
    unique_images = []
    for img in images:
        if img['url'] not in seen_urls:
            seen_urls.add(img['url'])
            unique_images.append(img)
    
    saved = []
    for i, img in enumerate(unique_images):
        filename = f"{article_slug}-{i+1}.{img['ext']}"
        local_path = os.path.join(image_dir, filename)
        subprocess.run(["curl", "-s", "-o", local_path, img['url']],
                       capture_output=True, timeout=15)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 100:
            saved.append({'rel_path': f"../image/{filename}", 'alt': img['alt']})
    return saved
```

### Image Download for General Web Pages

For non-X articles, scan fetched markdown for image URLs, selectively download relevant ones (diagrams, screenshots — skip avatars, icons, ads).

---

## Git Operations

### Commit and Push

After saving the file(s):

```bash
cd /home/node/.openclaw/workspace
git add <files>
git commit -m "feat: add <article-slug> notes"
git push
```

For images added alongside the article:

```bash
cd /home/node/.openclaw/workspace
git add image/ <files>
git commit -m "feat: add <article-slug> notes with images"
git push
```

> Git remote: `https://github.com/Jrink525/knowledges.git`

---

## 📂 Directory Size Management

### Threshold Rule

When any category directory exceeds **20 files**, suggest creating subdirectories for finer-grained organization.

### Current Knowledges subdirectory examples

```
ai-tools/
├── autoresearch/
├── career/
├── codex/
├── enterprise/
└── harness/

spring/     — flat 15 files (no split needed yet)
database/   — flat
sre/        — flat
```

### Implementation

When adding a new file to a directory approaching the threshold:

```python
count = len(list((Path.home() / '.openclaw' / 'workspace' / directory).rglob("*.md")))
if count > 20:
    print(f"  ⚠️  {directory}/ 达到 {count} 篇，建议拆分子目录")
    # Suggest audit
```

---

## Quick Reference: URL Detection

| URL Pattern | Site | Method |
|-------------|------|--------|
| `medium.com/...` | Medium | Freedium mirror |
| `towardsdatascience.com/...` | Medium (custom domain) | Freedium mirror |
| `x.com/.../status/...` | X/Twitter | fxtwitter API |
| `twitter.com/.../status/...` | X/Twitter | fxtwitter API |
| anything else | General | web_fetch |
| `baeldung.com/...` | Cloudflare-protected | JinAI Reader (POST to `r.jina.ai`) |
| `mp.weixin.qq.com/s/...` | WeChat 公众号 | Direct HTML → Python extract `js_content` |
