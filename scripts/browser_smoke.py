"""Local, no API requests: desktop/mobile and Streamlit rerun regression check."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(os.getenv('BROWSER_ARTIFACTS', 'artifacts'))
out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv('CHROME_EXECUTABLE', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'), headless=True)
    page = browser.new_page(viewport={'width': 1512, 'height': 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.getenv('APP_URL', 'http://127.0.0.1:8501'))
    page.get_by_role('button', name='새 대화', exact=True).wait_for()
    for _ in range(2):
        page.get_by_role('button', name='새 대화', exact=True).click()
        page.wait_for_timeout(350)
    page.get_by_text('확인 규칙', exact=True).first.click()
    page.wait_for_timeout(350)
    page.get_by_text('음성 질문', exact=True).click()
    page.wait_for_timeout(350)
    page.locator('[data-testid=stMain]').evaluate('(e) => e.scrollTop = 0')
    page.screenshot(path=str(out/'desktop.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.wait_for_timeout(500)
    page.locator('[data-testid=stMain]').evaluate('(e) => e.scrollTop = 0')
    page.screenshot(path=str(out/'mobile.png'), full_page=True)
    assert page.locator('.st-key-chat_console').bounding_box()['width'] >= 350
    composer = page.locator('[data-testid=stChatInput]').bounding_box()
    assert composer['y'] + composer['height'] <= 844, composer
    dimensions = page.evaluate('({width:innerWidth, scroll:document.documentElement.scrollWidth, body:document.body.scrollWidth})')
    assert dimensions['scroll'] <= dimensions['width'], dimensions
    assert not page.locator('.st-key-context_panel').is_visible()
    assert page.locator('.st-key-chat_console').is_visible()
    assert not any('removeChild' in error or 'NotFoundError' in error for error in errors), errors
    (out/'browser-results.json').write_text(json.dumps({'errors':errors, 'mobile':dimensions}, indent=2))
    print(json.dumps({'errors':errors, 'mobile':dimensions}))
    browser.close()
