import json
import time
from pathlib import Path
from collections import Counter
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError, expect
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = PROJECT_ROOT / "artifacts"
TRACES = ARTIFACTS / "traces"
TRACES.mkdir(parents=True, exist_ok=True)

LOG_JSONL = ARTIFACTS / "playwright_runs.jsonl"

BASE_URL = "http://127.0.0.1:8004"
RUNS = 50



def assert_server_up():
    with urlopen(f"{BASE_URL}/health", timeout=2) as r:
        if r.status != 200:
            raise RuntimeError(f"Server not ready: {r.status}")


def classify_error(e: Exception) -> str:
    msg = str(e)
    if isinstance(e, PWTimeoutError):
        return "timeout"
    if "strict mode violation" in msg:
        return "strict_mode"
    if "Element is not visible" in msg:
        return "not_visible"
    if "Element is not enabled" in msg:
        return "not_enabled"
    if "intercept" in msg.lower():
        return "click_intercepted"
    if "net::" in msg.lower():
        return "network"
    return "other"

def run_once(p, run_id: int) -> dict:
    t0 = time.perf_counter()
    trace_path = TRACES / f"trace_run_{run_id:03d}.zip"

    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    context.tracing.start(screenshots=True, snapshots=True, sources=True)

    ok = True
    err_type = ""
    err_msg = ""

    try:
        page = context.new_page()
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")

        first_link = page.locator("#list a").first
        first_link.wait_for(state="visible", timeout=5000)
        first_link.click()

        btn = page.locator("button#approve")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()

        status = page.locator("#status")

        # status.wait_for(timeout=5000)
        # # text check
        # if "Approved" not in status.inner_text():
        #     raise AssertionError(f"unexpected status: {status.inner_text()}")

        # Fix timeout to 10s to reduce flakes
        expect(status).to_contain_text("Approved", timeout=10_000)

    except Exception as e:
        ok = False
        err_type = classify_error(e)
        err_msg = str(e)[:500]  # 伸びすぎ防止
    finally:
        # 失敗時のみ trace 保存（成功時は捨てる）
        if not ok:
            context.tracing.stop(path=str(trace_path))
        else:
            context.tracing.stop()
        context.close()
        browser.close()

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    return {
        "run_id": run_id,
        "ok": ok,
        "error_type": err_type,
        "error_message": err_msg,
        "elapsed_ms": elapsed_ms,
        "base_url": BASE_URL,
        "ts_epoch_ms": int(time.time() * 1000),
    }

def main():
    results = []
    with sync_playwright() as p:
        for i in range(1, RUNS + 1):
            r = run_once(p, i)
            results.append(r)
            with LOG_JSONL.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = len(results)
    ok_count = sum(1 for r in results if r["ok"])
    fail_count = total - ok_count
    rate = round(ok_count / total * 100.0, 2)

    reasons = Counter(r["error_type"] for r in results if not r["ok"])

    print(f"Runs: {total}")
    print(f"OK: {ok_count}, FAIL: {fail_count}, SuccessRate: {rate}%")
    if reasons:
        print("Failure reasons:")
        for k, v in reasons.most_common():
            print(f"  - {k}: {v}")

if __name__ == "__main__":
    main()
