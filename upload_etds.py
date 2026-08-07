"""
ETDS PDF Uploader — Amirtharaj Investment
Connects to the user's own Chrome via CDP (no separate browser window).
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "https://backoffice.steelcitynettrade.com/backoffice/SCwbb"


def find_tds_frame(page):
    for frame in page.frames:
        try:
            for r in frame.query_selector_all("input[type=radio]"):
                text = r.evaluate("el=>(el.parentElement?.textContent||'')+(el.value||'')")
                if "ack" in text.lower():
                    return frame
        except Exception:
            pass
    return None


def find_akno_link(page, stem):
    norm = lambda s: s.replace("\xa0", "").replace(" ", "").strip()
    for frame in page.frames:
        try:
            for a in frame.query_selector_all("a"):
                if norm(a.text_content() or "") == norm(stem):
                    return frame, a
        except Exception:
            pass
    return None, None


def find_detail_frame(page):
    for frame in page.frames:
        try:
            if frame.query_selector("input[type=file]"):
                body = frame.evaluate("document.body?.textContent||''").lower()
                if "ack" in body and "number" in body:
                    return frame
        except Exception:
            pass
    return None


def click_go(frame):
    for val in ["GO", "Go", "go", " GO "]:
        try:
            el = frame.query_selector(f'input[value="{val}"]')
            if el:
                el.click()
                return True
        except Exception:
            pass
    try:
        el = frame.query_selector("input[type=image]")
        if el:
            el.click()
            return True
    except Exception:
        pass
    try:
        for el in frame.query_selector_all("input[type=submit]"):
            if el.is_visible():
                el.click()
                return True
    except Exception:
        pass
    try:
        for el in frame.query_selector_all("button"):
            if (el.text_content() or "").strip().upper() == "GO":
                el.click()
                return True
    except Exception:
        pass
    try:
        for el in frame.query_selector_all("input[type=text]"):
            if el.is_visible():
                el.press("Enter")
                return True
    except Exception:
        pass
    return False


def wait_for(fn, timeout=15, interval=0.3):
    end = time.time() + timeout
    while time.time() < end:
        try:
            r = fn()
            if r:
                return r
        except Exception:
            pass
        time.sleep(interval)
    return None


def main():
    pdf_folder = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not pdf_folder or not pdf_folder.exists():
        raw = input("Enter full path to renamed PDFs folder: ").strip().strip('"')
        pdf_folder = Path(raw)

    pdfs = sorted(pdf_folder.glob("*.pdf"))
    if not pdfs:
        print("No PDF files found in that folder.")
        input("Press ENTER to exit.")
        return

    print(f"\nFound {len(pdfs)} PDF(s) to upload.")

    with sync_playwright() as pw:
        print("\nConnecting to your Chrome browser...")
        browser = None
        for attempt in range(1, 13):   # retry up to ~24 seconds
            try:
                browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
                break
            except Exception:
                print(f"  Waiting for Chrome to start... ({attempt})", end="\r")
                time.sleep(2)
        if not browser:
            print("\n\nERROR: Could not connect to Chrome after waiting.")
            print("  The most common cause: Chrome was still running when the bat file")
            print("  tried to restart it, so it opened WITHOUT the debug port.")
            print("  -> Close ALL Chrome windows, then run run_uploader.bat again.")
            input("\nPress ENTER to exit.")
            return

        print("  Connected!")

        # use the first existing context (has your cookies/session)
        contexts = browser.contexts
        if not contexts:
            print("\nERROR: No browser context found.")
            input("Press ENTER to exit.")
            return

        ctx = contexts[0]

        # find or navigate to Default.aspx
        active = None
        for p in ctx.pages:
            try:
                u = p.url
                if "backoffice" in u and "login" not in u.lower() and "logout" not in u.lower():
                    active = p
                    break
            except Exception:
                pass

        if not active:
            # open Default.aspx in a new tab
            print("  No Steel City page found — opening Default.aspx...")
            active = ctx.new_page()
            active.goto(f"{BASE}/Default.aspx", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

        print(f"  Using page: {active.url[:70]}")

        # check if redirected to login
        if "login" in active.url.lower() or "logout" in active.url.lower():
            print("\n  Steel City is asking for login.")
            print("  Please log in in the Chrome window, then come back and press ENTER.")
            input()
            time.sleep(2)
            active.goto(f"{BASE}/Default.aspx", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            if "login" in active.url.lower() or "logout" in active.url.lower():
                print("\nERROR: Still not logged in. Please try again.")
                input("Press ENTER to exit.")
                return

        # print frame map
        print(f"\n  Frames ({len(active.frames)}):")
        for j, f in enumerate(active.frames):
            try:
                n = len(f.query_selector_all("input"))
            except Exception:
                n = "?"
            print(f"    [{j}] inputs={n}  {f.url[:70]}")

        # navigate to e TDS-TCS
        print("\n  Looking for e TDS-TCS menu...")
        tds_nav_done = False
        for frame in active.frames:
            try:
                for a in frame.query_selector_all("a"):
                    if (a.text_content() or "").strip() == "e TDS-TCS":
                        a.click()
                        tds_nav_done = True
                        print(f"  Clicked e TDS-TCS")
                        time.sleep(3)
                        break
                if tds_nav_done:
                    break
            except Exception:
                pass

        if not tds_nav_done:
            print("  Menu not found automatically.")
            print("  Please click  e-Governance → TIN Services → e TDS-TCS  in Chrome.")
            input("  Press ENTER when on the TDS search page... ")

        # find TDS search frame
        tds_frame = wait_for(lambda: find_tds_frame(active), timeout=12)
        if not tds_frame:
            print("\nERROR: TDS search form not found.")
            print("  Frames visible:")
            for f in active.frames:
                print(f"    {f.url[:70]}")
            input("Press ENTER to exit.")
            return

        tds_frame_url = tds_frame.url
        print(f"\n  TDS form ready: {tds_frame_url[:70]}")
        print(f"  Starting upload of {len(pdfs)} file(s)...\n")

        ok = failed = not_found = 0

        for i, pdf in enumerate(pdfs):
            stem = pdf.stem
            print(f"  [{i + 1:>2}/{len(pdfs)}]  {stem}", end="  ...  ", flush=True)

            try:
                tds_frame = wait_for(lambda: find_tds_frame(active), timeout=15)
                if not tds_frame:
                    raise Exception("TDS form not found")

                # click Ack No radio
                ack_radio = None
                for r in tds_frame.query_selector_all("input[type=radio]"):
                    text = r.evaluate("el=>(el.parentElement?.textContent||'')+(el.value||'')")
                    if "ack" in text.lower():
                        ack_radio = r
                        break
                if not ack_radio:
                    raise Exception("Ack No radio not found")
                ack_radio.click()

                # wait for text input after postback
                text_input = None
                for _ in range(40):
                    time.sleep(0.3)
                    tf = find_tds_frame(active)
                    if tf:
                        for el in tf.query_selector_all("input[type=text]"):
                            if el.is_visible():
                                text_input = el
                                tds_frame = tf
                                break
                    if text_input:
                        break
                if not text_input:
                    raise Exception("Text input did not appear after radio click")

                # fill ack number and click GO
                text_input.fill(stem)
                time.sleep(0.2)
                if not click_go(tds_frame):
                    raise Exception("GO button not found")

                # find AKNO result link
                result_frame = akno_link = None
                for _ in range(80):
                    time.sleep(0.25)
                    result_frame, akno_link = find_akno_link(active, stem)
                    if akno_link:
                        break

                if not akno_link:
                    print("? (not in backoffice)")
                    not_found += 1
                    try:
                        tds_frame.goto(tds_frame_url)
                    except Exception:
                        pass
                    time.sleep(1)
                    continue

                akno_link.click()

                # wait for detail frame with file upload
                detail_frame = wait_for(lambda: find_detail_frame(active), timeout=15)
                if not detail_frame:
                    raise Exception("Detail page did not load")
                time.sleep(0.7)

                # attach PDF
                file_input = detail_frame.query_selector("input[type=file]")
                if not file_input:
                    raise Exception("File input not found")
                file_input.set_input_files(str(pdf))
                time.sleep(0.5)

                # click Update
                update_btn = None
                for el in detail_frame.query_selector_all("input, button"):
                    val = (el.get_attribute("value") or el.text_content() or "").strip()
                    if "update" in val.lower():
                        update_btn = el
                        break
                if not update_btn:
                    raise Exception("Update button not found")
                update_btn.click()
                time.sleep(2.5)

                print("OK uploaded")
                ok += 1

            except Exception as exc:
                print(f"FAILED: {exc}")
                failed += 1
                try:
                    tds_frame.goto(tds_frame_url)
                except Exception:
                    pass
                time.sleep(1)

        print()
        print("=" * 54)
        print(f"  DONE  |  Uploaded: {ok}   Not found: {not_found}   Errors: {failed}")
        print("=" * 54)
        input("\nPress ENTER to finish.")


if __name__ == "__main__":
    main()
