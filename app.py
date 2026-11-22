# -*- coding: utf-8 -*-
"""biblequote - 聖書（文語訳）の全文から節を引用できるツール。

底本: 文語訳（旧約＝明治元訳 1887／新約＝大正改訳 1917、パブリックドメイン）。
データは data/bible.json（66書・1189章・全節）を起動時に読み込む。
出典: 日本語 Wikisource、補完に CrossWire JapBungo。
"""
import html
import json
import random
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

app = Flask(__name__)

DATA_PATH = Path(__file__).resolve().parent / "data" / "bible.json"

with DATA_PATH.open(encoding="utf-8") as f:
    _DATA = json.load(f)

# 各書: {"name": 書名, "testament": "old"|"new", "chapters": [[節テキスト, ...], ...]}
BOOKS = _DATA["books"]
BOOK_INDEX = {b["name"]: i for i, b in enumerate(BOOKS)}
TOTAL_CHAPTERS = sum(len(b["chapters"]) for b in BOOKS)

SOURCE_NOTE = "聖書 文語訳"
EMPTY_VERSE_NOTE = "（本文は次の節に続きます）"
UNRECORDED_CHAPTER_NOTE = "この章は底本の都合により未収録です"


def is_random_eligible(text):
    """ランダム表示の対象にする節か（空節と「[なし]」は除く）。"""
    return bool(text.strip()) and text.strip() != "[なし]"


# ランダム表示・検索用に全節を平坦化しておく
ALL_VERSES = [
    (bi, ci, vi, text)
    for bi, b in enumerate(BOOKS)
    for ci, chapter in enumerate(b["chapters"])
    for vi, text in enumerate(chapter)
]
RANDOM_POOL = [v for v in ALL_VERSES if is_random_eligible(v[3])]


def ref_label(book_name, chapter, verse):
    """「書名 第X章第Y節」形式の参照表記（chapter / verse は 1 始まり）。"""
    return "{} 第{}章第{}節".format(book_name, chapter, verse)


def quote_text(book_name, chapter, verse, text):
    """引用用のプレーンテキスト（本文＋出典行）。"""
    return text + "\n― " + ref_label(book_name, chapter, verse) + "（" + SOURCE_NOTE + "）"


def get_book(book_idx):
    if 0 <= book_idx < len(BOOKS):
        return BOOKS[book_idx]
    return None


def get_chapter(book, ch):
    """ch は 1 始まり。範囲外なら None。"""
    if 1 <= ch <= len(book["chapters"]):
        return book["chapters"][ch - 1]
    return None


CSS = """
:root { --bg: #faf7f0; --card: #ffffff; --text: #26221c; --border: #999; color-scheme: light; }
html[data-theme="dark"] { --bg: #171512; --card: #23201b; --text: #ece7dc; --border: #6b655c; color-scheme: dark; }
* { box-sizing: border-box; }
body { font-family: "Hiragino Mincho ProN", "Yu Mincho", serif; margin: 0; padding: 16px; line-height: 1.9; background: var(--bg); color: var(--text); }
main { max-width: 760px; margin: 0 auto; }
h1 { font-size: 1.5rem; text-align: center; }
h2 { font-size: 1.15rem; border-bottom: 1px solid var(--border); padding-bottom: 4px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; margin: 16px 0; }
.label { font-weight: bold; font-size: 1.1rem; }
.chap { opacity: 0.75; font-size: 0.9rem; }
button, .btn { font-size: 1rem; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: var(--card); color: var(--text); cursor: pointer; text-decoration: none; display: inline-block; margin: 4px 4px 4px 0; }
button.small { font-size: 0.8rem; padding: 2px 10px; }
input[type=text] { font-size: 1rem; padding: 8px; width: 65%; max-width: 420px; background: var(--card); color: var(--text); border: 1px solid var(--border); border-radius: 6px; }
nav { text-align: center; margin: 12px 0; }
footer { margin-top: 32px; font-size: 0.85rem; opacity: 0.8; text-align: center; }
textarea { width: 100%; min-height: 120px; }
textarea.verse { display: none; }
ul.toc { line-height: 2.0; }
.verse { margin: 10px 0; }
.vnum { font-weight: bold; opacity: 0.7; margin-right: 0.4em; }
.note { opacity: 0.65; font-size: 0.9rem; }
.chlist { line-height: 2.2; }
"""

SCRIPT = """
function copyQuote(id) {
  var el = document.getElementById(id);
  if (navigator.clipboard) { navigator.clipboard.writeText(el.value); }
  else { el.style.display = 'block'; el.select(); document.execCommand('copy'); el.style.display = 'none'; }
  alert('引用文をコピーしました');
}
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
}
function toggleTheme() {
  var cur = document.documentElement.getAttribute('data-theme') || 'light';
  var next = cur === 'dark' ? 'light' : 'dark';
  try { localStorage.setItem('bq-theme', next); } catch (e) {}
  applyTheme(next);
}
(function () {
  var saved = null;
  try { saved = localStorage.getItem('bq-theme'); } catch (e) {}
  if (saved) { applyTheme(saved); }
  else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) { applyTheme('dark'); }
})();
"""

PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title><style>{{ css|safe }}</style></head>
<body><main>
<h1>聖書 引用ツール</h1>
<nav>
<a class="btn" href="{{ url_for('index') }}">ランダム</a>
<a class="btn" href="{{ url_for('books') }}">書名一覧</a>
<button type="button" onclick="toggleTheme()">テーマ切替</button>
</nav>
<form method="get" action="{{ url_for('search') }}" style="text-align:center">
<input type="text" name="q" value="{{ q or '' }}" placeholder="キーワードで節を検索">
<button type="submit">検索</button>
</form>
{{ body|safe }}
<footer>底本：文語訳（旧約＝明治元訳 1887／新約＝大正改訳 1917、パブリックドメイン）。出典：日本語 Wikisource、補完に CrossWire JapBungo。</footer>
</main><script>{{ script|safe }}</script></body></html>"""


def verse_card(bi, ci, vi, text, quote_id):
    """1節分のカード（本文＋参照＋引用コピー）。ci / vi は 0 始まり。"""
    book = BOOKS[bi]
    label = ref_label(book["name"], ci + 1, vi + 1)
    chapter_url = url_for("chapter_page", book_idx=bi, ch=ci + 1)
    return (
        '<div class="card"><div class="label">' + html.escape(label) + "</div>"
        + "<p>" + html.escape(text) + "</p>"
        + '<textarea id="' + quote_id + '" readonly>'
        + html.escape(quote_text(book["name"], ci + 1, vi + 1, text))
        + "</textarea>"
        + '<button onclick="copyQuote(\'' + quote_id + '\')">引用文をコピー</button> '
        + '<a class="btn" href="' + chapter_url + '">この章のページ</a>'
        + "</div>"
    )


def render_page(title, body, q=None):
    return render_template_string(
        PAGE, title=title, css=CSS, script=SCRIPT, body=body, q=q
    )


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    bi, ci, vi, text = random.choice(RANDOM_POOL)
    body = "<h2>今日の一節（ランダム）</h2>" + verse_card(bi, ci, vi, text, "q0")
    body += '<p><a class="btn" href="' + url_for("index") + '">別の節を表示</a></p>'
    return render_page("聖書 引用ツール", body)


@app.route("/books")
def books():
    parts = ["<h2>書名一覧（全66書）</h2>"]
    for testament, heading in (("old", "旧約聖書（39書）"), ("new", "新約聖書（27書）")):
        parts.append("<h2>" + heading + "</h2><ul class=\"toc\">")
        for bi, b in enumerate(BOOKS):
            if b["testament"] != testament:
                continue
            parts.append(
                '<li><a href="' + url_for("book_page", book_idx=bi) + '">'
                + html.escape(b["name"]) + "</a>（全" + str(len(b["chapters"])) + "章）</li>"
            )
        parts.append("</ul>")
    return render_page("書名一覧", "".join(parts))


@app.route("/book/<int:book_idx>")
def book_page(book_idx):
    book = get_book(book_idx)
    if book is None:
        return redirect(url_for("books"))
    parts = ["<h2>" + html.escape(book["name"]) + "（全" + str(len(book["chapters"])) + "章）</h2>"]
    parts.append('<p class="chlist">')
    for ch in range(1, len(book["chapters"]) + 1):
        parts.append(
            '<a class="btn" href="'
            + url_for("chapter_page", book_idx=book_idx, ch=ch)
            + '">第' + str(ch) + "章</a>"
        )
    parts.append("</p>")
    return render_page(book["name"], "".join(parts))


@app.route("/book/<int:book_idx>/chapter/<int:ch>")
def chapter_page(book_idx, ch):
    book = get_book(book_idx)
    if book is None:
        return redirect(url_for("books"))
    chapter = get_chapter(book, ch)
    if chapter is None:
        return redirect(url_for("book_page", book_idx=book_idx))
    title = book["name"] + " 第" + str(ch) + "章"
    parts = ["<h2>" + html.escape(title) + "</h2>"]
    if not chapter:
        parts.append('<p class="note">' + UNRECORDED_CHAPTER_NOTE + "</p>")
    else:
        for vi, text in enumerate(chapter):
            anchor = "v" + str(vi + 1)
            if text == "":
                body = '<span class="note">' + EMPTY_VERSE_NOTE + "</span>"
                copy_btn = ""
            else:
                body = html.escape(text)
                qid = "q" + str(vi + 1)
                copy_btn = (
                    '<textarea class="verse" id="' + qid + '" readonly>'
                    + html.escape(quote_text(book["name"], ch, vi + 1, text))
                    + "</textarea>"
                    + '<button class="small" onclick="copyQuote(\'' + qid + '\')">コピー</button>'
                )
            parts.append(
                '<div class="verse" id="' + anchor + '"><span class="vnum">'
                + str(vi + 1) + "</span>" + body + " " + copy_btn + "</div>"
            )
    nav = ""
    if ch > 1:
        nav += '<a class="btn" href="' + url_for("chapter_page", book_idx=book_idx, ch=ch - 1) + '">前の章</a>'
    if ch < len(book["chapters"]):
        nav += '<a class="btn" href="' + url_for("chapter_page", book_idx=book_idx, ch=ch + 1) + '">次の章</a>'
    nav += '<a class="btn" href="' + url_for("book_page", book_idx=book_idx) + '">章一覧へ</a>'
    parts.append("<nav>" + nav + "</nav>")
    return render_page(title, "".join(parts))


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return redirect(url_for("index"))
    hits = [v for v in ALL_VERSES if v[3] and q in v[3]]
    total = len(hits)
    shown = hits[:100]
    body = "<h2>「" + html.escape(q) + "」の検索結果：" + str(total) + "件</h2>"
    if total > 100:
        body += '<p class="note">表示は最初の100件までです。</p>'
    if not shown:
        body += "<p>見つかりませんでした。</p>"
    for bi, ci, vi, text in shown:
        label = ref_label(BOOKS[bi]["name"], ci + 1, vi + 1)
        url = url_for("chapter_page", book_idx=bi, ch=ci + 1) + "#v" + str(vi + 1)
        snippet = text if len(text) <= 120 else text[:120] + "…"
        body += (
            '<div class="card"><div class="label"><a href="' + url + '">'
            + html.escape(label) + "</a></div><p>" + html.escape(snippet) + "</p></div>"
        )
    return render_page("検索結果", body, q=q)


@app.route("/api/random")
def api_random():
    bi, ci, vi, text = random.choice(RANDOM_POOL)
    return jsonify({
        "book": BOOKS[bi]["name"],
        "chapter": ci + 1,
        "verse": vi + 1,
        "text": text,
    })


@app.route("/api/verse")
def api_verse():
    name = request.args.get("book") or ""
    try:
        chapter = int(request.args.get("chapter") or "")
        verse = int(request.args.get("verse") or "")
    except ValueError:
        return jsonify({"error": "not found"}), 404
    bi = BOOK_INDEX.get(name)
    if bi is None:
        return jsonify({"error": "not found"}), 404
    chapter_data = get_chapter(BOOKS[bi], chapter)
    if chapter_data is None or not (1 <= verse <= len(chapter_data)):
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "book": name,
        "chapter": chapter,
        "verse": verse,
        "text": chapter_data[verse - 1],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
