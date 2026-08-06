#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一体化发布器：登录 + 发布 在同一个有头浏览器会话内完成。
微信会话极脆，关浏览器/换实例/cookie 重注都会被踢，所以必须一次会话走完。

用法：
  python wechat_auto.py --article <md> --cover <png> --img1 <png> --img2 <png> --img3 <png> --title "..." --author "..." --summary "..."

流程：
  1. 有头打开 mp 后台
  2. 若未登录 -> 截图二维码，轮询扫码（最多 300s）
  3. 登录后同会话内：点「草稿箱」->「新建图文消息」
  4. 填标题/作者/摘要/正文；上传 3 张配图 + 封面
  5. 保存草稿，截图 published.png
"""
import argparse
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
DEBUG = BASE / "debug"
DEBUG.mkdir(parents=True, exist_ok=True)
MP_HOME = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(s: str) -> str:
    s = _esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s


def md_to_html(md: str):
    lines = md.splitlines()
    title = ""
    body = []
    images = []
    last_heading = ""
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if i == 0 and ln.startswith("# "):
            title = ln[2:].strip()
            i += 1
            continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)\s*$", ln.strip())
        if m:
            alt = m.group(1).strip()
            path = m.group(2).strip()
            images.append({"after_heading": last_heading, "path": path, "alt": alt})
            # 插入一个醒目的占位块，方便手动/自动补图；不会混在正文文字里
            body.append(
                f'<div data-wechat-img-placeholder="{path}" style="border:2px dashed #d97706; border-radius:8px; padding:16px; margin:16px 0; background:#fffbeb; text-align:center; color:#92400e; font-size:14px;">'
                f'📷 <strong>配图位置：{_esc(alt)}</strong><br/>'
                f'<span style="color:#666; font-size:12px;">图片路径：{_esc(path)}</span>'
                f'</div>'
            )
            i += 1
            continue
        if ln.startswith("## "):
            last_heading = ln[3:].strip()
            body.append(f"<h2>{_esc(last_heading)}</h2>")
        elif ln.startswith("### "):
            last_heading = ln[4:].strip()
            body.append(f"<h3>{_esc(last_heading)}</h3>")
        elif ln.strip() == "---":
            body.append("<hr/>")
        elif ln.startswith("> "):
            body.append(f"<blockquote>{_inline(ln[2:].strip())}</blockquote>")
        elif ln.startswith("- "):
            items = []
            while i < n and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:].strip())}</li>")
                i += 1
            body.append(f"<ul>{''.join(items)}</ul>")
            continue
        elif ln.strip() == "":
            pass
        else:
            body.append(f"<p>{_inline(ln.strip())}</p>")
        i += 1
    return title, "".join(body), images


def is_logged(page) -> bool:
    try:
        return "WEME" in page.evaluate("() => document.body.innerText") or "草稿箱" in page.evaluate("() => document.body.innerText")
    except Exception:
        return False


def do_login(page, timeout=300):
    page.screenshot(path=str(DEBUG / "login.png"))
    print(f"QR_READY:{DEBUG / 'login.png'}")
    print("WAITING_FOR_SCAN ... 请微信扫码并点「确认登录」")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_logged(page):
            print("LOGIN_OK")
            return True
        page.wait_for_timeout(2000)
    print("LOGIN_TIMEOUT")
    return False


def fill_title(page, title):
    # 优先 input[placeholder*=标题]，其次 div#title contenteditable
    for sel in ['input[placeholder*="标题"]', 'textarea[placeholder*="标题"]', '#title', 'div.title[contenteditable]']:
        try:
            el = page.query_selector(sel)
            if el:
                if el.get_attribute("contenteditable") == "true":
                    el.click()
                    el.fill(title)
                else:
                    el.click()
                    el.fill(title)
                print(f"TITLE_OK via {sel}")
                return
        except Exception:
            pass
    # 兜底：用 JS 找 placeholder 含「标题」的元素
    res = page.evaluate(
        """(title) => {
            const el = [...document.querySelectorAll('input,textarea,[contenteditable]')].find(e => /标题/.test(e.placeholder||e.getAttribute('placeholder')||''));
            if(!el) return 'NO_TITLE';
            el.focus();
            if(el.tagName==='INPUT'||el.tagName==='TEXTAREA') el.value=title;
            else el.innerText=title;
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return 'OK';
        }""",
        title,
    )
    print(f"TITLE_JS: {res}")


def fill_author(page, author):
    try:
        el = page.query_selector('input[placeholder*="作者"]')
        if el:
            el.fill(author)
            print("AUTHOR_OK")
            return
    except Exception:
        pass
    print("AUTHOR_SKIP: 无作者框（可选项，忽略）")


def fill_digest(page, digest):
    if not digest:
        return
    try:
        link = page.get_by_text("摘要", exact=False).first
        if link.count() > 0:
            link.click(timeout=3000)
            page.wait_for_timeout(500)
    except Exception:
        pass
    try:
        el = page.query_selector('textarea[placeholder*="摘要"]')
        if el:
            el.fill(digest)
            print("DIGEST_OK")
            return
    except Exception:
        pass
    print("DIGEST_SKIP: 未找到摘要框")


def fill_body(page, html):
    res = page.evaluate(
        """(html) => {
            const ces = Array.from(document.querySelectorAll('[contenteditable="true"]'));
            if(!ces.length) return 'NO_CE';
            // 排除标题区（id=title 或 placeholder 含标题）
            const bodyEl = ces.find(e => !(e.id==='title') && !/标题/.test(e.getAttribute('placeholder')||'')) 
                        || ces.sort((a,b)=> (b.innerText||'').length - (a.innerText||'').length)[0];
            if(!bodyEl) return 'NO_BODY';
            bodyEl.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertHTML', false, html);
            return 'OK:' + (bodyEl.className||bodyEl.id||'ce');
        }""",
        html,
    )
    print(f"BODY: {res}")


def insert_image(page, img):
    alt = img.get("alt", "")
    path = img["path"]
    try:
        btn = page.locator('[data-name="image"], button:has-text("图片"), [title="图片"]').first
        if btn.count() == 0:
            print(f"IMG_SKIP {alt}: 找不到图片按钮")
            return
        with page.expect_file_chooser(timeout=8000) as fc:
            btn.click(timeout=5000)
        fc.value.set_files(path)
        # 等待上传完成：模态里出现该图缩略图或「确定」可点
        page.wait_for_timeout(5000)
        # 点「确定」插入
        ok = page.get_by_text("确定", exact=False).last
        if ok.count() > 0:
            ok.click(timeout=5000)
        page.wait_for_timeout(2000)
        print(f"IMG_OK {alt}")
    except Exception as e:
        print(f"IMG_FAIL {alt}: {e}")


def set_cover(page, cover):
    try:
        btn = page.locator('text=上传封面, button:has-text("封面"), [title="封面"]').first
        if btn.count() == 0:
            print("COVER_SKIP: 找不到封面按钮")
            return
        with page.expect_file_chooser(timeout=8000) as fc:
            btn.click(timeout=5000)
        fc.value.set_files(cover)
        page.wait_for_timeout(4000)
        print("COVER_OK")
    except Exception as e:
        print(f"COVER_FAIL: {e}")


def save_draft(page):
    try:
        # 优先「保存」(保存草稿)
        btn = page.get_by_text("保存", exact=False).first
        if btn.count() > 0:
            btn.click(timeout=5000)
            page.wait_for_timeout(2500)
            print("SAVED")
            return
    except Exception as e:
        print(f"SAVE_FAIL: {e}")
    print("SAVE_NOT_FOUND")


def run(args):
    article = Path(args.article).resolve()
    md = article.read_text(encoding="utf-8")
    title, html, images = md_to_html(md)
    title = args.title or title
    author = args.author or "湘月"
    digest = args.summary or ""

    with sync_playwright() as p:
        b = p.chromium.launch(headless=False)
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        page = ctx.new_page()
        page.goto(MP_HOME, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        if not is_logged(page):
            if not do_login(page, timeout=300):
                print("ABORT: 登录失败")
                b.close()
                return

        # 提取 token，直接导航到图文编辑器
        m = re.search(r"token=(\d+)", page.url)
        token = m.group(1) if m else ""
        if not token:
            print("ABORT: 未拿到 token")
            b.close()
            return
        page.goto(
            f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=10&isMul=0&isNew=1&share=1&lang=zh_CN&token={token}",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        page.wait_for_timeout(8000)
        if "loginpage" in page.url or "请重新登录" in page.evaluate("() => document.body.innerText"):
            print("SESSION_BROKE_AT_EDITOR")
            b.close()
            return
        page.screenshot(path=str(DEBUG / "editor.png"))

        if "loginpage" in page.url or "请重新登录" in page.evaluate("() => document.body.innerText"):
            print("SESSION_BROKE_AT_EDITOR; 会话在进编辑器时失效，请重试")
            b.close()
            return

        page.screenshot(path=str(DEBUG / "editor.png"))
        # 导出选择器供校准
        try:
            rep = page.evaluate("""() => {
                const o={inputs:[],ce:[],btns:[]};
                document.querySelectorAll('input,textarea').forEach(e=>o.inputs.push({ph:e.placeholder||'',id:e.id||'',cls:(e.className||'').slice(0,40)}));
                document.querySelectorAll('[contenteditable=true]').forEach(e=>o.ce.push({id:e.id||'',cls:(e.className||'').slice(0,50)}));
                document.querySelectorAll('button').forEach(e=>{const t=(e.textContent||'').trim(); if(t)o.btns.push(t.slice(0,20));});
                return o;
            }""")
            (DEBUG / "editor_dump.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        # 填内容
        fill_title(page, title)
        fill_author(page, author)
        fill_digest(page, digest)
        fill_body(page, html)

        # 配图（尽力）
        for img in images:
            insert_image(page, img)
        # 封面（尽力）
        if args.cover:
            set_cover(page, args.cover)

        page.wait_for_timeout(1500)
        page.screenshot(path=str(DEBUG / "before_save.png"))
        # 保存草稿
        save_draft(page)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(DEBUG / "published.png"))
        print("PUBLISH_DONE; 见 debug/published.png")
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--article", required=True)
    ap.add_argument("--cover", default="")
    ap.add_argument("--img1", default="")
    ap.add_argument("--img2", default="")
    ap.add_argument("--img3", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--summary", default="")
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
