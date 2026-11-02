# X Article 图片与内嵌推文

## 定位每一张图

- `atomic` 块 `data` 为空但 `entityRanges` 非空：实体是 `type: MEDIA`，带 `data.mediaItems[].mediaId`，与 `article.media_entities[].media_id` 对应。把这个 id 解析成 `pbs.twimg.com` URL，放在该块的位置——块序就是版面顺序，不需要猜。
- `atomic` 块 `data` 与 `entityRanges` 都为空：图片只存在于 `article.cover_media.media_info.original_img_url` 和 `article.media_entities[]` 里。这些放进一个 `## 附：原文配图（按抓取顺序）` 小节，并在 `## 局限` 写明小节与原文位置的对应无法核实；按猜测的标题分配图片等于把图说张冠李戴。
- `media_entities` 是上传顺序，不是版面顺序。按 id 手写下载列表会把图整体错位，必须按抽取出的位置序列生成。

## 按块序下载

先用抽取脚本打印 `[IMG] <mediaId>` 占位（见 SKILL.md 第 1 步），然后一条命令做完定位、下载、编号、魔数校验与引用输出：

```bash
python3 scripts/x-article-images.py tweet.json article.txt <slug> image
```

它按正文出现序命名 `image/<slug>-<n>.<ext>`，末行打印 `markers N | downloaded N`，两数不等即以退出码 1 结束。不要先把图按 `media_entities` 顺序下到临时目录再复制改名：两套编号一旦漂移，复制循环只会静默搬过去一部分图，而且不报错。没有脚本时用下面的等价循环（同样按 `order` 枚举编号）：

```bash
python3 - <<'EOF'
import json, re, subprocess, os
a = json.load(open('tweet.json'))['tweet']['article']
urls = {m['media_id']: (m.get('media_info') or {}).get('original_img_url') for m in a['media_entities']}
order = re.findall(r'\[IMG\] (\d+)', open('article.txt').read())
for i, mid in enumerate(order, 1):
    u = urls.get(mid)
    if not u:
        print('NO URL', mid); continue
    out = 'image/<slug>-%d%s' % (i, '.png' if u.endswith('.png') else '.jpg')
    for _ in range(3):
        subprocess.run(['curl', '-sL', '--max-time', '40', '-A', 'Mozilla/5.0', u, '-o', out])
        if os.path.getsize(out) > 2000: break
    print(out, os.path.getsize(out))
EOF
```

文件号就是正文里的出现序号，正文按 `image/<slug>-<n>.<ext>` 引用即可，不需要再看图猜顺序。

## 校验

每张图检查魔数：JPEG `\xff\xd8\xff`，PNG `\x89PNG\r\n\x1a\n`。0 字节或头部不对就是抓取失败，重试；三次仍失败就把这张图从正文删掉并在 `## 局限` 说明，不要留一个空文件或死链。

## 无图说与无视觉

原文没给图说时，alt 写成「一句复述相邻段落已写明的事实 +（原文配图，无图说）」，例如 `![图 1：累计完成 70 亿 AWU（原文配图，无图说）](...)`。图在页面上仍可导航，而事实来自正文而不是来自看图。

不要描述界面元素、布局、颜色，不要从图里读数，不要写相邻段落没有的信息：这些都会让 `## 局限` 里那句「图内内容未核实」变成假话。视觉工具读图失败一次就停止尝试，按未核实处理；只有确实读到图，才写纯视觉描述。

`Image model failed (<provider/model>): 400 The supported API model names are ...` 是网关的视觉路由没配好，不是网络抖动：原参数重试、换图重试都是同一结果，不要为每张图再试一次。这种环境下全部图按「原文配图，无图说」处理，并在 `## 局限` 写明图内内容未核实。图片是不是真的下载成功，用 Python 读文件头判（容器内常没有 `file` 命令）：JPEG `\xff\xd8\xff`、PNG `\x89PNG\r\n\x1a\n`。

## 编号与引用

图注编号是手写的，插入或删掉一张图后前面的编号就会重号。写完正文跑一遍重排，让最后一个编号等于图片文件数：

```bash
python3 - <<'EOF'
import re, glob
slug = '<slug>'
p = 'ai-tools/harness/%s.md' % slug
lines = open(p).read().split('\n')
n = 0
for i, l in enumerate(lines):
    if re.match(r'^\*图 \d+：', l):
        n += 1
        lines[i] = re.sub(r'^\*图 \d+：', f'*图 {n}：', l)
open(p, 'w').write('\n'.join(lines))
print('captions:', n, 'files:', len(glob.glob('image/%s-*' % slug)))
EOF
```

两个数不等就是有图没放进正文或多放了图：`grep -oE 'image/<slug>-[0-9]+' <page>.md | sort -u` 与 `ls image/<slug>-*` 逐项比对，缺的补进对应小节，多出来的删文件而不是在局限里提一句。

## 内嵌推文

`type: TWEET` 的实体是内嵌推文，不是配图：它带 `data.tweetId`，通常挂视频，产品与架构类长文把演示放在这里。用 `curl -s "https://api.fxtwitter.com/i/status/<id>"` 逐个解析（`/i/` 形式不需要用户名），记下作者 handle 与开头一句，正文写清每条内嵌推文展示了什么，而不是只报条数。按「原文内嵌推文」引用；媒体是视频且未观看时，在 `## 局限` 写明，不要描述界面。
