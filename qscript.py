import random
import re
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


PATH_TO_VIDEO_FOLDER = "./video"


CURSOR_AND_EFFECTS_SCRIPT = r"""
(() => {
  const install = () => {
    if (document.getElementById("__qa_cursor_overlay")) {
      return;
    }

    const root = document.createElement("div");
    root.id = "__qa_cursor_overlay";
    root.setAttribute("aria-hidden", "true");
    root.style.cssText = [
      "position:fixed",
      "left:0",
      "top:0",
      "width:0",
      "height:0",
      "z-index:2147483647",
      "pointer-events:none",
      "overflow:visible"
    ].join(";");

    const highlight = document.createElement("div");
    highlight.style.cssText = [
      "position:absolute",
      "left:-32px",
      "top:-32px",
      "width:64px",
      "height:64px",
      "border-radius:50%",
      "background:rgba(255,213,0,0.38)",
      "pointer-events:none"
    ].join(";");

    const cursor = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    cursor.setAttribute("viewBox", "0 0 32 32");
    cursor.setAttribute("width", "32");
    cursor.setAttribute("height", "32");
    cursor.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
    cursor.innerHTML = `
      <path
        d="M4 2 L4 25 L11 19 L16 30 L21 28 L16 17 L27 17 Z"
        fill="#ffffff"
        stroke="#111111"
        stroke-width="1.6"
        stroke-linejoin="round"
      />
    `;

    root.appendChild(highlight);
    root.appendChild(cursor);
    document.body.appendChild(root);

    const moveCursor = (x, y) => {
      root.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      try {
        sessionStorage.setItem("__qa_cursor_position", JSON.stringify({ x, y }));
      } catch (_) {
        // Storage can be unavailable on some pages; the cursor still works.
      }
    };

    window.__qaClickRipple = (x, y) => {
      moveCursor(x, y);
      const ripple = document.createElement("div");
      ripple.style.cssText = [
        "position:absolute",
        "left:-4px",
        "top:-4px",
        "width:8px",
        "height:8px",
        "border:2px solid rgba(255,179,0,0.95)",
        "border-radius:50%",
        "background:rgba(255,235,59,0.18)",
        "pointer-events:none"
      ].join(";");
      root.appendChild(ripple);
      const animation = ripple.animate(
        [
          { transform: "scale(1)", opacity: 0.95 },
          { transform: "scale(4)", opacity: 0 }
        ],
        { duration: 650, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" }
      );
      animation.onfinish = () => ripple.remove();
    };

    window.ShowCallout = async (
      text,
      bgColor = "#FFEB3B",
      textColor = "#000000",
      fade = 2000
    ) => {
      const callout = document.createElement("div");
      callout.textContent = String(text);
      callout.setAttribute("role", "status");
      callout.style.cssText = [
        "position:fixed",
        "top:20px",
        "left:50%",
        "transform:translateX(-50%)",
        "display:inline-block",
        "width:max-content",
        "max-width:80vw",
        "box-sizing:border-box",
        "padding:10px 18px",
        "border:1px solid rgba(0,0,0,0.2)",
        "border-radius:6px",
        `background:${bgColor}`,
        `color:${textColor}`,
        "font:16pt/1.25 Arial,sans-serif",
        "text-align:center",
        "box-shadow:0 3px 12px rgba(0,0,0,0.16)",
        "z-index:2147483647",
        "pointer-events:none",
        "opacity:0"
      ].join(";");
      document.body.appendChild(callout);

      const duration = Math.max(0, Number(fade) || 0);
      const fadeIn = callout.animate(
        [{ opacity: 0 }, { opacity: 1 }],
        { duration, fill: "forwards" }
      );
      await fadeIn.finished;
      await new Promise(resolve => setTimeout(resolve, 900));
      const fadeOut = callout.animate(
        [{ opacity: 1 }, { opacity: 0 }],
        { duration, fill: "forwards" }
      );
      await fadeOut.finished;
      callout.remove();
    };

    document.addEventListener(
      "mousemove",
      event => moveCursor(event.clientX, event.clientY),
      { passive: true }
    );
    let initialPosition = { x: 24, y: 24 };
    try {
      const saved = JSON.parse(sessionStorage.getItem("__qa_cursor_position"));
      if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
        initialPosition = saved;
      }
    } catch (_) {
      // Use the default position when no saved position is available.
    }
    moveCursor(initialPosition.x, initialPosition.y);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
"""


def _center(locator):
    """Scroll an element into view and return its viewport center."""
    locator.scroll_into_view_if_needed(timeout=15000)
    box = locator.bounding_box()
    if box is None:
        raise RuntimeError("Could not determine the element position")
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _move_cursor(page, x, y, position, duration_ms=650):
    """Move the real Playwright mouse with eased, video-visible motion."""
    start_x, start_y = position["x"], position["y"]
    steps = max(12, min(50, duration_ms // 16))

    for step in range(1, steps + 1):
        progress = step / steps
        eased = 3 * progress * progress - 2 * progress * progress * progress
        next_x = start_x + (x - start_x) * eased
        next_y = start_y + (y - start_y) * eased
        page.mouse.move(next_x, next_y)
        page.wait_for_timeout(16)

    position["x"], position["y"] = x, y


def _show_ripple(page, x, y):
    page.evaluate("([x, y]) => window.__qaClickRipple(x, y)", [x, y])
    page.wait_for_timeout(140)


def _type_human_like(page, text):
    """Type every character separately with small randomized pauses."""
    for character in text:
        page.keyboard.type(character)
        delay = random.randint(45, 125)
        if character == " ":
            delay += 70
        page.wait_for_timeout(delay)


def _safe_filename(company_name):
    """Keep the company name readable while excluding path separators."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", company_name)
    cleaned = cleaned.strip().rstrip(".")
    return cleaned or "company"


def CaptureVideo_Magento(
    url,
    company_name,
    language,
    country,
    postcode,
    city,
    street,
    house_no,
):
    """Run the sample search scenario and return an absolute WebM path."""
    video_folder = Path(PATH_TO_VIDEO_FOLDER).expanduser().resolve()
    video_folder.mkdir(parents=True, exist_ok=True)
    existing_videos = set(video_folder.glob("*.webm"))
    video = None

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                record_video_dir=str(video_folder),
                record_video_size={"width": 1280, "height": 720},
                locale=language.strip() or "en-US",
            )
            context.add_init_script(CURSOR_AND_EFFECTS_SCRIPT)

            try:
                page = context.new_page()
                video = page.video
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_function(
                    "() => typeof window.ShowCallout === 'function'",
                    timeout=15000,
                )

                position = {"x": 24, "y": 24}
                page.evaluate(
                    """([text, bgColor, textColor, fade]) =>
                        window.ShowCallout(text, bgColor, textColor, fade)""",
                    [
                        "Magento developer search in " + city,
                        "#FFEB3B",
                        "#111111",
                        2000,
                    ],
                )

                search_box = page.locator('textarea[name="q"]')
                search_box.wait_for(state="visible", timeout=30000)
                x, y = _center(search_box)
                _move_cursor(page, x, y, position)
                _show_ripple(page, x, y)
                search_box.click()

                query = "Magento developer in " + city
                _type_human_like(page, query)
                page.wait_for_timeout(400)

                search_button = page.locator('form button[type="submit"]:visible').first
                x, y = _center(search_button)
                _move_cursor(page, x, y, position)
                _show_ripple(page, x, y)
                try:
                    search_button.click(timeout=15000)
                except PlaywrightError as error:
                    message = str(error).lower()
                    if "context was destroyed" not in message and "navigation" not in message:
                        raise

                first_result = page.locator('a[data-testid="result-title-a"]').first
                first_result.wait_for(state="visible", timeout=60000)
                page.wait_for_function(
                    "() => !!document.getElementById('__qa_cursor_overlay')",
                    timeout=15000,
                )
                x, y = _center(first_result)
                _move_cursor(page, x, y, position, duration_ms=800)
                _show_ripple(page, x, y)
                page.mouse.click(x, y)

                try:
                    page.wait_for_load_state("domcontentloaded", timeout=30000)
                except PlaywrightTimeoutError:
                    # The click is already complete; a slow target site must not
                    # discard an otherwise valid recording.
                    pass
                page.wait_for_timeout(3000)
            finally:
                context.close()
                browser.close()

            if video is None:
                raise RuntimeError("Playwright did not create a video recording")

            source_path = Path(video.path()).resolve()
            target_path = video_folder / (_safe_filename(company_name) + ".webm")
            if source_path != target_path.resolve():
                source_path.replace(target_path)
            return str(target_path.resolve())

    except Exception as error:
        for partial_path in video_folder.glob("*.webm"):
            if partial_path in existing_videos:
                continue
            try:
                partial_path.unlink()
            except OSError:
                # Cleanup must not hide the original automation error.
                pass
        print(
            "Capture failed for " + repr(company_name) + ": " + str(error),
            file=sys.stderr,
        )
        return None
