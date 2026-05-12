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
web_fetch(url="https://freedium.cfd/https://medium.com/...", maxChars=100000)
```

**Fallback chain** (try in order):
```
1. https://freedium.cfd/https://medium.com/...
2. https://freedium-mirror.cfd/https://medium.com/...
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

## GitHub Push

After saving to `knowledges/`:

```bash
cd /home/node/.openclaw/workspace/knowledges
python3 _organize.py
```

This auto-classifies, updates README, and pushes to GitHub. No manual git steps needed.

---

## 📂 Directory Size Management

### Threshold Rule

When any knowledge base directory (including subdirectories) exceeds **20 files**, automatically trigger a re-classification/split into finer-grained subdirectories.

### MECE 分类原则 (核心红线)

拆分时必须遵循 **MECE (Mutually Exclusive, Collectively Exhaustive)**：

| 原则 | 含义 | 反面教材 |
|------|------|---------|
| **Mutually Exclusive** | 子目录之间不重叠，一篇文章只能归属一个子目录 | ❌ `java/` 里有 Spring 文章，`spring/` 里也有 → 一篇文章两个位置 |
| **Collectively Exhaustive** | 所有文章都有归属，没有遗漏 | ❌ `java/` 拆成 `jvm/` + `concurrency/`，但 `build-tools/` 的文章没地方放 |

#### 判断文章归属的决策树

```
文章应该放哪个子目录？
├── 文章主要讲的是具体技术 X → 放 X 的子目录
│   （如果 X 有多个子话题，往下拆分）
└── 文章横跨多个技术 →
    ├── 有主次关系？→ 放主要内容归属的子目录
    └── 无主次关系？→ 放父级上层目录
```

> **遇重叠则归主，无主次则归父。** 拆分时一篇文章只能出现在一个位置，严禁同一文件在多个子目录间

### 计算机语言/技术领域分类常识

拆分时使用业内通用的命名约定，而非创造新词：

| 技术领域 | 标准子目录命名方案 | 说明 |
|---------|-----------------|------|
| **编程语言** | `languages/<lang>/` | 按语言分：`java/`, `python/`, `go/`, `typescript/`。子话题按：`jvm/`, `concurrency/`, `build-tools/`, `testing/` |
| **框架** | `frameworks/<framework>/` | 框架名即目录名：`spring/`, `react/`, `langchain/`。Spring 子话题：`boot/`, `cloud/`, `security/`, `data/`, `testing/` |
| **数据库** | `database/<type>/` | `relational/` (MySQL/PostgreSQL), `cache/` (Redis/Memcached), `nosql/` (MongoDB/Cassandra), `message-queue/` (Kafka/RabbitMQ) |
| **AI/ML** | `ai/<subfield>/` | `agents/` (Agent 架构、框架), `ml/` (训练、模型), `llm/` (大模型、推理), `tools/` (Claude Code/Copilot/Cursor), `engineering/` (工程实践、Harness) |
| **基础设施** | `infra/<layer>/` | `cloud/`, `container/`, `cicd/`, `monitoring/`, `network/`, `security/` |
| **系统设计** | `system-design/<domain>/` | `distributed/`, `consensus/`, `consistency/`, `storage/`, `architecture-patterns/` |
| **SRE/DevOps** | `sre/<practice>/` | `incident-response/`, `observability/`, `capacity/`, `reliability-patterns/` |

#### 命名红线

| ❌ 错误 | ✅ 正确 | 为什么 |
|---------|---------|--------|
| `java-programming/` | `java/` | 不要冗余后缀，行业就叫 java |
| `java-spring-boot/` | `spring/boot/` | Spring Boot 是 Spring 的子话题，不是 Java 的 |
| `aiframework/` | `ai/agents/` | 用完整通用名，不用缩写私货 |
| `LangChain4j vs Spring AI/` | 放父目录 `ai/agents/` | 对比类文章横跨多主题，归上级最合适的目录 |
| `Claude-DeepSeek/` | `ai/tools/` | 工具名随时间变，按功能归类 |

### 拆分执行流程

```
目录超 20 篇
  │
  ▼
1. 全面盘点目录内所有文章的主题分布
2. 按 MECE 原则划分子目录边界（最多 5-8 个子目录）
3. 确保子目录命名符合行业惯例（参考上表）
4. 逐篇归类，交叉文章按决策树处理
5. 移动文件到新子目录
6. 更新 _organize.py 的 DOMAIN_PROFILES（添加子目录关键词映射）
7. 运行 _organize.py 验证分类正确
8. 检查 README.md 确认新结构
```

### Implementation (in _organize.py)

```python
# Threshold check after classification
THRESHOLD = 20
for directory in classified_dirs:
    count = len(list((KNOWLEDGES_DIR / directory).rglob("*.md")))
    if count > THRESHOLD:
        print(f"  ⚠️  {directory}/ 达到 {count} 篇 (> {THRESHOLD}), 需启动 MECE 拆分！")
        print(f"     当前子目录: {[d.name for d in (KNOWLEDGES_DIR/directory).iterdir() if d.is_dir()]}")
        print(f"     建议: 按 {directory} 主题聚类 → 创建 MECE 子目录 → 逐篇归类")
```

### When It Runs

- After every `_organize.py` run (implicitly checked)
- Also check explicitly when adding files manually
- The threshold is **per-directory**, not total — `ai/agents/` 18 篇 + `spring/` 5 篇 = 各自独立计算
- 告警意味着下一轮手动拆分，不是自动执行（需人工判断 MECE 边界）

---

## Quick Reference: URL Detection

| URL Pattern | Site | Method |
|-------------|------|--------|
| `medium.com/...` | Medium | Freedium mirror |
| `towardsdatascience.com/...` | Medium (custom domain) | Freedium mirror |
| `x.com/.../status/...` | X/Twitter | fxtwitter API |
| `twitter.com/.../status/...` | X/Twitter | fxtwitter API |
| anything else | General | web_fetch |
