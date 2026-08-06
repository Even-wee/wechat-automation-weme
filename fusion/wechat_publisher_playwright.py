#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat 公众号草稿箱发布器（个人订阅号 / 无 API 权限专用 · Playwright 自动化）

三段式子命令：
  login    打开 mp.weixin.qq.com，截图二维码，轮询登录，保存 cookie 到 wechat_cookies.json
  inspect  用 cookie 进入编辑器，导出关键选择器 + 截图（editor.png），供校准 publish 用
  publish  用 cookie 进入编辑器，填标题/作者/摘要/正文/配图/封面，保存草稿

说明：
- 微信内容管理 API（draft/add）仅对「已认证」号开放；个人未认证号只能走浏览器自动化。
- 首次 login 需要用户用微信扫码确认；之后 cookie 可复用一段时间，publish 免扫码。
- 正文 HTML 由 Markdown 转换（标题/加粗/列表/引用/分隔），图片单独通过编辑器上传按钮插入。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
COOKIE_FILE = BASE / "wechat_cookies.json"
SELECTOR_FILE = BASE / "editor_selectors.json"
DEBUG_DIR = BASE / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

MP_HOME = "https://mp.weixin.qq.com/"

# ---------------------------------------------------------------------------
# Markdown -> 微信内联 HTML（正文，不含图片；图片稍后单独上传）
# ---------------------------------------------------------------------------

def md_to_html(md: str):
    """返回 (html, images)。images: [{after_heading, path, alt}]"""
    lines = md.splitlines()
    title = ""
    body_lines = []
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
        # 图片
        m = re.match(r"^!\[(.*?)\]\((.*?)\)\s*$", ln.strip())
        if m:
            images.append({"after_heading": last_heading, "path": m.group(2).strip(), "alt": m.group(1).strip()})
            i += 1
            continue
        if ln.startswith("## "):
            last_heading = ln[3:].strip()
            body_lines.append(f"<h2>{_esc(last_heading)}</h2>")
        elif ln.startswith("### "):
            last_heading = ln[4:].strip()
            body_lines.append(f"<h3>{_esc(last_heading)}</h3>")
        elif ln.strip() == "---":
            body_lines.append("<hr/>")
        elif ln.startswith("> "):
            body_lines.append(f"<blockquote>{_inline(ln[2:].strip())}</blockquote>")
        elif ln.startswith("- "):
            # 收集连续列表
            items = []
            while i < n and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:].strip())}</li>")
                i += 1
            body_lines.append(f"<ul>{''.join(items)}</ul>")
            continue
        elif ln.strip() == "":
            pass
        else:
            body_lines.append(f"<p>{_inline(ln.strip())}</p>")
        i += 1
    html = "".join(body_lines)
    return title, html, images


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(s: str) -> str:
    s = _esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------

def cmd_login(args):
    qr_out = DEBUG_DIR / "qr.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not getattr(args, "headed", False))
        ctx = browser.new_context(viewport={"width": 1000, "height": 800}, device_scale_factor=2)
        page = ctx.new_page()
        try:
            page.goto(MP_HOME, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"GOTO_WARN: {e}")
        page.wait_for_timeout(3000)
        # 整页截图（必定含二维码），作为兜底
        page.screenshot(path=str(DEBUG_DIR / "login.png"), full_page=False)
        qr_out = DEBUG_DIR / "login.png"
        # 尝试定位二维码图片元素并单独截图（更干净）
        qr_el = None
        for sel in ["#wxLoginPanel img", ".login__type__container img", "img[src*='qrcode']", "canvas", ".login_qrcode img", "#login_container img"]:
            try:
                el = page.query_selector(sel)
                if el:
                    qr_el = el
                    break
            except Exception:
                pass
        if qr_el is not None:
            try:
                qr_el.screenshot(path=str(DEBUG_DIR / "qr.png"))
                qr_out = DEBUG_DIR / "qr.png"
            except Exception:
                pass
        print(f"QR_READY:{qr_out}")
        # 轮询登录：等待跳转到 home 或首页特征元素出现（最多 600s）
        print("WAITING_FOR_SCAN ... 请用微信扫码并在手机上点「确认登录」（最多 600s）")
        logged_in = False
        deadline = time.time() + 600
        while time.time() < deadline:
            try:
                if "cgi-bin/home" in page.url or page.locator("text=草稿箱").count() > 0 or page.locator("text=首页").count() > 0:
                    logged_in = True
                    break
            except Exception:
                pass
            page.wait_for_timeout(3000)
        if logged_in:
            ctx.cookies().__class__  # noop
            cookies = ctx.cookies()
            COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
            print(f"LOGIN_OK; cookies saved -> {COOKIE_FILE} ({len(cookies)} items)")
            # 顺便打开编辑器，导出选择器
            _open_editor_and_dump(ctx, page)
        else:
            print("LOGIN_TIMEOUT; cookie 未保存，请重试")
        browser.close()


def _open_editor_and_dump(ctx, page):
    """登录后尝试进入图文编辑器，导出选择器 + 截图。"""
    try:
        # 新版首页：点「草稿箱」->「写新图文」；或首页直接有「新建图文」
        clicked = False
        for text in ["新建图文", "写新图文", "新的创作"]:
            try:
                btn = page.get_by_text(text, exact=False).first
                if btn.count() > 0:
                    btn.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            print("EDITOR_OPEN: 未自动找到「新建图文」按钮，稍后 inspect 手动处理")
            return
        page.wait_for_timeout(4000)
        page.wait_for_load_state("domcontentloaded")
        page.screenshot(path=str(DEBUG_DIR / "editor.png"), full_page=False)
        report = _dump_editor_dom(page)
        SELECTOR_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"EDITOR_DUMP_OK -> {SELECTOR_FILE}")
    except Exception as e:
        print(f"EDITOR_DUMP_FAIL: {e}")


def _dump_editor_dom(page):
    """导出标题/作者/摘要/正文/图片按钮/封面的候选选择器。"""
    return page.evaluate(
        """() => {
            const out = {title: [], author: [], digest: [], body: [], imageBtn: [], cover: []};
            document.querySelectorAll('input,textarea').forEach(el => {
                const id = el.id || '';
                const ph = el.placeholder || '';
                const cls = el.className || '';
                const label = (el.previousElementSibling && el.previousElementSibling.textContent || '').trim().slice(0,20);
                if (/title/i.test(id+ph+cls+label)) out.title.push({id, cls, ph, label});
                if (/author|作者/i.test(id+ph+cls+label)) out.author.push({id, cls, ph, label});
                if (/digest|摘要/i.test(id+ph+cls+label)) out.digest.push({id, cls, ph, label});
            });
            document.querySelectorAll('[contenteditable="true"],.edui-body-container,#ueditor_0,.weui-desktop-media__content [contenteditable]').forEach(el => {
                out.body.push({cls: el.className||'', tag: el.tagName});
            });
            document.querySelectorAll('[title],button,[data-name]').forEach(el => {
                const t = (el.getAttribute('title')||'') + ' ' + (el.getAttribute('data-name')||'') + ' ' + (el.textContent||'');
                if (/图片|image/i.test(t)) out.imageBtn.push({title: el.getAttribute('title'), dataName: el.getAttribute('data-name'), cls: el.className, text: (el.textContent||'').trim().slice(0,20)});
                if (/封面|cover/i.test(t)) out.cover.push({title: el.getAttribute('title'), cls: el.className, text: (el.textContent||'').trim().slice(0,20)});
            });
            return out;
        }"""
    )


# ---------------------------------------------------------------------------
# 检查（已登录 cookie 下打开编辑器并导出选择器）
# ---------------------------------------------------------------------------

def cmd_inspect(args):
    if not COOKIE_FILE.exists():
        print("NO_COOKIE; 请先运行 login")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1000, "height": 800})
        ctx.add_cookies(json.loads(COOKIE_FILE.read_text(encoding="utf-8")))
        page = ctx.new_page()
        try:
            page.goto(MP_HOME, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"GOTO_WARN: {e}")
        page.wait_for_timeout(3000)
        page.wait_for_timeout(2000)
        _open_editor_and_dump(ctx, page)
        browser.close()


# ---------------------------------------------------------------------------
# 发布
# ---------------------------------------------------------------------------

def cmd_publish(args):
    if not COOKIE_FILE.exists():
        print("NO_COOKIE; 请先运行 login")
        return
    article = Path(args.article).resolve()
    md = article.read_text(encoding="utf-8")
    title, html, images = md_to_html(md)
    title = args.title or title
    author = args.author or "湘月"
    digest = args.summary or ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1200, "height": 900})
        ctx.add_cookies(json.loads(COOKIE_FILE.read_text(encoding="utf-8")))
        page = ctx.new_page()
        try:
            page.goto(MP_HOME, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"GOTO_WARN: {e}")
        page.wait_for_timeout(3000)
        page.wait_for_timeout(2000)

        # 进入编辑器
        opened = False
        for text in ["新建图文", "写新图文", "新的创作"]:
            try:
                btn = page.get_by_text(text, exact=False).first
                if btn.count() > 0:
                    btn.click(timeout=5000)
                    opened = True
                    break
            except Exception:
                pass
        if not opened:
            print("EDITOR_OPEN_FAIL; 找不到新建图文按钮")
            browser.close()
            return
        page.wait_for_timeout(4000)
        page.wait_for_load_state("domcontentloaded")

        # 填标题
        _fill_by_js(page, "input,textarea", "title", title)
        # 作者
        _fill_by_js(page, "input,textarea", "author", author)
        # 摘要（点开摘要区域后填）
        _fill_digest(page, digest)
        # 正文
        _fill_body(page, html)
        # 图片（每个锚点标题后插入）
        for img in images:
            _insert_image(page, img)
        # 封面
        if args.cover:
            _set_cover(page, args.cover)
        # 保存草稿
        _save_draft(page)
        page.screenshot(path=str(DEBUG_DIR / "published.png"))
        print("PUBLISH_DONE; 已保存草稿，见 debug/published.png")
        browser.close()


def _fill_by_js(page, tag, field, value):
    sel = f"""() => {{
        const els = Array.from(document.querySelectorAll('{tag}'));
        const el = els.find(e => /{field}/i.test((e.id||'')+(e.placeholder||'')+(e.className||'')+((e.previousElementSibling&&e.previousElementSibling.textContent)||'')));
        if(!el) return 'NO_FIELD';
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
        setter.call(el, {json.dumps(value)});
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
        el.dispatchEvent(new Event('change',{{bubbles:true}}));
        return 'OK';
    }}"""
    res = page.evaluate(sel)
    print(f"FILL {field}: {res}")


def _fill_digest(page, digest):
    if not digest:
        return
    try:
        # 点击「摘要」链接展开
        link = page.get_by_text("摘要", exact=False).first
        if link.count() > 0:
            link.click(timeout=3000)
            page.wait_for_timeout(500)
    except Exception:
        pass
    _fill_by_js(page, "textarea", "digest", digest)


def _fill_body(page, html):
    res = page.evaluate(
        """(html) => {
            const el = document.querySelector('[contenteditable=\"true\"],.edui-body-container,#ueditor_0 .view,.weui-desktop-media__content [contenteditable]');
            if(!el) return 'NO_BODY';
            el.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertHTML', false, html);
            return 'OK';
        }""",
        html,
    )
    print(f"FILL body: {res}")


def _insert_image(page, img):
    # 找到锚点标题元素，把光标放到它之后
    anchor = img.get("after_heading", "")
    try:
        page.evaluate(
            """(txt) => {
                const hs = Array.from(document.querySelectorAll('h1,h2,h3'));
                const h = hs.find(e => e.textContent.includes(txt));
                if(h){
                    const r = document.createRange();
                    r.setStartAfter(h);
                    r.collapse(true);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(r);
                }
            }""",
            anchor,
        )
    except Exception as e:
        print(f"ANCHOR_FAIL {anchor}: {e}")
    # 点击图片按钮 -> 等待文件选择 -> 选本地文件
    try:
        btn = page.locator('[title="图片"], [data-name="image"], button:has-text("图片")').first
        with page.expect_file_chooser(timeout=5000) as fc:
            btn.click(timeout=5000)
        fc.value.set_files(img["path"])
        page.wait_for_timeout(4000)  # 等待上传完成
        print(f"IMAGE_INSERTED: {img['alt']}")
    except Exception as e:
        print(f"IMAGE_FAIL {img['alt']}: {e}")


def _set_cover(page, cover):
    try:
        btn = page.locator('text=上传封面, [title="封面"], button:has-text("封面")').first
        with page.expect_file_chooser(timeout=5000) as fc:
            btn.click(timeout=5000)
        fc.value.set_files(cover)
        page.wait_for_timeout(3000)
        print("COVER_SET")
    except Exception as e:
        print(f"COVER_FAIL: {e}")


def _save_draft(page):
    try:
        btn = page.get_by_text("保存", exact=False).first
        if btn.count() > 0:
            btn.click(timeout=5000)
            page.wait_for_timeout(2000)
            print("SAVED")
        else:
            print("SAVE_BTN_NOT_FOUND")
    except Exception as e:
        print(f"SAVE_FAIL: {e}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    login_p = sub.add_parser("login")
    login_p.add_argument("--headed", action="store_true", help="有头模式（弹真实窗口，便于人工扫码）")
    sub.add_parser("inspect")
    pp = sub.add_parser("publish")
    pp.add_argument("--article", required=True)
    pp.add_argument("--title", default="")
    pp.add_argument("--author", default="")
    pp.add_argument("--summary", default="")
    pp.add_argument("--cover", default="")
    pp.add_argument("--headed", action="store_true", help="有头模式（弹真实窗口，便于人工扫码）")
    args = ap.parse_args()
    if args.cmd == "login":
        cmd_login(args)
    elif args.cmd == "inspect":
        cmd_inspect(args)
    elif args.cmd == "publish":
        cmd_publish(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
