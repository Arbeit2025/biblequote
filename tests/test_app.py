# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as bible


class TestData(unittest.TestCase):
    def test_books_and_chapters(self):
        self.assertEqual(len(bible.BOOKS), 66)
        self.assertEqual(bible.TOTAL_CHAPTERS, 1189)
        self.assertEqual(
            sum(len(b["chapters"]) for b in bible.BOOKS), 1189)

    def test_testament_split(self):
        old = [b for b in bible.BOOKS if b["testament"] == "old"]
        new = [b for b in bible.BOOKS if b["testament"] == "new"]
        self.assertEqual(len(old), 39)
        self.assertEqual(len(new), 27)


class TestPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = bible.app.test_client()

    def test_index(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    def test_books(self):
        res = self.client.get("/books")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("創世記", body)
        self.assertIn("ヨハネの黙示録", body)

    def test_chapter_view(self):
        res = self.client.get("/book/0/chapter/1")
        self.assertEqual(res.status_code, 200)
        self.assertIn("元始に神天地を創造たまへり",
                      res.get_data(as_text=True))

    def test_empty_chapter_isaiah_1(self):
        idx = bible.BOOK_INDEX["イザヤ書"]
        res = self.client.get("/book/{}/chapter/1".format(idx))
        self.assertEqual(res.status_code, 200)
        self.assertIn("未収録", res.get_data(as_text=True))

    def test_book_page(self):
        res = self.client.get("/book/0")
        self.assertEqual(res.status_code, 200)
        self.assertIn("第50章", res.get_data(as_text=True))

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"status": "ok"})


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = bible.app.test_client()

    def test_api_random(self):
        for _ in range(20):
            res = self.client.get("/api/random")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["text"].strip())
            self.assertNotEqual(data["text"].strip(), "[なし]")
            self.assertIn(data["book"], bible.BOOK_INDEX)
            self.assertGreaterEqual(data["chapter"], 1)
            self.assertGreaterEqual(data["verse"], 1)

    def test_api_verse_genesis_1_1(self):
        res = self.client.get(
            "/api/verse",
            query_string={"book": "創世記", "chapter": 1, "verse": 1})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        # 明治元訳の創世記1:1は「元始に…」で始まる
        self.assertTrue(data["text"].startswith("元始に"))
        self.assertEqual(data["book"], "創世記")
        self.assertEqual(data["chapter"], 1)
        self.assertEqual(data["verse"], 1)

    def test_api_verse_not_found(self):
        res = self.client.get(
            "/api/verse",
            query_string={"book": "存在しない書", "chapter": 1, "verse": 1})
        self.assertEqual(res.status_code, 404)
        res = self.client.get(
            "/api/verse",
            query_string={"book": "創世記", "chapter": 999, "verse": 1})
        self.assertEqual(res.status_code, 404)


class TestSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = bible.app.test_client()

    def test_search_hits(self):
        res = self.client.get("/search", query_string={"q": "初めに"})
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("検索結果", body)
        self.assertNotIn("0件", body)

    def test_search_no_hits(self):
        res = self.client.get(
            "/search", query_string={"q": "ぜったいに存在しない語句xyz"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("0件", res.get_data(as_text=True))

    def test_theme_toggle_wired(self):
        # テーマ切替は CSS変数 + data-theme + localStorage で実際に色が変わる方式
        res = self.client.get("/")
        body = res.get_data(as_text=True)
        self.assertIn('html[data-theme="dark"]', body)
        self.assertIn("--bg:", body)
        self.assertIn("background: var(--bg)", body)
        self.assertIn("toggleTheme", body)
        self.assertIn("localStorage.setItem('bq-theme'", body)


if __name__ == "__main__":
    unittest.main()
