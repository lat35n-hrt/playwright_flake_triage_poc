import json
import time
from pathlib import Path
from collections import Counter
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError, expect
from urllib.request import urlopen
import os
import random

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = PROJECT_ROOT / "artifacts"
TRACES = ARTIFACTS / "traces"
TRACES.mkdir(parents=True, exist_ok=True)

LOG_JSONL = ARTIFACTS / "playwright_runs.jsonl"

BASE_URL = "http://127.0.0.1:8004"
RUNS = 50

# --- Flake injection (test-side overlay) ---
FLAKE_STRATEGY = os.getenv("FLAKE_STRATEGY", "off")  # off | naive | wait
FLAKE_OVERLAY_MS = int(os.getenv("FLAKE_OVERLAY_MS", "300"))
FLAKE_OVERLAY_PROB = float(os.getenv("FLAKE_OVERLAY_PROB", "0.3"))
TEST_FLAKE_SEED = int(os.getenv("TEST_FLAKE_SEED", "42"))

_rng = random.Random(TEST_FLAKE_SEED)

def assert_server_up():
    with urlopen(f"{BASE_URL}/health", timeout=2) as r:
        if r.status != 200:
            raise RuntimeError(f"Server not ready: {r.status}")


def classify_error(e: Exception) -> str:
    msg = str(e)
    low = msg.lower()
    if isinstance(e, PWTimeoutError):
        # click側のtimeout
        if "locator.click" in low or "click" in low:
            return "click_timeout"
        return "timeout"
    if isinstance(e, AssertionError) or "unexpected status" in msg:
        return "assertion"

    if "intercept" in low or "other element would receive the click" in low or "pointer events" in low:
        return "click_intercepted"

    if "net::" in low or "err_connection_refused" in low:
        return "network"

    return "other"

# inject overlay
def inject_overlay(page, duration_ms: int) -> None:
    page.evaluate(
        """
        (durationMs) => {
          const id = "__flake_overlay";
          const old = document.getElementById(id);
          if (old) old.remove();

          const el = document.createElement("div");
          el.id = id;
          el.style.position = "fixed";
          el.style.inset = "0";
          el.style.background = "rgba(0,0,0,0.01)";
          el.style.zIndex = "2147483647";
          el.style.pointerEvents = "auto";
          document.body.appendChild(el);

          setTimeout(() => { el.remove(); }, durationMs);
        }
        """,
        duration_ms,
    )


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
        # Overlay injection for flake simulation
        step = "start"
        overlay_injected = False

        page = context.new_page()

        step = "goto_index"
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")

        step = "open_detail"
        first_link = page.locator("#list a").first
        first_link.wait_for(state="visible", timeout=5000)
        first_link.click()

        step = "click_approve_prepare"
        btn = page.locator("button#approve")
        btn.wait_for(state="visible", timeout=5000)


        # --- test-side overlay injection ---
        if FLAKE_STRATEGY != "off" and (_rng.random() < FLAKE_OVERLAY_PROB):
            overlay_injected = True
            inject_overlay(page, FLAKE_OVERLAY_MS)

            if FLAKE_STRATEGY == "wait":
                # improved: wait overlay to disappear
                page.locator("#__flake_overlay").wait_for(
                    state="detached",
                    timeout=FLAKE_OVERLAY_MS + 2000
                )


        step = "click_approve"
        if FLAKE_STRATEGY == "naive" and overlay_injected:
            # intentionally fragile: short timeout so click fails while overlay exists
            btn.click(timeout=200)
        else:
            btn.click()

        step = "wait_approved"
        status = page.locator("#status")
        # Fix timeout to 10s to reduce flakes
        expect(status).to_contain_text("Approved", timeout=10_000)

        # status.wait_for(timeout=5000)
        # # text check
        # if "Approved" not in status.inner_text():
        #     raise AssertionError(f"unexpected status: {status.inner_text()}")



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

        # diagnostics
        "step": step,
        "flake_strategy": FLAKE_STRATEGY,
        "overlay_injected": overlay_injected,
        "overlay_ms": FLAKE_OVERLAY_MS,
        "overlay_prob": FLAKE_OVERLAY_PROB,
        "test_flake_seed": TEST_FLAKE_SEED,
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

def inject_overlay(page, duration_ms: int) -> None:
    page.evaluate(
        """
        (durationMs) => {
          const id = "__flake_overlay";
          const old = document.getElementById(id);
          if (old) old.remove();

          const el = document.createElement("div");
          el.id = id;
          el.style.position = "fixed";
          el.style.inset = "0";
          el.style.background = "rgba(0,0,0,0.01)";
          el.style.zIndex = "2147483647";
          el.style.pointerEvents = "auto";
          document.body.appendChild(el);

          setTimeout(() => { el.remove(); }, durationMs);
        }
        """,
        duration_ms,
    )
